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
