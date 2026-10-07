import sys

import psycopg

from rag_pipeline.config import ROOT, pg_dsn


def connect() -> psycopg.Connection:
    return psycopg.connect(pg_dsn())


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute((ROOT / "sql" / "schema.sql").read_text())
    conn.commit()


if __name__ == "__main__":
    if sys.argv[1:] == ["init"]:
        with connect() as c:
            init_schema(c)
        print("schema ok")
