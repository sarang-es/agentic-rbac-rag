import bcrypt

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