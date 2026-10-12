"""Small validation helpers shared by all routes."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from flask import request


class ApiError(Exception):
    """An error that is shown to the user as JSON: {"error": message}."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def as_int(value, field, minimum=None, maximum=None):
    if value is None or value == "" or isinstance(value, bool):
        raise ApiError(f"{field} is required.")
    if isinstance(value, float) and not value.is_integer():
        raise ApiError(f"{field} must be a whole number.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a whole number.")
    if minimum is not None and number < minimum:
        raise ApiError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ApiError(f"{field} must be at most {maximum}.")
    return number


def clean_str(value, field, max_len, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(f"{field} must be text.")
    value = value.strip()
    if required and not value:
        raise ApiError(f"{field} is required.")
    if len(value) > max_len:
        raise ApiError(f"{field} must be {max_len} characters or fewer.")
    return value


def percent_to_bp(value, field):
    """'5' or '2.5' (percent) -> basis points, validated to 0-100%."""
    try:
        bp = int((Decimal(str(value)) * 100).to_integral_value(ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        raise ApiError(f"{field} must be a number.")
    if not 0 <= bp <= 10000:
        raise ApiError(f"{field} must be between 0 and 100.")
    return bp
