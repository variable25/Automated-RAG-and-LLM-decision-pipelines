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
