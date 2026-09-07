from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    categories: List[str] = Field(..., min_length=1)
    cost_per_kg: float = Field(..., gt=0, description="Cost per kg must be strictly positive")
    status: Literal["active", "suspended"] = Field(...)

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdateRate(BaseModel):
    cost_per_kg: float = Field(..., gt=0)

class SupplierUpdateStatus(BaseModel):
    status: Literal["active", "suspended"] = Field(...)

class Supplier(SupplierBase):
    id: int
    updated_at: str

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
