"""Tests for configuration module - redirects to actual tests.

Note: The actual configuration tests are in socket_load_test/tests/test_config.py
These placeholder tests verify the Config class structure has changed from the original design.
"""

import pytest
from socket_load_test.config import (
    Config,
    InfrastructureConfig,
    TestConfig,
    RegistriesConfig,
    SSHInfraConfig,
    SSHServerConfig,
)


def test_config_requires_dataclass_structure():
    """Test that Config now requires structured dataclass arguments."""
    # Old design: Config({"a": {"b": {"c": "value"}}})
    # New design: Config(infrastructure=..., test=..., registries=...)
    
    # Verify it raises TypeError with old dict-based approach
    with pytest.raises(TypeError):
        Config({"a": {"b": {"c": "value"}}})


def test_config_from_file_implemented():
    """Test that Config.from_file is now implemented (not NotImplementedError)."""
    # The method now exists and loads from YAML/JSON
    # It will raise FileNotFoundError for non-existent files, not NotImplementedError
    
    with pytest.raises(FileNotFoundError, match="Configuration file not found"):
        Config.from_file("nonexistent_test_file.yaml")


def test_config_structure():
    """Test that Config has the expected dataclass structure."""
    # Create minimal valid config
    infra = InfrastructureConfig(
        type="ssh",
        ssh=SSHInfraConfig(
            firewall_server=SSHServerConfig(
                host="test.example.com",
                user="admin",
                password="test123",
            ),
            load_generators=[
                SSHServerConfig(
                    host="gen1.example.com",
                    user="loadtest",
                    password="gen123",
                )
            ],
        ),
    )
    
    test = TestConfig(
        rps=1000,
        duration="5m",
    )
    
    registries = RegistriesConfig(
        npm_url="http://registry.npmjs.org",
        pypi_url="https://pypi.org/simple",
        maven_url="https://repo1.maven.org/maven2",
    )
    
    # Create config with new structure
    config = Config(
        infrastructure=infra,
        test=test,
        registries=registries,
    )
    
    # Verify structure
    assert config.infrastructure == infra
    assert config.test == test
    assert config.registries == registries
    assert config.traffic is not None  # Auto-created with defaults
    assert config.monitoring is not None  # Auto-created with defaults
    assert config.results is not None  # Auto-created with defaults

