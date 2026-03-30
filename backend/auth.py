import jwt
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from backend.db import SessionLocal
from backend.models import User
from backend.otp import generate_otp, verify_otp, send_email_otp

router = APIRouter()

SECRET_KEY = "super-secret-finance-tracker-key"
ALGORITHM = "HS256"
# ✨ FIXED 1: Unique cookie name so localhost doesn't mix up old projects
COOKIE_NAME = "smartspend_session" 

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    bot_tel_id = request.query_params.get("telegram_id")
    if bot_tel_id:
        user = db.query(User).filter(User.telegram_id == str(bot_tel_id)).first()
        if user:
            return user
    
    token = request.cookies.get("smartspend_session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # ✨ FIXED 2: Ensure user_id is treated as an integer when querying DB
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

@router.post("/request-otp")
def request_otp(email: str = Form(...)):
    otp = generate_otp(email)
    send_email_otp(email, otp)
    return {"message": "OTP sent"}

@router.post("/verify-otp")
def verify(email: str = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    if not verify_otp(email, otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    # ✨ FIXED 3: Timezone-aware expiration 
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    
    # ✨ FIXED 4: JWT standards expect the "sub" (subject) to be a string
    token = jwt.encode({"sub": str(user.id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    
    # ✨ FIXED 5: Just in case your PyJWT version returns bytes, force it to a string
    if isinstance(token, bytes):
        token = token.decode("utf-8")

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, max_age=7*24*3600)
    return response

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response