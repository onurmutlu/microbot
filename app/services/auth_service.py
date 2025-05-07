from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.database import get_db
from app.models import User
from app.config import settings

# OAuth2 şeması oluşturulurken auto_error=False ayarı ile token yoksa hata vermemesini sağlıyoruz
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False
        if not AuthService.verify_password(password, user.password_hash):
            return False
        return user

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
        return encoded_jwt

    @staticmethod
    def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        return user

    @staticmethod
    def get_current_active_user(current_user: User = Depends(get_current_user)):
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Pasif kullanıcı")
        return current_user

# Keep original functions for backward compatibility
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Pasif kullanıcı")
    return current_user

def get_current_user_optional(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme_optional)):
    """
    Kullanıcı kimlik doğrulamasını opsiyonel yapar.
    Token geçerli değilse None döndürür.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except JWTError:
        return None
    except Exception:
        return None
