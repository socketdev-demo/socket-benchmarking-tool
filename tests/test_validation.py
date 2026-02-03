"""Tests for validation utilities."""

import tempfile
from pathlib import Path

import pytest

from socket_load_test.utils.validation import (
    ValidationError,
    validate_positive_int,
    validate_positive_float,
    validate_percentage,
    parse_duration,
    format_duration,
    validate_url,
    validate_path,
    validate_port,
    validate_hostname,
    validate_rps,
    validate_test_id,
    validate_ratio_sum,
    validate_non_empty_string,
)


class TestValidatePositiveInt:
    """Tests for validate_positive_int."""

    def test_valid_positive_int(self):
        """Test with valid positive integer."""
        assert validate_positive_int(10, "test_value") == 10
        assert validate_positive_int(1, "test_value") == 1
        assert validate_positive_int(1000, "test_value") == 1000

    def test_with_custom_min_value(self):
        """Test with custom minimum value."""
        assert validate_positive_int(10, "test_value", min_value=5) == 10
        
        with pytest.raises(ValidationError, match="must be >= 10"):
            validate_positive_int(5, "test_value", min_value=10)

    def test_zero_fails(self):
        """Test that zero fails validation."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            validate_positive_int(0, "test_value")

    def test_negative_fails(self):
        """Test that negative values fail."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            validate_positive_int(-5, "test_value")

    def test_non_integer_fails(self):
        """Test that non-integer values fail."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_positive_int(10.5, "test_value")
        
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_positive_int("10", "test_value")


class TestValidatePositiveFloat:
    """Tests for validate_positive_float."""

    def test_valid_positive_float(self):
        """Test with valid positive float."""
        assert validate_positive_float(10.5, "test_value") == 10.5
        assert validate_positive_float(0.1, "test_value") == 0.1
        assert validate_positive_float(1000.99, "test_value") == 1000.99

    def test_accepts_int(self):
        """Test that integers are accepted and converted to float."""
        assert validate_positive_float(10, "test_value") == 10.0

    def test_with_min_and_max(self):
        """Test with min and max values."""
        assert validate_positive_float(50, "test", min_value=0, max_value=100) == 50.0
        
        with pytest.raises(ValidationError, match="must be >= 10"):
            validate_positive_float(5, "test", min_value=10)
        
        with pytest.raises(ValidationError, match="must be <= 100"):
            validate_positive_float(150, "test", max_value=100)

    def test_non_number_fails(self):
        """Test that non-numeric values fail."""
        with pytest.raises(ValidationError, match="must be a number"):
            validate_positive_float("10.5", "test_value")


class TestValidatePercentage:
    """Tests for validate_percentage."""

    def test_valid_percentage(self):
        """Test with valid percentage values."""
        assert validate_percentage(0, "test") == 0.0
        assert validate_percentage(50, "test") == 50.0
        assert validate_percentage(100, "test") == 100.0
        assert validate_percentage(33.33, "test") == 33.33

    def test_below_zero_fails(self):
        """Test that negative percentages fail."""
        with pytest.raises(ValidationError, match="must be >= 0"):
            validate_percentage(-1, "test")

    def test_above_100_fails(self):
        """Test that percentages > 100 fail."""
        with pytest.raises(ValidationError, match="must be <= 100"):
            validate_percentage(101, "test")


class TestParseDuration:
    """Tests for parse_duration."""

    def test_parse_seconds(self):
        """Test parsing seconds."""
        assert parse_duration("30s") == 30
        assert parse_duration("1s") == 1
        assert parse_duration("90s") == 90

    def test_parse_minutes(self):
        """Test parsing minutes."""
        assert parse_duration("5m") == 300
        assert parse_duration("1m") == 60
        assert parse_duration("30m") == 1800

    def test_parse_hours(self):
        """Test parsing hours."""
        assert parse_duration("2h") == 7200
        assert parse_duration("1h") == 3600

    def test_parse_days(self):
        """Test parsing days."""
        assert parse_duration("1d") == 86400
        assert parse_duration("2d") == 172800

    def test_whitespace_handling(self):
        """Test that whitespace is handled."""
        assert parse_duration(" 5m ") == 300
        assert parse_duration("5 m") == 300

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert parse_duration("5M") == 300
        assert parse_duration("2H") == 7200

    def test_invalid_format_fails(self):
        """Test that invalid formats fail."""
        with pytest.raises(ValidationError, match="Invalid duration format"):
            parse_duration("5")
        
        with pytest.raises(ValidationError, match="Invalid duration format"):
            parse_duration("5x")
        
        with pytest.raises(ValidationError, match="Invalid duration format"):
            parse_duration("abc")


class TestFormatDuration:
    """Tests for format_duration."""

    def test_format_seconds(self):
        """Test formatting seconds."""
        assert format_duration(30) == "30s"
        assert format_duration(45) == "45s"

    def test_format_minutes(self):
        """Test formatting minutes."""
        assert format_duration(60) == "1m"
        assert format_duration(300) == "5m"
        assert format_duration(90) == "1m30s"

    def test_format_hours(self):
        """Test formatting hours."""
        assert format_duration(3600) == "1h"
        assert format_duration(7200) == "2h"
        assert format_duration(5400) == "1h30m"

    def test_format_days(self):
        """Test formatting days."""
        assert format_duration(86400) == "1d"
        assert format_duration(90000) == "1d1h"


class TestValidateUrl:
    """Tests for validate_url."""

    def test_valid_http_url(self):
        """Test with valid HTTP URL."""
        url = "http://example.com"
        assert validate_url(url, "test_url") == url

    def test_valid_https_url(self):
        """Test with valid HTTPS URL."""
        url = "https://example.com:8080/path"
        assert validate_url(url, "test_url") == url

    def test_custom_schemes(self):
        """Test with custom allowed schemes."""
        url = "ftp://example.com"
        assert validate_url(url, "test_url", schemes=["ftp"]) == url
        
        with pytest.raises(ValidationError, match="scheme must be one of"):
            validate_url(url, "test_url", schemes=["http", "https"])

    def test_missing_scheme_fails(self):
        """Test that URL without scheme fails."""
        with pytest.raises(ValidationError, match="must include a scheme"):
            validate_url("example.com", "test_url")

    def test_missing_netloc_fails(self):
        """Test that URL without network location fails."""
        with pytest.raises(ValidationError, match="must include a network location"):
            validate_url("http://", "test_url")

    def test_empty_url_fails(self):
        """Test that empty URL fails."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_url("", "test_url")


