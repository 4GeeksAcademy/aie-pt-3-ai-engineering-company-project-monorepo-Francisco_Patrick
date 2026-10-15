"""JWT and Cryptographic security adapter.

Implements SecurityPort using python-jose and passlib/libpass bcrypt hashing.
"""

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext

from domain.auth.ports import SecurityPort
from domain.common.exceptions import AuthenticationError


class JwtSecurityAdapter(SecurityPort):
    """Concrete driven adapter implementing SecurityPort for JWT tokens and password hashing."""

    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256") -> None:
        """Initialize the adapter with secret key and cryptographic context."""
        self.secret_key = secret_key or os.environ.get("JWT_SECRET_KEY")
        if not self.secret_key:
            # Fallback to dev secret key if none provided
            self.secret_key = "trackflow-dev-secret-key-32-bytes-minimum-length"

        self.algorithm = algorithm
        self.default_expire_minutes = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, plain_password: str) -> str:
        """Compute bcrypt cryptographic hash for password."""
        return self.pwd_context.hash(plain_password)

    def get_password_hash(self, password: str) -> str:
        """Alias for hash_password."""
        return self.hash_password(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed password."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(
        self,
        subject: Union[str, Dict[str, Any]],
        expires_delta_minutes: Optional[int] = None,
        expires_delta: Optional[int] = None,
    ) -> str:
        """Generate a signed JWT access token."""
        if isinstance(subject, dict):
            to_encode = subject.copy()
            sub_val = to_encode.get("sub", "")
        else:
            to_encode = {"sub": str(subject)}
            sub_val = str(subject)

        delta = expires_delta_minutes if expires_delta_minutes is not None else expires_delta
        expire_minutes = delta if delta is not None else self.default_expire_minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)

        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def decode_access_token(self, token: str) -> str:
        """Decode and validate JWT access token, returning subject user ID."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            subject: Optional[str] = payload.get("sub")
            if subject is None:
                raise AuthenticationError("Token payload missing subject")
            return subject
        except JWTError as e:
            raise AuthenticationError("Could not validate credentials") from e


__all__ = ["JwtSecurityAdapter"]
