"""Supplier domain models and value objects.

Pure business entities for TrackFlow suppliers domain with zero framework or database dependencies.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Supplier(BaseModel):
    """Pure domain entity representing a freight or logistics supplier."""

    id: Optional[int] = Field(default=None, description="Unique numeric supplier identifier")
    name: str = Field(..., min_length=1, description="Supplier company name")
    country: str = Field(..., min_length=1, description="Country of origin")
    category: Optional[str] = Field(default=None, description="Primary supplier category")
    categories: Optional[List[str]] = Field(default=None, description="List of operational categories")
    cost_per_kg: float = Field(..., gt=0.0, description="Freight shipping cost per kg (must be > 0.0)")
    status: Literal["active", "suspended"] = Field(default="active", description="Operational status")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp of creation")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp of last modification")

    @model_validator(mode="after")
    def synchronize_categories(self) -> "Supplier":
        """Synchronizes category and categories fields for bidirectional compatibility."""
        if self.categories and not self.category:
            self.category = self.categories[0] if self.categories else None
        elif self.category and not self.categories:
            self.categories = [self.category]
        return self


__all__ = ["Supplier"]