class TestValidatePath:
    """Tests for validate_path."""

    def test_valid_path(self):
        """Test with valid path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            path.touch()
            
            result = validate_path(str(path), "test_path", must_exist=True)
            # Use samefile() to handle macOS /private symlink
            assert result.samefile(path)

    def test_must_exist_fails_when_missing(self):
        """Test that must_exist fails for non-existent path."""
        with pytest.raises(ValidationError, match="does not exist"):
            validate_path("/non/existent/path", "test_path", must_exist=True)

    def test_must_be_file(self):
        """Test must_be_file validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "file.txt"
            file_path.touch()
            dir_path = Path(tmpdir) / "subdir"
            dir_path.mkdir()
            
            # File should pass
            validate_path(str(file_path), "test", must_be_file=True)
            
            # Directory should fail
            with pytest.raises(ValidationError, match="must be a file"):
                validate_path(str(dir_path), "test", must_be_file=True)

    def test_must_be_dir(self):
        """Test must_be_dir validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "file.txt"
            file_path.touch()
            dir_path = Path(tmpdir) / "subdir"
            dir_path.mkdir()
            
            # Directory should pass
            validate_path(str(dir_path), "test", must_be_dir=True)
            
            # File should fail
            with pytest.raises(ValidationError, match="must be a directory"):
                validate_path(str(file_path), "test", must_be_dir=True)

    def test_create_if_missing(self):
        """Test creating directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "nested" / "dir"
            
            result = validate_path(
                str(new_dir),
                "test",
                must_be_dir=True,
                create_if_missing=True
            )
            
            assert result.exists()
            assert result.is_dir()

    def test_empty_path_fails(self):
        """Test that empty path fails."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_path("", "test_path")

    def test_expands_user_path(self):
        """Test that ~ is expanded."""
        result = validate_path("~/test", "test_path")
        assert "~" not in str(result)


class TestValidatePort:
    """Tests for validate_port."""

    def test_valid_ports(self):
        """Test with valid port numbers."""
        assert validate_port(80, "test_port") == 80
        assert validate_port(443, "test_port") == 443
        assert validate_port(8080, "test_port") == 8080
        assert validate_port(65535, "test_port") == 65535

    def test_port_too_low_fails(self):
        """Test that port < 1 fails."""
        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_port(0, "test_port")

    def test_port_too_high_fails(self):
        """Test that port > 65535 fails."""
        with pytest.raises(ValidationError, match="must be between 1 and 65535"):
            validate_port(65536, "test_port")

    def test_non_integer_fails(self):
        """Test that non-integer fails."""
        with pytest.raises(ValidationError, match="must be an integer"):
            validate_port(80.5, "test_port")


class TestValidateHostname:
    """Tests for validate_hostname."""

    def test_valid_hostname(self):
        """Test with valid hostnames."""
        assert validate_hostname("example.com", "test") == "example.com"
        assert validate_hostname("sub.example.com", "test") == "sub.example.com"
        assert validate_hostname("localhost", "test") == "localhost"
        assert validate_hostname("192.168.1.1", "test") == "192.168.1.1"

    def test_hostname_with_hyphens_underscores(self):
        """Test hostname with hyphens and underscores."""
        assert validate_hostname("my-server.com", "test") == "my-server.com"
        assert validate_hostname("my_server.com", "test") == "my_server.com"

    def test_empty_hostname_fails(self):
        """Test that empty hostname fails."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_hostname("", "test")

    def test_invalid_characters_fail(self):
        """Test that invalid characters fail."""
        with pytest.raises(ValidationError, match="Invalid"):
            validate_hostname("server with spaces", "test")
        
        with pytest.raises(ValidationError, match="Invalid"):
            validate_hostname("server@domain", "test")


