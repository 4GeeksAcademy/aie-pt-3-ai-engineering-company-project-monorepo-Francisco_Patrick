from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class SecurityPort(ABC):
    @abstractmethod
    def hash_password(self, plain_password: str) -> str:
        pass

    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        pass

    @abstractmethod
    def create_access_token(self, subject: str, expires_delta_minutes: Optional[int] = None) -> str:
        pass

    @abstractmethod
    def decode_access_token(self, token: str) -> str:
        """Returns the subject (user ID) if valid, raises AuthenticationError if invalid"""
        pass

class UserRepositoryPort(ABC):
    @abstractmethod
    def create(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete(self, user_id: str) -> bool:
        pass

class ProfileRepositoryPort(ABC):
    @abstractmethod
    def create(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def update(self, profile_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete(self, profile_id: str) -> bool:
        pass
