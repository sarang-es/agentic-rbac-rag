from . import models
from pydantic import BaseModel,Field
from fastapi import FastAPI, HTTPException, Query, Depends, File, UploadFile, Form
from sqlalchemy.orm import Session
from .database import SessionLocal, engine
from .security import get_password_hash, verify_password, create_access_token, get_current_user, get_clearance_level
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import os
import io
import pypdf
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DIR = os.path.join(BACKEND_DIR, "chroma_db")

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

app = FastAPI(title="Secure Agentic RAG Backend")

# --- NEW AI INITIALIZATION ---
embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embedding_function)
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)

# Create database tables automatically if they don't exist
models.Base.metadata.create_all(bind=engine)

# Dependency to open/close DB sessions per request safely
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:        
        db.close()
        
#checking whether the user is admin        
def require_admin(current_user: dict):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

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

# 4. GET SECURE DOCUMENTS (Hierarchical RBAC metadata list)
@app.get("/api/v1/documents")
def get_secure_documents(current_user: dict = Depends(get_current_user), db_session: Session = Depends(get_db)):
    user_role = current_user["role"]
    user_level = get_clearance_level(user_role)
    
    # Query database for all documents with clearance_level <= user_level
    docs = db_session.query(models.UploadedDocument).filter(models.UploadedDocument.clearance_level <= user_level).all()
    
    return {
        "access_granted": True,
        "user": current_user["username"],
        "clearance_level": user_level,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "clearance_level": doc.clearance_level,
                "uploaded_by": doc.uploaded_by,
                "uploaded_at": doc.uploaded_at
            }
            for doc in docs
        ]
    }
    
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


