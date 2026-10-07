"""Stage 3: score cached generations, tune adaptive thresholds, store runs in Postgres.

Scoring
  lenient (primary)  : strict match, or answer tokens within an accepted answer ("Catholic" ~
                       "Catholic Church"), or an accepted answer's tokens within the output in any
                       order ("noir crime film" ~ "film noir"), or a near-identical spelling
  strict (audit)     : an accepted PopQA answer string appears in the normalized output

Metrics (per mode)
  accuracy           : lenient score; strict_accuracy is kept alongside for audits
  hallucination_rate : answered (not "I don't know") but wrong
  abstain_rate       : "I don't know"
  retrieval_rate     : share of questions that triggered retrieval (cost proxy)

Thresholds are tuned on a 50% tune split and reported on the held-out test split.

Run: python -m rag_pipeline.evaluate
"""
import json
import re
import string
import unicodedata
from difflib import SequenceMatcher

import numpy as np
import pandas as pd
from psycopg.types.json import Jsonb

from rag_pipeline.config import ROOT, SEED
from rag_pipeline.db import connect, init_schema

RESULTS_DIR = ROOT / "results"
CONF_GRID = np.round(np.arange(0.0, 1.0001, 0.05), 2)
POP_QUANTILES = np.arange(0.0, 1.0001, 0.1)
EXPORT_COLS = ["answer", "confidence", "correct", "correct_strict", "hallucinated", "retrieved"]
_ABSTAIN = re.compile(r"\b(i don'?t know|i do not know|unknown|not sure)\b")
_ARTICLES = re.compile(r"\b(a|an|the)\b")
# too vague to count as a match on their own ("film" vs "horror film")
_GENERIC = {"film", "movie", "music", "church", "album", "song", "band", "series", "novel", "rock", "pop"}
FUZZY_RATIO = 0.9


# ---------- scoring ----------
def _fold_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def normalize(s: str) -> str:
    s = _fold_accents(s).lower().replace("’", "'")
    s = "".join(ch for ch in s if ch not in set(string.punctuation) - {"'"})
    return " ".join(_ARTICLES.sub(" ", s).split())


def is_abstain(answer: str) -> bool:
    return bool(_ABSTAIN.search(answer.lower().replace("’", "'")))


def is_correct(answer: str, possible_answers: list[str]) -> bool:
    a = normalize(answer)
    return any(normalize(p) and normalize(p) in a for p in possible_answers)


def is_correct_lenient(answer: str, possible_answers: list[str]) -> bool:
    if is_correct(answer, possible_answers):
        return True
    if is_abstain(answer):
        return False
    a = normalize(answer)
    at = set(a.split())
    for p in possible_answers:
        g = normalize(p)
        gt = set(g.split())
        if not g:
            continue
        if at and at <= gt and at - _GENERIC:  # partial answer, e.g. surname only
            return True
        if gt <= at and gt - _GENERIC:  # same words, different order
            return True
        if len(g) >= 6 and SequenceMatcher(None, a, g).ratio() >= FUZZY_RATIO:  # spelling variant
            return True
    return False


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["correct_strict"] = [is_correct(a, p) for a, p in zip(df["answer"], df["possible_answers"])]
    df["correct"] = [is_correct_lenient(a, p) for a, p in zip(df["answer"], df["possible_answers"])]
    df["abstained"] = df["answer"].map(is_abstain) & ~df["correct"]
    df["hallucinated"] = ~df["correct"] & ~df["abstained"]
    return df


# ---------- policies ----------
def wide(gen: pd.DataFrame) -> pd.DataFrame:
    """One row per question with closed-book (_c) and retrieval (_r) columns."""
    c = gen[~gen["with_context"]].set_index("question_id")
    r = gen[gen["with_context"]].set_index("question_id")
    base = c[["question", "prop", "s_pop", "possible_answers"]]
    cols = ["answer", "confidence", "correct", "correct_strict", "abstained", "hallucinated", "latency_ms"]
    return base.join(c[cols].add_suffix("_c")).join(r[cols].add_suffix("_r")).dropna(subset=["answer_r"])


def apply_policy(w: pd.DataFrame, mode: str, pop_t: float = 0, conf_t: float = 0) -> pd.DataFrame:
    """Pick closed-book or retrieval answer per question, with the latency the runtime policy would incur."""
    if mode == "never":
        retrieve = pd.Series(False, index=w.index)
        by_pop = retrieve
    elif mode == "always":
        retrieve = pd.Series(True, index=w.index)
        by_pop = retrieve
    else:
        by_pop = w["s_pop"] < pop_t
        retrieve = by_pop | (w["confidence_c"] < conf_t)
    out = pd.DataFrame(index=w.index)
    out["retrieved"] = retrieve
    for col in ["answer", "confidence", "correct", "correct_strict", "abstained", "hallucinated"]:
        out[col] = np.where(retrieve, w[f"{col}_r"], w[f"{col}_c"])
    # rare entities skip the closed-book pass; confidence fallbacks pay for both passes
    out["latency_ms"] = np.select(
        [~retrieve, by_pop], [w["latency_ms_c"], w["latency_ms_r"]], w["latency_ms_c"] + w["latency_ms_r"]
    )
    return out


