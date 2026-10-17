"""Global domain-to-HTTP exception handlers for FastAPI.

Maps pure domain exception hierarchies and validation errors to standardized,
sanitized HTTP error payloads (ErrorResponsePayload) ensuring zero stack trace leaks
and consistent client responses across all backend endpoints.
"""

from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from domain.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    DomainException,
    DuplicateEntityError,
    EntityNotFoundError,
    ErrorResponsePayload,
    IncidentNotFoundError,
    InsufficientStockError,
    InvalidStatusTransitionError,
    ResourceNotFoundError,
    UserInactiveError,
    ValidationErrorDetail,
)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Format Pydantic request validation failures into standardized payloads without stack traces."""
    errors: List[Dict[str, str]] = []
    for err in exc.errors():
        locs = [str(loc) for loc in err.get("loc", []) if str(loc) != "body"]
        field_name = " -> ".join(locs) if locs else "payload"
        errors.append({"field": field_name, "issue": err.get("msg", "Invalid value")})

    primary_msg = (
        f"Validation failed for field '{errors[0]['field']}': {errors[0]['issue']}"
        if errors
        else "Validation failed"
    )

    payload = ErrorResponsePayload(
        error="Validation Error",
        message=primary_msg,
        details=[ValidationErrorDetail(**e) for e in errors],
    )
    status_code = (
        status.HTTP_422_UNPROCESSABLE_CONTENT
        if "/telemetry" in request.url.path
        else status.HTTP_400_BAD_REQUEST
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )


async def http_exception_handler(
    request: Request, exc: HTTPException
) -> JSONResponse:
    """Format FastAPI HTTP exceptions into standardized payloads."""
    detail_str = str(exc.detail) if exc.detail else "HTTP Error"
    payload = ErrorResponsePayload(
        error="HTTP Error",
        message=detail_str,
        detail=detail_str,
    )
    headers = exc.headers if exc.headers else None
    return JSONResponse(
        status_code=exc.status_code,
        content=payload.model_dump(),
        headers=headers,
    )


async def resource_not_found_handler(
    request: Request, exc: ResourceNotFoundError
) -> JSONResponse:
    """Map domain EntityNotFoundError / ResourceNotFoundError to HTTP 404 Not Found."""
    payload = ErrorResponsePayload(
        error="Not Found",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=payload.model_dump(),
    )


async def invalid_status_transition_handler(
    request: Request, exc: InvalidStatusTransitionError
) -> JSONResponse:
    """Map domain InvalidStatusTransitionError to HTTP 400 Bad Request."""
    payload = ErrorResponsePayload(
        error="Invalid Status Transition",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


async def insufficient_stock_handler(
    request: Request, exc: InsufficientStockError
) -> JSONResponse:
    """Map domain InsufficientStockError to HTTP 400 Bad Request."""
    payload = ErrorResponsePayload(
        error="Insufficient Stock",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


async def duplicate_entity_handler(
    request: Request, exc: DuplicateEntityError
) -> JSONResponse:
    """Map domain DuplicateEntityError to HTTP 409 Conflict."""
    payload = ErrorResponsePayload(
        error="Conflict",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=payload.model_dump(),
    )


async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    """Map domain AuthenticationError to HTTP 401 Unauthorized."""
    payload = ErrorResponsePayload(
        error="Unauthorized",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=payload.model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def authorization_error_handler(
    request: Request, exc: AuthorizationError
) -> JSONResponse:
    """Map domain AuthorizationError / UserInactiveError to HTTP 403 Forbidden."""
    payload = ErrorResponsePayload(
        error="Forbidden",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=payload.model_dump(),
    )


async def business_rule_violation_handler(
    request: Request, exc: BusinessRuleViolationError
) -> JSONResponse:
    """Map generic domain BusinessRuleViolationError to HTTP 400 Bad Request."""
    payload = ErrorResponsePayload(
        error="Business Rule Violation",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    """Fallback handler mapping any uncaught DomainException to HTTP 400 Bad Request."""
    payload = ErrorResponsePayload(
        error="Domain Error",
        message=exc.message,
        detail=exc.message,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=payload.model_dump(),
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Sanitized 500 handler ensuring zero raw stack traces or internal leaks are exposed."""
    payload = ErrorResponsePayload(
        error="Server Error",
        message="An unexpected error occurred. Please try again or contact support.",
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=payload.model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain-to-HTTP exception handlers onto a FastAPI application instance."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidStatusTransitionError, invalid_status_transition_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IncidentNotFoundError, resource_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(EntityNotFoundError, resource_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(InsufficientStockError, insufficient_stock_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DuplicateEntityError, duplicate_entity_handler)  # type: ignore[arg-type]
    app.add_exception_handler(UserInactiveError, authorization_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AuthenticationError, authentication_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AuthorizationError, authorization_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DomainException, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]


__all__ = [
    "authentication_error_handler",
    "authorization_error_handler",
    "business_rule_violation_handler",
    "domain_exception_handler",
    "duplicate_entity_handler",
    "generic_exception_handler",
    "http_exception_handler",
    "insufficient_stock_handler",
    "invalid_status_transition_handler",
    "register_exception_handlers",
    "resource_not_found_handler",
    "validation_exception_handler",
]
