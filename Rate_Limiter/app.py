import time
from fastapi import Request, HTTPException, FastAPI, status
from pydantic import BaseModel

app = FastAPI()

stored_user = {"id": "1", "username": "Brog205", "password": "bebo56179011"}

requests = {}

def is_allowed(user_ip: str) -> bool:
    current_time = time.time()
    
    if user_ip not in requests:
        requests[user_ip] = {"count": 1, "reset_time": current_time + 60}
        return True
    
    user_data = requests[user_ip]
    
    if current_time > user_data["reset_time"]:
        requests[user_ip] = {"count": 1, "reset_time": current_time + 60}
        return True
    
    if user_data["count"] < 5: 
        user_data["count"] += 1
        return True
    
    return False 

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(request: Request, data_login: LoginRequest):
    client_ip = request.client.host if request.client else "unknown"
    
    if not is_allowed(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Too many requests. Please try again later."
        )

    if data_login.username != stored_user["username"] or data_login.password != stored_user["password"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Something is wrong in username or password"
        )
    
    return {
        "Message": "Successfully login",
        "username": data_login.username
    }