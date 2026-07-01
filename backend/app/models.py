from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class User(Base):
    # 1. Name the actual table in the database
    __tablename__ = "users"

    # 2. Define the exact columns
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")

class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    clearance_level = Column(Integer, default=1)
    uploaded_by = Column(String)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)