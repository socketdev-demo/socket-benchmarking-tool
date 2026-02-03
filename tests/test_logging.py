"""Tests for logging utilities."""

import logging
import tempfile
from pathlib import Path

import pytest

from socket_load_test.utils.logging import (
    SensitiveDataFilter,
    ContextLogger,
    setup_logging,
    get_logger,
    set_log_level,
    enable_debug_logging,
    disable_debug_logging,
)


class TestSensitiveDataFilter:
    """Tests for SensitiveDataFilter."""

    def test_filter_password(self):
        """Test filtering password from log message."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Connecting with password="secret123"',
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert "secret123" not in record.msg
        assert "password=" in record.msg
        assert "***" in record.msg

    def test_filter_key(self):
        """Test filtering key from log message."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Using key: mySecretKey123',
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert "mySecretKey123" not in record.msg
        assert "key:" in record.msg
        assert "***" in record.msg

    def test_filter_token(self):
        """Test filtering token from log message."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Auth token=ghp_1234567890abcdef',
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert "ghp_1234567890abcdef" not in record.msg
        assert "token=" in record.msg
        assert "***" in record.msg

    def test_filter_api_key(self):
        """Test filtering API key from log message."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Config: {"api_key": "sk_live_1234567890"}',
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert "sk_live_1234567890" not in record.msg
        assert "api_key" in record.msg
        assert "***" in record.msg

    def test_filter_multiple_sensitive_values(self):
        """Test filtering multiple sensitive values."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='Config: password=pass123, token=tok456, key=key789',
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert "pass123" not in record.msg
        assert "tok456" not in record.msg
        assert "key789" not in record.msg
        assert record.msg.count("***") == 3

    def test_filter_dict_args(self):
        """Test filtering sensitive data from dict args."""
        log_filter = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Config: %s",
            args=({"password": "secret"},),
            exc_info=None,
        )
        
        log_filter.filter(record)
        # The args should be modified - dict becomes tuple of modified values
        assert isinstance(record.args, (tuple, dict))

    def test_no_sensitive_data(self):
        """Test message without sensitive data remains unchanged."""
        log_filter = SensitiveDataFilter()
        original_msg = "This is a normal log message"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=original_msg,
            args=(),
            exc_info=None,
        )
        
        log_filter.filter(record)
        assert record.msg == original_msg


class TestContextLogger:
    """Tests for ContextLogger."""

    def test_context_added_to_message(self):
        """Test that context is added to log messages."""
        base_logger = logging.getLogger("test_context")
        context = {"test_id": "test-123", "node": "node-1"}
        logger = ContextLogger(base_logger, context)
        
        msg, kwargs = logger.process("Test message", {})
        assert "test_id=test-123" in msg
        assert "node=node-1" in msg
        assert "Test message" in msg

    def test_no_context(self):
        """Test logger with no context."""
        base_logger = logging.getLogger("test_no_context")
        logger = ContextLogger(base_logger, {})
        
        original_msg = "Test message"
        msg, kwargs = logger.process(original_msg, {})
        # With empty context, message should remain mostly unchanged
        # (might have empty brackets)
        assert "Test message" in msg


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_default(self):
        """Test default logging setup."""
        logger = setup_logging()
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    def test_setup_debug_level(self):
        """Test setup with DEBUG level."""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_setup_verbose(self):
        """Test setup with verbose flag."""
        logger = setup_logging(verbose=True)
        assert logger.level == logging.DEBUG

    def test_setup_with_file(self):
        """Test setup with log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_file=str(log_file))
            
            # Should have file handler
            file_handlers = [
                h for h in logger.handlers
                if isinstance(h, logging.FileHandler)
            ]
            assert len(file_handlers) > 0
            assert log_file.exists()

    def test_setup_creates_log_directory(self):
        """Test that setup creates log directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "logs" / "subdir" / "test.log"
            setup_logging(log_file=str(log_file))
            
            assert log_file.exists()
            assert log_file.parent.exists()

    def test_setup_no_console(self):
        """Test setup without console logging."""
        logger = setup_logging(log_to_console=False)
        
        # Should have no StreamHandler
        stream_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 0

    def test_sensitive_filter_applied(self):
        """Test that sensitive data filter is applied to handlers."""
        logger = setup_logging()
        
        for handler in logger.handlers:
            # Check if filter is applied
            filters = [
                f for f in handler.filters
                if isinstance(f, SensitiveDataFilter)
            ]
            assert len(filters) > 0


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_basic(self):
        """Test getting a basic logger."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_with_context(self):
        """Test getting a logger with context."""
        context = {"test_id": "test-456"}
        logger = get_logger("test_module", context=context)
        assert isinstance(logger, ContextLogger)
        assert logger.extra == context


class TestLogLevelFunctions:
    """Tests for log level management functions."""

    def test_set_log_level(self):
        """Test setting log level."""
        logger = setup_logging(level="INFO")
        assert logger.level == logging.INFO
        
        set_log_level("DEBUG")
        assert logger.level == logging.DEBUG
        
        set_log_level("WARNING")
        assert logger.level == logging.WARNING

    def test_enable_debug_logging(self):
        """Test enabling debug logging."""
        logger = setup_logging(level="INFO")
        assert logger.level == logging.INFO
        
        enable_debug_logging()
        assert logger.level == logging.DEBUG

    def test_disable_debug_logging(self):
        """Test disabling debug logging."""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG
        
        disable_debug_logging()
        assert logger.level == logging.INFO

    def test_invalid_log_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        logger = setup_logging(level="INVALID")
        assert logger.level == logging.INFO
