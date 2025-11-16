from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
# from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
import os


def build_engine() -> Engine:
    """
    Create a SQLAlchemy engine based on environment variables declared in `.env`.

    Expected variables:
        user=<database username>
        password=<database password>
        host=<database host>
        port=<database port>
        dbname=<database name>
    """
    load_dotenv()

    user = os.getenv("user")
    password = os.getenv("password")
    host = os.getenv("host")
    port = os.getenv("port")
    dbname = os.getenv("dbname")

    if not all([user, password, host, port, dbname]):
        missing = [name for name, value in {
            "user": user,
            "password": password,
            "host": host,
            "port": port,
            "dbname": dbname,
        }.items() if not value]
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    database_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}?sslmode=require"
    engine: Engine = create_engine(database_url)
    # To disable SQLAlchemy’s client-side pooling uncomment:
    # engine = create_engine(database_url, poolclass=NullPool)
    return engine


if __name__ == "__main__":
    try:
        engine = build_engine()
        with engine.connect() as connection:
            print("Connection successful!")
    except Exception as exc:
        print(f"Failed to connect: {exc}")

