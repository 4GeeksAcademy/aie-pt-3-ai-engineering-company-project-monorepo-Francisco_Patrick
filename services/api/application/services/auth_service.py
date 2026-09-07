from typing import Optional
from domain.ports import UserRepositoryPort, SecurityPort
from domain.exceptions import AuthenticationError, UserInactiveError

class AuthService:
    def __init__(
        self,
        user_repo: UserRepositoryPort,
        security_port: SecurityPort
    ):
        self.user_repo = user_repo
        self.security_port = security_port

    def authenticate_user(self, email: str, password: str) -> str:
        """
        Validates credentials and returns a JWT access token.
        Raises AuthenticationError if invalid, or UserInactiveError if user is inactive.
        """
        user_data = self.user_repo.get_by_email(email)
        if not user_data:
            raise AuthenticationError("Invalid email or password")

        if not self.security_port.verify_password(password, user_data["hashed_password"]):
            raise AuthenticationError("Invalid email or password")

        if not user_data.get("is_active", True):
            raise UserInactiveError("User account is inactive")

        # Create token using the user's ID as the subject
        return self.security_port.create_access_token(subject=user_data["id"])
