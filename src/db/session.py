from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# En producción esto vendría de variables de entorno (Pydantic Settings)
SQLALCHEMY_DATABASE_URL = (
    "postgresql+psycopg://molt_admin:molt_secure_password@localhost:5432/molt_core"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
