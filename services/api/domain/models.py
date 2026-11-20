from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime
from domain.incident_model import Incident


from domain.suppliers.models import (
    Supplier,
    SupplierStatus,
    VALID_CATEGORIES,
    VALID_STATUSES,
)

SupplierBase = Supplier
SupplierCreate = Supplier


class ProfileBase(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class Profile(ProfileBase):
    id: str
    user_id: str

class UserBase(BaseModel):
    email: str # Use standard str to avoid extra dependency on email-validator if not installed, or we can use EmailStr if email-validator is present. We will use str and regex.
    is_active: bool = True
    role: Literal["admin", "manager", "user"] = "user"

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    profile: Optional[ProfileBase] = None

class User(UserBase):
    id: str
    hashed_password: str
    created_at: str

class UserResponse(UserBase):
    id: str
    created_at: str

class MessageResponse(BaseModel):
    message: str
