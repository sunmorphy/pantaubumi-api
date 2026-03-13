"""
Standardised API response envelope.

Every endpoint returns:
    {
        "code":    <HTTP status int>,
        "status":  <human label>,
        "message": <optional string or null>,
        "data":    <payload or null>
    }
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


# HTTP status → human label
_STATUS_LABELS = {
    200: "Success",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
}


class APIResponse(BaseModel, Generic[T]):
    code: int
    status: str
    message: Optional[str] = None
    data: Optional[T] = None


def ok(data: Any = None, message: Optional[str] = None, code: int = 200) -> dict:
    """Return a successful envelope dict (200 / 201)."""
    return {
        "code": code,
        "status": _STATUS_LABELS.get(code, "Success"),
        "message": message,
        "data": data,
    }


def error(code: int, message: str) -> dict:
    """Return an error envelope dict."""
    return {
        "code": code,
        "status": _STATUS_LABELS.get(code, "Error"),
        "message": message,
        "data": None,
    }
