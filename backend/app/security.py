import bcrypt
from datetime import datetime, timedelta
from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

# --- JWT Configuration ---
# 1. The Master Password used to sign the tokens (Do not share this!)
SECRET_KEY = "your-super-secret-master-key-change-this-later" 
# 2. The specific mathematical algorithm used for the signature
ALGORITHM = "HS256"
# 3. How long the VIP pass is valid before the user gets kicked out
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 1. Scramble a new password
def get_password_hash(password: str) -> str:
    # Convert string to bytes
    password_bytes = password.encode('utf-8')
    # Generate a random salt and hash the password
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # Convert back to a string for the database
    return hashed_bytes.decode('utf-8')

# 2. Check a typed password against the hash
def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    # Let bcrypt do the secure comparison
    return bcrypt.checkpw(password_bytes, hashed_bytes)

# --- JWT Minting Engine ---
def create_access_token(data: dict):
    # 1. Make a copy of the data so we don't alter the original dictionary
    to_encode = data.copy()
    
    # 2. Calculate the exact second this token should self-destruct
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # 3. Run the data, the expiration, and the SECRET_KEY through the signing algorithm
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt

# --- The Security Checkpoint ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode the wristband
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. Extract the VIP data
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None or role is None:
            raise credentials_exception
            
        # 3. Return the verified clearance data back to the route
        return {"username": username, "role": role}
        
    except JWTError:
        raise credentials_exception

# --- Role to Clearance Level Mapping ---
ROLE_LEVELS = {
    "admin": 4,
    "executive": 3,
    "hr": 3,
    "manager": 2,
    "user": 1,
    "intern": 1
}

def get_clearance_level(role: str) -> int:
    """Translates a user role string to an integer clearance level (1-4)."""
    return ROLE_LEVELS.get(role.lower(), 1)