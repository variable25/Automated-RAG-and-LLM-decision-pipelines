"""Read the exported results/*.csv for the API (no DB, no model).

Files (written by `python -m rag_pipeline.evaluate`)
  summary.csv        : one row per mode x split (accuracy, retrieval rate, latency, thresholds)
  threshold_grid.csv : every adaptive threshold pair scored on the tune split
  pareto.csv         : the grid points no other point beats on both accuracy and retrieval
  predictions.csv    : one row per question, with each mode's answer and scores side by side
"""
import json
from pathlib import Path

import pandas as pd

from rag_pipeline.config import ROOT

RESULTS_DIR = ROOT / "results"
MODES = ["never", "always", "adaptive"]
MODE_FIELDS = ["answer", "confidence", "correct", "correct_strict", "hallucinated", "retrieved"]
FILES = {"summary": "summary.csv", "grid": "threshold_grid.csv", "pareto": "pareto.csv",
         "predictions": "predictions.csv"}


def load(results_dir: Path = RESULTS_DIR) -> dict[str, pd.DataFrame]:
    out = {name: pd.read_csv(results_dir / f) for name, f in FILES.items()}
    preds = out["predictions"]
    preds["answers"] = preds["answers"].map(json.loads)
    for mode in MODES:
        preds[f"{mode}_answer"] = preds[f"{mode}_answer"].fillna("")
    return out


def chosen_thresholds(summary: pd.DataFrame) -> tuple[float, float]:
    row = summary[summary["mode"] == "adaptive"].iloc[0]
    return float(row["pop_threshold"]), float(row["conf_threshold"])


def verdict(df: pd.DataFrame) -> pd.Series:
    """Per answer: correct under both rules, lenient only, abstained, or wrong."""
    v = pd.Series("wrong", index=df.index)
    v[df["correct"] & df["correct_strict"]] = "correct (both)"
    v[df["correct"] & ~df["correct_strict"]] = "lenient only"
    v[~df["correct"] & ~df["hallucinated"]] = "abstained"
    return v