# 2. USER LOGIN (Read from DB, Verify Hash, and Mint Token)
@app.post("/api/v1/login")
def login_user(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. Fetch user from the database
    user = db.query(models.User).filter(models.User.username == user_credentials.username).first()
    
    # 2. Check if user exists and password math checks out (Combined for security)
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Mint the JWT VIP Wristband
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    # 4. Return the standard OAuth2 JSON response
    return {"access_token": access_token, "token_type": "bearer"}

# 3. GET ALL USERS (Read from DB)
@app.get("/api/v1/users")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return {
        "total_users": len(users),
        "database_records": users
    }
    
# --- DOCUMENT UPLOAD & PARSING ROUTE ---

@app.post("/api/v1/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    clearance_level: int = Form(1),
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    # Validate clearance level range
    if clearance_level < 1 or clearance_level > 4:
        raise HTTPException(status_code=400, detail="Invalid clearance level. Must be between 1 and 4.")
    
    # Check if uploader has sufficient clearance to assign this level
    uploader_role = current_user["role"]
    uploader_level = get_clearance_level(uploader_role)
    if uploader_level < clearance_level:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot upload a document with a clearance level higher than your own."
        )
    
    # Read the file contents
    file_bytes = await file.read()
    filename = file.filename
    
    # Extract text content
    text_content = ""
    if filename.endswith(".pdf"):
        try:
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content += text + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {str(e)}")
    elif filename.endswith((".txt", ".md")):
        try:
            text_content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_content = file_bytes.decode("latin-1")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decode text file: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Only .txt, .md, and .pdf files are supported.")
    
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Document contains no text content.")
    
    # Save the file to disk in the backend/uploads directory
    upload_dir = os.path.join(BACKEND_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_text(text_content)
    
    # Create Langchain documents with metadata
    langchain_docs = [
        Document(
            page_content=chunk,
            metadata={"clearance_level": clearance_level, "source": filename}
        )
        for chunk in chunks
    ]
    
    # Add to ChromaDB
    db.add_documents(langchain_docs)
    
    # Save metadata to SQLite Database
    db_doc = models.UploadedDocument(
        filename=filename,
        clearance_level=clearance_level,
        uploaded_by=current_user["username"]
    )
    db_session.add(db_doc)
    db_session.commit()
    db_session.refresh(db_doc)
    
    return {
        "status": "Success",
        "message": f"Document '{filename}' uploaded and indexed successfully!",
        "document_id": db_doc.id,
        "clearance_level": db_doc.clearance_level,
        "chunks_indexed": len(chunks)
    }

# --- NEW CHAT ROUTE ---
class ChatRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat_with_ai(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    try:
        user_role = current_user["role"]
        user_level = get_clearance_level(user_role)
        
        # Search the database for matching chunks filtered by user clearance level
        docs = db.similarity_search(
            request.query,
            k=8,
            filter={"clearance_level": {"$lte": user_level}}
        )
        
        # TEMP DEBUG — remove after checking
        print(f"\n=== Retrieved {len(docs)} chunks for query: '{request.query}' ===")
        for i, d in enumerate(docs):
            print(f"--- Chunk {i+1} | source: {d.metadata.get('source')} | clearance: {d.metadata.get('clearance_level')} ---")
            print(d.page_content)
            print()
        
        context_parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "Unknown source")
            context_parts.append(f"[Chunk {i+1} from {source}]:\n{doc.page_content}")
            
        context = "\n\n".join(context_parts) if context_parts else "No relevant context found."

        system_prompt = (
            "You are a secure assistant. Answer the user's question using ONLY the provided context below. "
            "If the answer cannot be found in the context, say 'I do not know'.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {request.query}\n\n"
            "Answer:"
        )

        response = llm.invoke(system_prompt)
        return {
            "query": request.query,
            "answer": response.content,
            "user": current_user["username"],
            "clearance_level": user_level
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.delete("/api/v1/documents")
def delete_all_documents(
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    require_admin(current_user)
    
    # Delete all vectors from ChromaDB
    all_data = db._collection.get()
    all_ids = all_data.get("ids", [])
    if all_ids:
        db._collection.delete(ids=all_ids)
    
    # Delete all rows from SQLite
    deleted_count = db_session.query(models.UploadedDocument).delete()
    db_session.commit()
    
    return {
        "status": "Success",
        "message": "All documents deleted from vector store and database.",
        "sql_rows_deleted": deleted_count,
        "chroma_chunks_deleted": len(all_ids)
    }
    
    
@app.delete("/api/v1/documents/{document_id}")
def delete_one_document(
    document_id: int,
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    require_admin(current_user)
    
    # Find the document in SQLite first, to get its filename
    doc = db_session.query(models.UploadedDocument).filter(
        models.UploadedDocument.id == document_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    filename = doc.filename
    
    # Delete matching chunks from ChromaDB (matched by "source" metadata)
    matches = db._collection.get(where={"source": filename})
    match_ids = matches.get("ids", [])
    if match_ids:
        db._collection.delete(ids=match_ids)
    
    # Delete the row from SQLite
    db_session.delete(doc)
    db_session.commit()
    
    return {
        "status": "Success",
        "message": f"Document '{filename}' (id={document_id}) deleted from both stores.",
        "chroma_chunks_deleted": len(match_ids)
    }
    
@app.delete("/api/v1/users")
def delete_all_users(
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    require_admin(current_user)
    
    deleted_count = db_session.query(models.User).delete()
    db_session.commit()
    
    return {
        "status": "Success",
        "message": "All users deleted.",
        "users_deleted": deleted_count
    }

@app.delete("/api/v1/users/{user_id}")
def delete_one_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db_session: Session = Depends(get_db)
):
    require_admin(current_user)
    
    user = db_session.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    db_session.delete(user)
    db_session.commit()
    
    return {
        "status": "Success",
        "message": f"User '{user.username}' (id={user_id}) deleted."
    }
    
    
# remove after testing 
@app.get("/debug/chunks/{filename}")
def debug_chunks(filename: str):
    results = db._collection.get(where={"source": filename})
    chunks = results.get("documents", [])
    return {
        "filename": filename,
        "total_chunks": len(chunks),
        "chunks": chunks
    }