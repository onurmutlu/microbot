"""
Kimlik doğrulama ve yetkilendirme işlevleri.

Bu modül, JWT tabanlı kimlik doğrulama ve kullanıcı yetkilendirme
işlevlerini içerir.

License: MIT
Author: MicroBot Team
Version: 1.5.0
"""

from datetime import datetime, timedelta
from typing import Optional, Union, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.database import get_db
from app.config import settings
from app.models.user import User

# OAuth2 yapılandırması
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

# JWT yapılandırması
ALGORITHM = "HS256"

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    JWT erişim jetonu oluşturur.
    
    Args:
        subject: Token içinde saklanacak veri (genellikle kullanıcı ID'si)
        expires_delta: Geçerlilik süresi (yoksa varsayılan kullanılır)
        
    Returns:
        Oluşturulan JWT token
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Geçerli JWT token'ı kullanarak aktif kullanıcıyı alır.
    
    Args:
        db: Veritabanı oturumu
        token: JWT token
        
    Returns:
        Kullanıcı nesnesi
        
    Raises:
        HTTPException: Token geçersizse veya kullanıcı bulunamazsa
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz kimlik bilgileri",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgileri",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Aktif kullanıcıyı alır ve hesabın aktif olup olmadığını kontrol eder.
    
    Args:
        current_user: Mevcut kullanıcı
        
    Returns:
        Aktif kullanıcı
        
    Raises:
        HTTPException: Kullanıcı aktif değilse
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hesap aktif değil"
        )
    return current_user 