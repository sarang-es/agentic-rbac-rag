import models
from pydantic import BaseModel,Field
from fastapi import FastAPI, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from security import get_password_hash, verify_password

app = FastAPI(title="Secure Agentic RAG Backend")

# Create database tables automatically if they don't exist
models.Base.metadata.create_all(bind=engine)

# Dependency to open/close DB sessions per request safely
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Models (Network Inbound Validation) ---
class UserCreate(BaseModel):
    username: str
    email: str
    password: str = Field(..., max_length=72) # This tells the Bouncer to reject huge passwords
    role: str

class UserLogin(BaseModel):
    username: str
    password: str = Field(..., max_length=72)

# --- API Routes ---

@app.get("/")
def read_root():
    return {"message": "Welcome to the Secure Agentic RAG API"}

@app.get("/api/v1/documents")
def get_secure_documents(role: str = Query(..., description="The role of the current user")):
    user_role = role.lower()
    if user_role == "admin":
        return {
            "access_granted": True,
            "data": "CONFIDENTIAL: Internal server configurations and master admin files."
        }
    elif user_role == "intern" or user_role == "user":
        return {
            "access_granted": True,
            "data": "PUBLIC: Standard corporate onboarding documentation."
        }
    else:
        raise HTTPException(status_code=403, detail="Unauthorized: Role not recognized.")

@app.get("/api/v1/users/{user_id}")
def get_user_profile(user_id: int):
    return {
        "user_id": user_id,
        "profile_name": f"Employee_{user_id}",
        "clearance_level": "Standard"
    }

@app.get("/api/v1/search")
def dynamic_search(
    search_query: str = Query(..., description="The keyword you are searching for"),
    user_clearance: str = Query(..., description="Your security clearance level")
):
    query = search_query.lower()
    clearance = user_clearance.lower()
    
    if "salary" in query:
        if clearance != "ceo":
            raise HTTPException(
                status_code=403, 
                detail="Access Denied: You do not have permission to search financial records."
            )
        else:
            return {
                "search_status": "Success",
                "results": "FOUND: Confirmed matching salary bands for fiscal year 2026 for CEO viewing access."
            }
            
    return {
        "search_status": "Success",
        "results": f"FOUND: General corporate documentation containing the term '{search_query}'."
    }

# 1. USER REGISTRATION (Write to DB with Real Hashing)
@app.post("/api/v1/users")
def register_new_user(new_user: UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists to avoid database crashes
    existing_user = db.query(models.User).filter(models.User.username == new_user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_user = models.User(
        username=new_user.username,
        email=new_user.email,
        hashed_password=get_password_hash(new_user.password),
        role=new_user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {
        "status": "Success",
        "message": "Account securely saved to database!",
        "user_id": db_user.id,
        "username": db_user.username
    }

# 2. USER LOGIN (Read from DB and Verify Hash)
@app.post("/api/v1/login")
def login_user(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()
    
    if not user:
        raise HTTPException(status_code=403, detail="Invalid credentials")
        
    is_password_correct = verify_password(user_credentials.password, user.hashed_password)
    if not is_password_correct:
        raise HTTPException(status_code=403, detail="Invalid credentials")
        
    return {
        "status": "Success",
        "message": f"Welcome back, {user.username}! Your password was verified."
    }

# 3. GET ALL USERS (Read from DB)
@app.get("/api/v1/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return {
        "total_users": len(users),
        "database_records": users
    }