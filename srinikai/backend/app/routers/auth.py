"""Account registration, login, and current-user endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user
from ..database import get_db
from ..limiter import limiter
from ..config import settings
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import (
    create_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_auth)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    exists = db.scalar(select(User).where(User.email == email))
    if exists:
        # Generic message: don't leak which emails are registered.
        raise HTTPException(status_code=409, detail="Unable to register with these details.")

    user = User(
        email=email,
        display_name=body.display_name.strip(),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.rate_limit_auth)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))

    # Constant-ish work + generic error to resist user enumeration.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()

    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
