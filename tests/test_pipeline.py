import pytest

from rag_pipeline.llm import Generation, build_messages
from rag_pipeline.pipeline import Pipeline, should_retrieve
from rag_pipeline.retriever import BM25Retriever

PASSAGES = [
    ("George Rankin", "George James Rankin was an Australian politician and soldier."),
    ("Paris", "Paris is the capital and largest city of France."),
    ("Inception", "Inception is a 2010 science fiction film directed by Christopher Nolan."),
]


class FakeBackend:
    """Confident without context, records every prompt."""
    name = "fake"

    def __init__(self, closed_conf: float):
        self.closed_conf, self.calls = closed_conf, []

    def generate(self, batch):
        self.calls.extend(batch)
        return [Generation("x", 0.99 if "Context:" in m[-1]["content"] else self.closed_conf) for m in batch]


@pytest.mark.parametrize("s_pop,conf,expected", [
    (10, 0.99, True),     # rare entity -> retrieve
    (50_000, 0.2, True),  # popular but unsure -> retrieve
    (50_000, 0.9, False), # popular and confident -> closed book
    (50_000, None, False),
])
def test_should_retrieve(s_pop, conf, expected):
    assert should_retrieve(s_pop, conf, pop_threshold=1000, conf_threshold=0.6) is expected


def test_bm25_finds_relevant_passage():
    r = BM25Retriever(PASSAGES)
    assert r.search("Who directed Inception?", k=1)[0][0] == "Inception"
    assert len(r.search("capital of France", k=2)) == 2


def test_build_messages_with_and_without_context():
    closed = build_messages("Q?")
    rag = build_messages("Q?", PASSAGES[:1])
    assert "Context:" not in closed[-1]["content"]
    assert "[George Rankin]" in rag[-1]["content"]
    assert closed[0]["role"] == "system"


@pytest.mark.parametrize("mode,s_pop,closed_conf,n_calls,retrieved", [
    ("never", 10, 0.1, 1, False),
    ("always", 10**6, 0.99, 1, True),
    ("adaptive", 10, 0.99, 1, True),        # rare: skip closed-book pass
    ("adaptive", 10**6, 0.99, 1, False),    # popular + confident: no retrieval
    ("adaptive", 10**6, 0.1, 2, True),      # popular + unsure: fall back to retrieval
])
def test_pipeline_modes(mode, s_pop, closed_conf, n_calls, retrieved):
    be = FakeBackend(closed_conf)
    a = Pipeline(be, BM25Retriever(PASSAGES)).answer("What is the capital of France?", s_pop, mode=mode)
    assert a.retrieved is retrieved
    assert len(be.calls) == n_calls