def metrics(p: pd.DataFrame) -> dict:
    return {
        "n": int(len(p)),
        "accuracy": float(p["correct"].mean()),
        "strict_accuracy": float(p["correct_strict"].mean()),
        "hallucination_rate": float(p["hallucinated"].mean()),
        "abstain_rate": float(p["abstained"].mean()),
        "retrieval_rate": float(p["retrieved"].mean()),
        "avg_latency_ms": float(p["latency_ms"].mean()),
    }


def tune(w: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Grid-search (pop, conf) thresholds. Objective: max accuracy, tie-break fewer retrievals."""
    pops = sorted(set(np.quantile(w["s_pop"], POP_QUANTILES).round().tolist()) | {0.0})
    rows = [
        {"pop_threshold": pt, "conf_threshold": float(ct), **metrics(apply_policy(w, "adaptive", pt, ct))}
        for pt in pops for ct in CONF_GRID
    ]
    grid = pd.DataFrame(rows)
    best = grid.sort_values(["accuracy", "retrieval_rate"], ascending=[False, True]).iloc[0]
    return grid, {"pop_threshold": float(best.pop_threshold), "conf_threshold": float(best.conf_threshold)}


def split(w: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    tune_idx = w.sample(frac=0.5, random_state=seed).index
    return w.loc[tune_idx], w.drop(tune_idx)


# ---------- io ----------
def load_generations(conn) -> pd.DataFrame:
    rows = conn.execute(
        """SELECT g.question_id, g.model, g.with_context, g.answer, g.confidence, g.latency_ms,
                  q.question, q.prop, q.s_pop, q.possible_answers
           FROM generations g JOIN questions q ON q.id = g.question_id"""
    ).fetchall()
    cols = ["question_id", "model", "with_context", "answer", "confidence", "latency_ms",
            "question", "prop", "s_pop", "possible_answers"]
    return pd.DataFrame(rows, columns=cols)


def save_run(conn, model, mode, params, split_name, m, preds: pd.DataFrame) -> int:
    run_id = conn.execute(
        """INSERT INTO runs (model, mode, params, split, n, accuracy, strict_accuracy, hallucination_rate,
                             abstain_rate, retrieval_rate, avg_latency_ms)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (model, mode, Jsonb(params), split_name, m["n"], m["accuracy"], m["strict_accuracy"],
         m["hallucination_rate"], m["abstain_rate"], m["retrieval_rate"], m["avg_latency_ms"]),
    ).fetchone()[0]
    conn.cursor().executemany(
        """INSERT INTO predictions (run_id, question_id, retrieved, answer, confidence, correct, correct_strict,
                                    hallucinated)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        [(run_id, int(q), bool(r.retrieved), r.answer, float(r.confidence), bool(r.correct),
          bool(r.correct_strict), bool(r.hallucinated))
         for q, r in preds.iterrows()],
    )
    return run_id


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    with connect() as conn:
        init_schema(conn)
        gen = load_generations(conn)
        for model, g in gen.groupby("model"):
            w = wide(score(g))
            tune_w, test_w = split(w)
            grid, best = tune(tune_w)
            policies = {"never": {}, "always": {}, "adaptive": best}
            summary, test_preds = [], {}
            for mode, params in policies.items():
                pt, ct = params.get("pop_threshold", 0), params.get("conf_threshold", 0)
                for split_name, part in [("tune", tune_w), ("test", test_w), ("all", w)]:
                    p = apply_policy(part, mode, pt, ct)
                    m = metrics(p)
                    run_id = save_run(conn, model, mode, params, split_name, m, p)
                    summary.append({"run_id": run_id, "model": model, "mode": mode, "split": split_name,
                                    **params, **m})
                    if split_name == "all":
                        test_preds[mode] = p
            conn.commit()

            # exports for the (DB-less) Streamlit explorer
            pd.DataFrame(summary).to_csv(RESULTS_DIR / "summary.csv", index=False)
            grid.to_csv(RESULTS_DIR / "threshold_grid.csv", index=False)
            per_q = w[["question", "prop", "s_pop"]].copy()
            per_q["answers"] = w["possible_answers"].map(json.dumps)
            per_q["split"] = np.where(w.index.isin(test_w.index), "test", "tune")
            for mode, p in test_preds.items():
                per_q[[f"{mode}_{c}" for c in EXPORT_COLS]] = p[EXPORT_COLS].values
            per_q.reset_index().to_csv(RESULTS_DIR / "predictions.csv", index=False)

            test = pd.DataFrame(summary).query("split == 'test'")
            print(f"model={model} best thresholds={best}")
            print(test[["mode", "accuracy", "strict_accuracy", "hallucination_rate", "abstain_rate", "retrieval_rate",
                        "avg_latency_ms"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
