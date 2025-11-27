from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.engine import Engine
import logging
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

def safe_str(value: Any) -> str:
    """Safely convert values for string operations."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, str):
            return first
        return "" if first is None else str(first)
    if value is None:
        return ""
    return str(value)
ROOT_DIR = Path(__file__).parent

# Load .env file - try multiple locations
env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # Try parent directory
    parent_env = ROOT_DIR.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env, override=True)

DEFAULT_SQLITE_PATH = (ROOT_DIR / "local.db").resolve()
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

def _build_engine(url: str) -> Engine:
    connect_args: Dict[str, Any] = {}
    normalized_url = safe_str(url)
    if normalized_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(normalized_url, pool_pre_ping=True, connect_args=connect_args)

def _verify_connection(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

def _initialise_engine() -> Tuple[str, Engine]:
    primary_url = (os.environ.get("DATABASE_URL") or "").strip()
    fallback_url = (os.environ.get("FALLBACK_DATABASE_URL") or "").strip() or DEFAULT_SQLITE_URL

    # For PostgreSQL URLs, convert postgres:// to postgresql://
    if safe_str(primary_url).startswith("postgres://"):
        primary_url = primary_url.replace("postgres://", "postgresql://", 1)

    if primary_url:
        try:
            engine_candidate = _build_engine(primary_url)
            _verify_connection(engine_candidate)
            logger.info("✅ Successfully connected to DATABASE_URL")
            return primary_url, engine_candidate
        except (OperationalError, SQLAlchemyError) as exc:
            logger.warning(
                "⚠️  Could not connect using DATABASE_URL (%s). "
                "Falling back to %s. Original error: %s",
                primary_url,
                fallback_url,
                exc,
            )
    else:
        logger.info("📝 DATABASE_URL not set. Using fallback database at %s", fallback_url)

    engine_candidate = _build_engine(fallback_url)
    _verify_connection(engine_candidate)
    logger.info("✅ Using SQLite database at %s", fallback_url)
    return fallback_url, engine_candidate

ACTIVE_DATABASE_URL, engine = _initialise_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()