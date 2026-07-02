"""Local auth: first registered user bootstraps the app."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import create_token, current_user, hash_password, verify_password
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {"needs_setup": db.query(User).count() == 0}


@router.post("/register", status_code=201)
def register(creds: Credentials, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == creds.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    if len(creds.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    user = User(email=creds.email.lower(), name=creds.name or creds.email,
                password_hash=hash_password(creds.password))
    db.add(user)
    db.flush()
    log(db, user.email, "create", "users", user.id)
    db.commit()
    return {"token": create_token(user.id), "name": user.name, "email": user.email}


@router.post("/login")
def login(creds: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email.lower()).first()
    if user is None or not verify_password(creds.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    log(db, user.email, "login", "users", user.id)
    db.commit()
    return {"token": create_token(user.id), "name": user.name, "email": user.email}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}
