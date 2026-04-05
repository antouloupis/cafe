# database.py
from sqlmodel import create_engine, Session, SQLModel

# In Docker, this file will live in your mounted volume
sqlite_url = "sqlite:////app/data/cafe.db"

# The 'engine' is the actual connection pipe
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def init_db():
    # This magic line looks at models.py and creates the tables if they are missing
    SQLModel.metadata.create_all(engine)

def get_session():
    # This gives FastAPI a temporary 'Session' to save or read data
    with Session(engine) as session:
        yield session
        