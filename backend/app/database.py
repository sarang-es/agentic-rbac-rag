import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get the directory where database.py is located (backend/app/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "secure_app.db")

# 1. The Database URL (Where the file will be saved)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# 2. The Engine (The physical pipeline to the database)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} # Required specifically for SQLite in FastAPI
)

# 3. The SessionLocal (The temporary workspace for reading/writing)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. The Base (The master blueprint that your tables will inherit from)
Base = declarative_base()