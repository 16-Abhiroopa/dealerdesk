"""Custom exception hierarchy and DRF exception handler adhering strictly to API_CONTRACT.md.

Every error response must have the shape:
{
    "error": {
        "code": "...",
        "message": "...",
        "details": [...]
    }
}
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class DealerDeskError(APIException):
    """Base API exception for DealerDesk."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"
    default_message = "A validation error occurred."

    def __init__(self, message=None, details=None, code=None, status_code=None):
        self.message = message or self.default_message
        self.details = details if details is not None else []
        if code:
            self.error_code = code
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)


class ValidationAppError(DealerDeskError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"
    default_message = "Invalid input data."


class NotFoundAppError(DealerDeskError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"
    default_message = "Requested resource was not found."


class DuplicateAppError(DealerDeskError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE"
    default_message = "A resource with this identifier already exists."


class InsufficientStockAppError(DealerDeskError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "INSUFFICIENT_STOCK"
    default_message = "Insufficient stock available to confirm order."


class InvalidTransitionAppError(DealerDeskError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "INVALID_TRANSITION"
    default_message = "The requested status transition is not permitted."


class OrderLockedAppError(DealerDeskError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "ORDER_LOCKED"
    default_message = "Order cannot be modified because it is not in DRAFT status."


class IdempotencyConflictAppError(DealerDeskError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "IDEMPOTENCY_CONFLICT"
    default_message = "Idempotency key was previously used with a different request payload."


class SupplierUnavailableAppError(DealerDeskError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "SUPPLIER_UNAVAILABLE"
    default_message = "Could not fetch the full feed from the supplier."


def custom_exception_handler(exc, context):
    """Transform all exceptions into the contract error shape."""
    # First handle DealerDeskError instances
    if isinstance(exc, DealerDeskError):
        return Response(
            {
                "error": {
                    "code": exc.error_code,
                    "message": str(exc.message),
                    "details": exc.details if isinstance(exc.details, list) else [str(exc.details)],
                }
            },
            status=exc.status_code,
        )

    # Let standard DRF exception handler produce a response
    response = exception_handler(exc, context)

    if response is not None:
        code = "VALIDATION_ERROR"
        if response.status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
        elif response.status_code == status.HTTP_409_CONFLICT:
            code = "CONFLICT"
        elif response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            code = "METHOD_NOT_ALLOWED"
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            code = "UNAUTHORIZED"
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            code = "FORBIDDEN"
        elif response.status_code >= 500:
            code = "SERVER_ERROR"

        details = []
        message = "An error occurred."

        data = response.data
        if isinstance(data, dict):
            if "detail" in data:
                message = str(data["detail"])
            else:
                # Field errors from serializer
                for field, errs in data.items():
                    if isinstance(errs, list):
                        for err in errs:
                            details.append(f"{field}: {err}")
                    else:
                        details.append(f"{field}: {errs}")
                if details:
                    message = details[0]
        elif isinstance(data, list):
            details = [str(d) for d in data]
            if details:
                message = details[0]
        else:
            message = str(data)

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        }
        return response

    # Unhandled 500 exceptions
    logger.exception("Unhandled server exception: %s", exc)
    return Response(
        {
            "error": {
                "code": "SERVER_ERROR",
                "message": "Internal server error.",
                "details": [str(exc)],
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
