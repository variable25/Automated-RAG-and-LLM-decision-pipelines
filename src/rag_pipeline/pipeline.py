"""Retrieval-decision pipeline.

Modes
  never    : closed-book answer
  always   : BM25 top-k passages + answer
  adaptive : retrieve if the entity is rare (s_pop < pop_threshold) or the
             closed-book answer is low-confidence (confidence < conf_threshold)

`generate` precomputes both closed-book and retrieval answers for every question once,
so any adaptive threshold setting can be evaluated offline without re-running the LLM.

Run: python -m rag_pipeline.pipeline generate [--limit N] [--batch-size 8]
"""
import argparse
import time
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from tqdm import tqdm

from rag_pipeline.db import connect, init_schema
from rag_pipeline.llm import build_messages, load_backend
from rag_pipeline.retriever import BM25Retriever

TOP_K = 3


def should_retrieve(s_pop: int, closed_conf: float | None, pop_threshold: float, conf_threshold: float) -> bool:
    """Adaptive policy. closed_conf=None means the closed-book pass hasn't run yet (popularity check only)."""
    if s_pop < pop_threshold:
        return True
    return closed_conf is not None and closed_conf < conf_threshold


@dataclass
class Answer:
    answer: str
    confidence: float
    retrieved: bool
    contexts: list


class Pipeline:
    def __init__(self, backend, retriever: BM25Retriever, top_k: int = TOP_K):
        self.backend, self.retriever, self.top_k = backend, retriever, top_k

    def _closed(self, q: str) -> Answer:
        g = self.backend.generate([build_messages(q)])[0]
        return Answer(g.answer, g.confidence, False, [])

    def _rag(self, q: str) -> Answer:
        ctx = self.retriever.search(q, self.top_k)
        g = self.backend.generate([build_messages(q, ctx)])[0]
        return Answer(g.answer, g.confidence, True, ctx)

    def answer(self, question: str, s_pop: int, mode: str = "adaptive",
               pop_threshold: float = 1000, conf_threshold: float = 0.6) -> Answer:
        if mode == "never":
            return self._closed(question)
        if mode == "always" or should_retrieve(s_pop, None, pop_threshold, conf_threshold):
            return self._rag(question)
        closed = self._closed(question)
        if should_retrieve(s_pop, closed.confidence, pop_threshold, conf_threshold):
            return self._rag(question)
        return closed


def generate(limit: int | None, batch_size: int) -> None:
    backend = load_backend()
    with connect() as conn:
        init_schema(conn)
        retriever = BM25Retriever.from_db(conn)
        print(f"indexed {len(retriever.passages)} passages; model={backend.name}")
        for with_ctx in (False, True):
            todo = conn.execute(
                """SELECT q.id, q.question FROM questions q
                   WHERE NOT EXISTS (SELECT 1 FROM generations g WHERE g.question_id=q.id
                                     AND g.model=%s AND g.with_context=%s)
                   ORDER BY q.id LIMIT %s""",
                (backend.name, with_ctx, limit),
            ).fetchall()
            for i in tqdm(range(0, len(todo), batch_size), desc=f"with_context={with_ctx}"):
                chunk = todo[i:i + batch_size]
                ctxs = [retriever.search(q, TOP_K) if with_ctx else [] for _, q in chunk]
                t0 = time.perf_counter()
                gens = backend.generate([build_messages(q, c or None) for (_, q), c in zip(chunk, ctxs)])
                ms = (time.perf_counter() - t0) * 1000 / len(chunk)
                conn.cursor().executemany(
                    """INSERT INTO generations (question_id, model, with_context, answer, confidence, contexts, latency_ms)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    [(qid, backend.name, with_ctx, g.answer, g.confidence, Jsonb(c), ms)
                     for (qid, _), g, c in zip(chunk, gens, ctxs)],
                )
                conn.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["generate"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=8)
    a = ap.parse_args()
    generate(a.limit, a.batch_size)
