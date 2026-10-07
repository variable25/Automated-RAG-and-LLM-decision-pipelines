"""Stage 1 ETL: PopQA sample + Wikipedia passages -> Postgres.

Extract:   PopQA (HF) and full Wikipedia plaintext per subject (MediaWiki API, cached on disk).
Transform: popularity-stratified sample; articles chunked into ~100-word passages.
Load:      idempotent upserts into `questions` and `passages`.

Run: python -m rag_pipeline.etl
"""
import json
import time
from urllib.parse import quote

import numpy as np
import pandas as pd
import requests
from datasets import load_dataset
from psycopg.types.json import Jsonb
from tqdm import tqdm

from rag_pipeline.config import RAW_DIR, SAMPLE_SIZE, SEED
from rag_pipeline.db import connect, init_schema

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "rag-decision-pipeline/0.1 (educational project; github.com/variable25)"
CHUNK_WORDS = 100
MAX_CHUNKS = 30  # ~3k words per article is plenty for PopQA-style facts
REQUEST_INTERVAL_S = 1.0


# ---------- extract ----------
def load_popqa() -> pd.DataFrame:
    return load_dataset("akariasai/PopQA", split="test").to_pandas()


def fetch_wiki_text(title: str, session: requests.Session) -> str:
    cache = RAW_DIR / "wiki" / f"{quote(title, safe='')}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    params = {
        "action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1,
        "titles": title, "format": "json", "formatversion": 2,
    }
    for attempt in range(8):
        time.sleep(REQUEST_INTERVAL_S)  # stay under Wikimedia's anonymous rate limit
        r = session.get(WIKI_API, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(int(r.headers.get("Retry-After", 0)) or min(5 * 2 ** attempt, 120))
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError(f"wikipedia fetch failed for {title!r}: HTTP {r.status_code}")
    pages = r.json()["query"]["pages"]
    text = pages[0].get("extract", "") if pages else ""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


# ---------- transform ----------
def stratified_sample(df: pd.DataFrame, n: int, seed: int = SEED, bins: int = 10) -> pd.DataFrame:
    """Equal draws from each log-popularity decile so rare and popular entities are both covered."""
    df = df.copy()
    df["pop_bin"] = pd.qcut(np.log10(df["s_pop"].clip(lower=1)), q=bins, labels=False, duplicates="drop")
    per_bin = n // df["pop_bin"].nunique()
    out = df.groupby("pop_bin").sample(n=per_bin, random_state=seed)
    return out.drop(columns="pop_bin").reset_index(drop=True)


def chunk_text(text: str, chunk_words: int = CHUNK_WORDS, max_chunks: int = MAX_CHUNKS) -> list[str]:
    """Pack paragraphs into ~chunk_words passages; drop section headers and empty lines."""
    paras = [p.strip() for p in text.split("\n") if p.strip() and not p.strip().startswith("==")]
    chunks, cur = [], []
    for p in paras:
        words = p.split()
        while words:
            room = chunk_words - len(cur)
            cur.extend(words[:room])
            words = words[room:]
            if len(cur) >= chunk_words:
                chunks.append(" ".join(cur))
                cur = []
                if len(chunks) >= max_chunks:
                    return chunks
    if cur:
        chunks.append(" ".join(cur))
    return chunks[:max_chunks]


# ---------- load ----------
def load_questions(conn, df: pd.DataFrame) -> None:
    rows = [
        (int(r.id), r.question, r.subj, r.prop, r.obj, r.s_wiki_title,
         int(r.s_pop), int(r.o_pop), Jsonb(json.loads(r.possible_answers)))
        for r in df.itertuples()
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO questions (id, question, subj, prop, obj, s_wiki_title, s_pop, o_pop, possible_answers)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (id) DO UPDATE SET question=EXCLUDED.question, s_pop=EXCLUDED.s_pop,
                   possible_answers=EXCLUDED.possible_answers""",
            rows,
        )


def load_passages(conn, title: str, chunks: list[str]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO passages (wiki_title, chunk_idx, text) VALUES (%s,%s,%s)
               ON CONFLICT (wiki_title, chunk_idx) DO UPDATE SET text=EXCLUDED.text""",
            [(title, i, c) for i, c in enumerate(chunks)],
        )


def main() -> None:
    sample = stratified_sample(load_popqa(), SAMPLE_SIZE)
    titles = sorted(sample["s_wiki_title"].unique())
    print(f"sampled {len(sample)} questions, {len(titles)} unique subject articles")

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    with connect() as conn:
        init_schema(conn)
        load_questions(conn, sample)
        missing = 0
        for t in tqdm(titles, desc="wikipedia"):
            chunks = chunk_text(fetch_wiki_text(t, session))
            missing += not chunks
            load_passages(conn, t, chunks)
        conn.commit()
        nq = conn.execute("SELECT count(*) FROM questions").fetchone()[0]
        np_ = conn.execute("SELECT count(*) FROM passages").fetchone()[0]
    print(f"loaded questions={nq} passages={np_} articles_without_text={missing}")


if __name__ == "__main__":
    main()
