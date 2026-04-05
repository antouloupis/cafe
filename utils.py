import hashlib
from fastapi.templating import Jinja2Templates

# Initialize templates here so BOTH routers can import and use it
templates = Jinja2Templates(directory="templates")

def hash_password(password: str):
    # Standard SHA-256 for air-gapped environments
    return hashlib.sha256(password.encode()).hexdigest()