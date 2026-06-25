from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import config

database_url = config.DATABASE_URL
if database_url.startswith("postgres://"):
    # Render (and Heroku) hand out "postgres://", but SQLAlchemy 2.x
    # requires the "postgresql://" scheme.
    database_url = database_url.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
