class DomainException(Exception):
    """Base class for all domain exceptions"""
    pass

class AuthenticationError(DomainException):
    """Raised when authentication fails (e.g. invalid credentials)"""
    pass

class AuthorizationError(DomainException):
    """Raised when user lacks permissions for an action"""
    pass

class ResourceNotFoundError(DomainException):
    """Raised when a requested resource is not found"""
    pass

class UserInactiveError(AuthenticationError):
    """Raised when an inactive user attempts to authenticate"""
    pass

class InvalidStatusTransitionError(DomainException):
    """Raised when an illegal incident status transition is requested"""
    pass

class IncidentNotFoundError(ResourceNotFoundError):
    """Raised when an incident is not found by ID"""
    pass

