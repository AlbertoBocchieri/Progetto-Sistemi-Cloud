import os

from sqlalchemy import create_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://parcheggia:parcheggia@localhost:5432/parcheggia",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)