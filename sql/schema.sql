-- Idempotent schema. Applied by docker on first init and by `python -m rag_pipeline.db init`.

CREATE TABLE IF NOT EXISTS questions (
    id               INTEGER PRIMARY KEY,      -- PopQA id
    question         TEXT    NOT NULL,
    subj             TEXT    NOT NULL,
    prop             TEXT    NOT NULL,          -- relation, e.g. occupation, director
    obj              TEXT    NOT NULL,
    s_wiki_title     TEXT    NOT NULL,
    s_pop            INTEGER NOT NULL,          -- monthly Wikipedia page views of subject
    o_pop            INTEGER NOT NULL,
    possible_answers JSONB   NOT NULL           -- list of accepted answer strings
);
CREATE INDEX IF NOT EXISTS idx_questions_s_pop ON questions (s_pop);

CREATE TABLE IF NOT EXISTS passages (
    id         SERIAL  PRIMARY KEY,
    wiki_title TEXT    NOT NULL,
    chunk_idx  INTEGER NOT NULL,
    text       TEXT    NOT NULL,
    UNIQUE (wiki_title, chunk_idx)
);
CREATE INDEX IF NOT EXISTS idx_passages_title ON passages (wiki_title);

-- Stage 2: cached LLM outputs. Both closed-book and retrieval answers per question,
-- so every retrieval policy can be evaluated offline.
CREATE TABLE IF NOT EXISTS generations (
    question_id  INTEGER NOT NULL REFERENCES questions(id),
    model        TEXT    NOT NULL,
    with_context BOOLEAN NOT NULL,
    answer       TEXT    NOT NULL,
    confidence   REAL,                          -- geometric-mean token probability
    contexts     JSONB   NOT NULL DEFAULT '[]', -- [[wiki_title, passage], ...]
    latency_ms   REAL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (question_id, model, with_context)
);

-- Stage 3: one row per (mode, thresholds, split) evaluation + its per-question predictions.
CREATE TABLE IF NOT EXISTS runs (
    id                 SERIAL PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    model              TEXT  NOT NULL,
    mode               TEXT  NOT NULL CHECK (mode IN ('never', 'always', 'adaptive')),
    params             JSONB NOT NULL DEFAULT '{}',   -- pop_threshold, conf_threshold
    split              TEXT  NOT NULL,                -- tune | test | all
    n                  INTEGER NOT NULL,
    accuracy           REAL NOT NULL,
    hallucination_rate REAL NOT NULL,
    abstain_rate       REAL NOT NULL,
    retrieval_rate     REAL NOT NULL,
    avg_latency_ms     REAL
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id       INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    question_id  INTEGER NOT NULL REFERENCES questions(id),
    retrieved    BOOLEAN NOT NULL,
    answer       TEXT    NOT NULL,
    confidence   REAL,
    correct      BOOLEAN NOT NULL,
    hallucinated BOOLEAN NOT NULL,
    PRIMARY KEY (run_id, question_id)
);
