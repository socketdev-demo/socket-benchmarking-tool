"""Validation utilities for Socket Load Test.

This module provides validation functions for:
- Configuration values
- File paths and URLs
- Duration parsing
- RPS and performance parameters
- Network connectivity
"""

import re
import os
from pathlib import Path
from typing import Optional, List, Union
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_positive_int(value: int, name: str, min_value: int = 1) -> int:
    """Validate that a value is a positive integer.

    Args:
        value: Value to validate.
        name: Name of the parameter (for error messages).
        min_value: Minimum acceptable value.

    Returns:
        The validated value.

    Raises:
        ValidationError: If validation fails.
    """
    if not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer, got {type(value).__name__}")
    
    if value < min_value:
        raise ValidationError(f"{name} must be >= {min_value}, got {value}")
    
    return value


def validate_positive_float(
    value: float,
    name: str,
    min_value: float = 0.0,
    max_value: Optional[float] = None
) -> float:
    """Validate that a value is a positive float.

    Args:
        value: Value to validate.
        name: Name of the parameter (for error messages).
        min_value: Minimum acceptable value.
        max_value: Maximum acceptable value (optional).

    Returns:
        The validated value.

    Raises:
        ValidationError: If validation fails.
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"{name} must be a number, got {type(value).__name__}"
        )
    
    if value < min_value:
        raise ValidationError(f"{name} must be >= {min_value}, got {value}")
    
    if max_value is not None and value > max_value:
        raise ValidationError(f"{name} must be <= {max_value}, got {value}")
    
    return float(value)


def validate_percentage(value: Union[int, float], name: str) -> float:
    """Validate that a value is a valid percentage (0-100).

    Args:
        value: Value to validate.
        name: Name of the parameter (for error messages).

    Returns:
        The validated value as a float.

    Raises:
        ValidationError: If validation fails.
    """
    return validate_positive_float(value, name, min_value=0.0, max_value=100.0)


def parse_duration(duration: str) -> int:
    """Parse a duration string to seconds.

    Supports formats like: 30s, 5m, 2h, 1d
    
    Args:
        duration: Duration string (e.g., "5m", "30s", "2h").

    Returns:
        Duration in seconds.

    Raises:
        ValidationError: If duration format is invalid.
    """
    duration = duration.strip().lower()
    
    # Match pattern like "30s", "5m", "2h", "1d"
    match = re.match(r'^(\d+)\s*([smhd])$', duration)
    if not match:
        raise ValidationError(
            f"Invalid duration format: {duration}. "
            "Expected format: <number><unit> where unit is s/m/h/d (e.g., 5m, 30s)"
        )
    
    value, unit = match.groups()
    value = int(value)
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
    }
    
    return value * multipliers[unit]


def format_duration(seconds: int) -> str:
    """Format seconds into a human-readable duration string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string (e.g., "5m", "2h30m").
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        if remaining_seconds:
            return f"{minutes}m{remaining_seconds}s"
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        if remaining_minutes:
            return f"{hours}h{remaining_minutes}m"
        return f"{hours}h"
    else:
        days = seconds // 86400
        remaining_hours = (seconds % 86400) // 3600
        if remaining_hours:
            return f"{days}d{remaining_hours}h"
        return f"{days}d"


def validate_url(url: str, name: str, schemes: Optional[List[str]] = None) -> str:
    """Validate a URL.

    Args:
        url: URL to validate.
        name: Name of the parameter (for error messages).
        schemes: Allowed URL schemes (default: ['http', 'https']).

    Returns:
        The validated URL.

    Raises:
        ValidationError: If URL is invalid.
    """
    if not url:
        raise ValidationError(f"{name} cannot be empty")
    
    if schemes is None:
        schemes = ['http', 'https']
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL for {name}: {url} - {e}")
    
    if not parsed.scheme:
        raise ValidationError(f"{name} must include a scheme (e.g., http://): {url}")
    
    if parsed.scheme not in schemes:
        raise ValidationError(
            f"{name} scheme must be one of {schemes}, got {parsed.scheme}"
        )
    
    if not parsed.netloc:
        raise ValidationError(f"{name} must include a network location: {url}")
    
    return url