class TestValidateRps:
    """Tests for validate_rps."""

    def test_valid_rps(self):
        """Test with valid RPS values."""
        assert validate_rps(100) == 100
        assert validate_rps(1000) == 1000
        assert validate_rps(1) == 1

    def test_zero_rps_fails(self):
        """Test that zero RPS fails."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            validate_rps(0)

    def test_negative_rps_fails(self):
        """Test that negative RPS fails."""
        with pytest.raises(ValidationError, match="must be >= 1"):
            validate_rps(-100)


class TestValidateTestId:
    """Tests for validate_test_id."""

    def test_valid_test_ids(self):
        """Test with valid test IDs."""
        assert validate_test_id("test-123") == "test-123"
        assert validate_test_id("my_test") == "my_test"
        assert validate_test_id("Test123") == "Test123"
        assert validate_test_id("test-2024-01-01") == "test-2024-01-01"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert validate_test_id("  test-123  ") == "test-123"

    def test_empty_test_id_fails(self):
        """Test that empty test ID fails."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_test_id("")

    def test_invalid_characters_fail(self):
        """Test that invalid characters fail."""
        with pytest.raises(ValidationError, match="Invalid test ID"):
            validate_test_id("test 123")
        
        with pytest.raises(ValidationError, match="Invalid test ID"):
            validate_test_id("test@123")
        
        with pytest.raises(ValidationError, match="Invalid test ID"):
            validate_test_id("test/123")


class TestValidateRatioSum:
    """Tests for validate_ratio_sum."""

    def test_valid_ratio_sum(self):
        """Test with valid ratio sum."""
        ratios = {"npm": 40, "pypi": 30, "maven": 30}
        validate_ratio_sum(ratios, expected_sum=100)
        
        # Should not raise

    def test_valid_ratio_sum_with_tolerance(self):
        """Test that tolerance is applied."""
        ratios = {"npm": 40.001, "pypi": 30, "maven": 29.999}
        validate_ratio_sum(ratios, expected_sum=100, tolerance=0.01)
        
        # Should not raise

    def test_invalid_ratio_sum_fails(self):
        """Test that invalid ratio sum fails."""
        ratios = {"npm": 40, "pypi": 30, "maven": 20}
        
        with pytest.raises(ValidationError, match="must sum to 100"):
            validate_ratio_sum(ratios, expected_sum=100)

    def test_custom_expected_sum(self):
        """Test with custom expected sum."""
        ratios = {"a": 0.3, "b": 0.3, "c": 0.4}
        validate_ratio_sum(ratios, expected_sum=1.0)
        
        # Should not raise


class TestValidateNonEmptyString:
    """Tests for validate_non_empty_string."""

    def test_valid_string(self):
        """Test with valid non-empty string."""
        assert validate_non_empty_string("test", "name") == "test"
        assert validate_non_empty_string("hello world", "name") == "hello world"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        assert validate_non_empty_string("  test  ", "name") == "test"

    def test_empty_string_fails(self):
        """Test that empty string fails."""
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_non_empty_string("", "name")
        
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_non_empty_string("   ", "name")

    def test_non_string_fails(self):
        """Test that non-string value fails."""
        with pytest.raises(ValidationError, match="must be a string"):
            validate_non_empty_string(123, "name")
        
        with pytest.raises(ValidationError, match="must be a string"):
            validate_non_empty_string(None, "name")
