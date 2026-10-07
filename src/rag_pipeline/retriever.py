"""BM25 retriever over all Wikipedia passages in Postgres (corpus is small enough to index in memory)."""
import re

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Retriever:
    def __init__(self, passages: list[tuple[str, str]]):
        """passages: list of (wiki_title, text)."""
        self.passages = passages
        self.bm25 = BM25Okapi([tokenize(f"{t} {p}") for t, p in passages])

    @classmethod
    def from_db(cls, conn) -> "BM25Retriever":
        rows = conn.execute("SELECT wiki_title, text FROM passages ORDER BY id").fetchall()
        return cls([(t, p) for t, p in rows])

    def search(self, query: str, k: int = 3) -> list[tuple[str, str]]:
        scores = self.bm25.get_scores(tokenize(query))
        top = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:k]
        return [self.passages[i] for i in top]
