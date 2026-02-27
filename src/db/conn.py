import os

from dotenv import load_dotenv


def get_db_conninfo() -> str:
    load_dotenv()
    dbname = os.getenv("POSTGRES_DB", "olist_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"
