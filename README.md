# Automated RAG & LLM Decision Pipeline

LLMs hallucinate on rare facts. This pipeline decides **at runtime** whether to retrieve
Wikipedia context before answering, and measures the hallucination reduction on
[PopQA](https://huggingface.co/datasets/akariasai/PopQA).

| Stage | What |
|---|---|
| 1. Setup + ETL | PopQA sample (1,000 Qs, popularity-stratified) + Wikipedia passages → Postgres (Docker) |
| 2. Pipeline | Llama-3-8B-Instruct (4-bit, GPU). Modes: `never`, `always`, `adaptive` |
| 3. Evaluate | Accuracy + hallucination rate per mode, threshold tuning, runs stored in Postgres |
| 4. Ship | pytest + GitHub Actions, Dockerfile, Cloud Run Streamlit explorer |

## Quickstart

```bash
cp .env.example .env            # add HF_TOKEN
docker compose up -d            # Postgres 16
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && pip install -e .
python -m rag_pipeline.etl      # ~17 min first run (Wikipedia is rate-limited; cached after)
pytest -q
```

## Data model

- `questions`: PopQA id, question, relation (`prop`), subject popularity (`s_pop`, monthly page views), accepted answers (JSONB)
- `passages`: ~100-word chunks of each subject's Wikipedia article (`wiki_title`, `chunk_idx`, `text`)

Sampling: 100 questions from each log-popularity decile, so rare and popular entities are evenly represented.

## Results (Stage 3)

`python -m rag_pipeline.evaluate` scores the cached generations, tunes the adaptive thresholds on a
50% tune split, and reports on the held-out 500-question test split. Outputs land in Postgres
(`runs`, `predictions`) and in [`results/`](results/) for the DB-less explorer.

| Mode | Accuracy | Strict accuracy | Hallucination rate | Retrieval rate | Avg latency |
|---|---|---|---|---|---|
| never | 27.6% | 23.2% | 60.4% | 0% | 121 ms |
| always | 62.8% | 57.8% | 23.2% | 100% | 741 ms |
| adaptive (`s_pop < 9568` or confidence `< 0.75`) | 62.2% | 57.0% | 23.8% | 86.6% | 670 ms |

**Scoring.** Accuracy uses a lenient matcher: a strict match, a partial answer ("Catholic" for
"Catholic Church", a surname only), the same words in any order ("noir crime film" for
"film noir"), or a near-identical spelling. Strict accuracy (accepted answer appears verbatim)
is stored alongside for audits. In a hand check of 50 lenient-only matches, 43 were right,
6 were a broader category than the gold ("Comedy" for "romantic comedy") and 1 was wrong
(since fixed).

**Tuning.** Adaptive picks the setting with the fewest retrievals within 1 accuracy point of the
best on the tune split. Retrieval helps in every popularity decile for this 8B model, so the
policy still retrieves for most questions; `results/pareto.csv` lists the cheaper trade-offs
(e.g. retrieving for 60% of questions keeps ~58% accuracy on the tune split).
