"""Logging utilities for Socket Load Test.

This module provides centralized logging configuration with support for:
- Console and file output
- Configurable log levels
- Sensitive data filtering (passwords, keys, tokens)
- Structured logging with contextual information
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any


# Sensitive patterns to filter from logs
SENSITIVE_PATTERNS = [
    # Password patterns
    (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    # API keys
    (re.compile(r'(key["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    # Tokens
    (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(npm[_-]?token["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(pypi[_-]?token["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    # Secrets
    (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    # Generic auth values
    (re.compile(r'(auth["\']?\s*[:=]\s*["\']?)([^"\'}\s,]+)', re.IGNORECASE), r'\1***'),
    # Authorization headers (Bearer, Basic)
    (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?Bearer\s+)([^\s"\'}\],]+)', re.IGNORECASE), r'\1***'),
    (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?Basic\s+)([^\s"\'}\],]+)', re.IGNORECASE), r'\1***'),
    # Command line arguments with tokens/passwords
    (re.compile(r'(--[a-z-]*(?:token|password|key|secret)[=\s]+)([^\s]+)', re.IGNORECASE), r'\1***'),
]


class SensitiveDataFilter(logging.Filter):
    """Filter to remove sensitive data from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter sensitive data from log message.

        Args:
            record: Log record to filter.

        Returns:
            Always True (we modify but don't exclude records).
        """
        if isinstance(record.msg, str):
            record.msg = self._filter_sensitive_data(record.msg)
        
        # Also filter args if present
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._filter_sensitive_data(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    self._filter_sensitive_data(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True

    @staticmethod
    def _filter_sensitive_data(text: str) -> str:
        """Remove sensitive data from text.

        Args:
            text: Text to filter.

        Returns:
            Filtered text with sensitive data replaced.
        """
        for pattern, replacement in SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds contextual information to log messages."""

    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """Initialize context logger.

        Args:
            logger: Base logger instance.
            extra: Extra context to add to all log messages.
        """
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message to add context.

        Args:
            msg: Log message.
            kwargs: Additional keyword arguments.

        Returns:
            Tuple of (modified message, modified kwargs).
        """
        # Add context prefix if available
        if self.extra:
            context_parts = [f"{k}={v}" for k, v in self.extra.items()]
            msg = f"[{' '.join(context_parts)}] {msg}"
        return msg, kwargs


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False,
    log_to_console: bool = True,
) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional file path for log output.
        verbose: If True, set level to DEBUG.
        log_to_console: If True, log to console.

    Returns:
        Configured root logger.
    """
    # Determine log level
    if verbose:
        level = "DEBUG"
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Add console handler if requested
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """Get a logger instance with optional context.

    Args:
        name: Logger name (typically __name__).
        context: Optional context dictionary to add to all log messages.

    Returns:
        Logger instance (ContextLogger if context provided, else standard Logger).
    """
    logger = logging.getLogger(name)
    
    if context:
        return ContextLogger(logger, context)
    
    return logger


def set_log_level(level: str) -> None:
    """Set the log level for all handlers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(log_level)


def enable_debug_logging() -> None:
    """Enable debug logging."""
    set_log_level("DEBUG")


def disable_debug_logging() -> None:
    """Disable debug logging (set to INFO)."""
    set_log_level("INFO")


def mask_sensitive_value(value: str, show_chars: int = 4) -> str:
    """Mask a sensitive value for safe display.
    
    Args:
        value: The sensitive value to mask.
        show_chars: Number of characters to show at the end (default: 4).
    
    Returns:
        Masked value showing only last few characters.
    
    Example:
        >>> mask_sensitive_value("my-secret-token-12345")
        "***2345"
        >>> mask_sensitive_value("short")
        "***"
    """
    if not value:
        return ""
    
    if len(value) <= show_chars:
        return "***"
    
    return f"***{value[-show_chars:]}"


def mask_auth_header(header_value: str) -> str:
    """Mask an Authorization header value for safe display.
    
    Args:
        header_value: The Authorization header value (e.g., "Bearer token123" or "Basic base64string").
    
    Returns:
        Masked header value.
    
    Example:
        >>> mask_auth_header("Bearer my-secret-token")
        "Bearer ***en"
        >>> mask_auth_header("Basic dXNlcjpwYXNz")
        "Basic ***ss"
    """
    if not header_value:
        return ""
    
    parts = header_value.split(None, 1)
    if len(parts) == 2:
        auth_type, token = parts
        return f"{auth_type} {mask_sensitive_value(token)}"
    
    return mask_sensitive_value(header_value)
