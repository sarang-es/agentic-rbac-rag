from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    # 1. Name the actual table in the database
    __tablename__ = "users"

    # 2. Define the exact columns
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="user")