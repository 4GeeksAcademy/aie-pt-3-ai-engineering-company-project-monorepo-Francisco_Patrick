import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from domain.ports import SecurityPort
from domain.exceptions import AuthenticationError

class JwtSecurityAdapter(SecurityPort):
    def __init__(self):
        self.secret_key = os.environ.get("JWT_SECRET_KEY")
        if not self.secret_key:
            raise RuntimeError("JWT_SECRET_KEY environment variable is missing. Aborting startup.")
            
        self.algorithm = "HS256"
        # 30 minutes default
        self.default_expire_minutes = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        
        # Use bcrypt per requirements via libpass (drop-in replacement for passlib)
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, plain_password: str) -> str:
        return self.pwd_context.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, subject: str, expires_delta_minutes: Optional[int] = None) -> str:
        to_encode = {"sub": subject}
        
        expire_minutes = expires_delta_minutes if expires_delta_minutes is not None else self.default_expire_minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_access_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            subject: str = payload.get("sub")
            if subject is None:
                raise AuthenticationError("Token payload missing subject")
            return subject
        except JWTError as e:
            raise AuthenticationError("Could not validate credentials") from e
