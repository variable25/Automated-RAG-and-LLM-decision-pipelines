import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

SAMPLE_SIZE = int(os.getenv("SAMPLE_SIZE", "1000"))
SEED = 42


def pg_dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'rag')} "
        f"user={os.getenv('POSTGRES_USER', 'rag')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'rag')}"
    )
