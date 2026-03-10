import os

from dotenv import load_dotenv


def get_db_conninfo() -> str:
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    dbname = os.getenv("POSTGRES_DB", "olist_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")

    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def get_sqlalchemy_url() -> str:
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    dbname = os.getenv("POSTGRES_DB", "olist_db")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")

    return f"postgresql+pg8000://{user}:{password}@{host}:{port}/{dbname}"