def validate_path(
    path: str,
    name: str,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    create_if_missing: bool = False,
) -> Path:
    """Validate a file system path.

    Args:
        path: Path to validate.
        name: Name of the parameter (for error messages).
        must_exist: If True, path must exist.
        must_be_file: If True, path must be a file.
        must_be_dir: If True, path must be a directory.
        create_if_missing: If True, create directory if missing.

    Returns:
        Validated Path object.

    Raises:
        ValidationError: If validation fails.
    """
    if not path:
        raise ValidationError(f"{name} cannot be empty")
    
    path_obj = Path(path).expanduser().resolve()
    
    if must_exist and not path_obj.exists():
        raise ValidationError(f"{name} does not exist: {path}")
    
    if must_be_file and path_obj.exists() and not path_obj.is_file():
        raise ValidationError(f"{name} must be a file: {path}")
    
    if must_be_dir and path_obj.exists() and not path_obj.is_dir():
        raise ValidationError(f"{name} must be a directory: {path}")
    
    if create_if_missing and must_be_dir and not path_obj.exists():
        try:
            path_obj.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValidationError(f"Failed to create directory {name}: {path} - {e}")
    
    return path_obj


def validate_port(port: int, name: str) -> int:
    """Validate a network port number.

    Args:
        port: Port number to validate.
        name: Name of the parameter (for error messages).

    Returns:
        The validated port number.

    Raises:
        ValidationError: If port is invalid.
    """
    if not isinstance(port, int):
        raise ValidationError(f"{name} must be an integer, got {type(port).__name__}")
    
    if port < 1 or port > 65535:
        raise ValidationError(f"{name} must be between 1 and 65535, got {port}")
    
    return port


def validate_hostname(hostname: str, name: str) -> str:
    """Validate a hostname or IP address.

    Args:
        hostname: Hostname to validate.
        name: Name of the parameter (for error messages).

    Returns:
        The validated hostname.

    Raises:
        ValidationError: If hostname is invalid.
    """
    if not hostname:
        raise ValidationError(f"{name} cannot be empty")
    
    hostname = hostname.strip()
    
    # Simple validation - just check it's not empty and has reasonable characters
    # More complex validation would require DNS lookup
    if not re.match(r'^[a-zA-Z0-9._-]+$', hostname):
        raise ValidationError(
            f"Invalid {name}: {hostname}. "
            "Must contain only alphanumeric characters, dots, hyphens, and underscores"
        )
    
    return hostname


def validate_rps(rps: int) -> int:
    """Validate requests per second value.

    Args:
        rps: RPS value to validate.

    Returns:
        The validated RPS value.

    Raises:
        ValidationError: If RPS is invalid.
    """
    return validate_positive_int(rps, "RPS", min_value=1)


def validate_test_id(test_id: str) -> str:
    """Validate a test ID.

    Args:
        test_id: Test ID to validate.

    Returns:
        The validated test ID.

    Raises:
        ValidationError: If test ID is invalid.
    """
    if not test_id:
        raise ValidationError("Test ID cannot be empty")
    
    test_id = test_id.strip()
    
    # Must be alphanumeric with hyphens and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', test_id):
        raise ValidationError(
            f"Invalid test ID: {test_id}. "
            "Must contain only alphanumeric characters, hyphens, and underscores"
        )
    
    return test_id


def validate_ratio_sum(
    ratios: dict,
    expected_sum: Union[int, float] = 100.0,
    tolerance: float = 0.01
) -> None:
    """Validate that a set of ratios sum to expected value.

    Args:
        ratios: Dictionary of ratio names to values.
        expected_sum: Expected sum of ratios.
        tolerance: Acceptable difference from expected sum.

    Raises:
        ValidationError: If ratios don't sum correctly.
    """
    total = sum(ratios.values())
    
    if abs(total - expected_sum) > tolerance:
        ratio_str = ", ".join(f"{k}={v}" for k, v in ratios.items())
        raise ValidationError(
            f"Ratios must sum to {expected_sum}, got {total:.2f} ({ratio_str})"
        )


def validate_non_empty_string(value: str, name: str) -> str:
    """Validate that a string is not empty.

    Args:
        value: String to validate.
        name: Name of the parameter (for error messages).

    Returns:
        The validated string (stripped).

    Raises:
        ValidationError: If string is empty.
    """
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}")
    
    value = value.strip()
    
    if not value:
        raise ValidationError(f"{name} cannot be empty")
    
    return value
