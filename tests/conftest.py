"""Test configuration for socket-load-test."""

import pytest


@pytest.fixture
def sample_config():
    """Provide sample configuration for testing."""
    return {
        "infrastructure": {
            "type": "ssh",
            "ssh": {
                "firewall_server": {
                    "host": "192.168.1.100",
                    "port": 22,
                    "user": "test_user",
                    "key_file": "~/.ssh/id_rsa"
                },
                "load_generators": [
                    {
                        "host": "192.168.1.101",
                        "port": 22,
                        "user": "test_user",
                        "key_file": "~/.ssh/id_rsa"
                    }
                ]
            }
        },
        "test": {
            "rps": 1000,
            "duration": "5m",
            "warmup": True
        },
        "registries": {
            "npm_url": "http://localhost:3128/npm",
            "pypi_url": "http://localhost:3128/pypi",
            "maven_url": "http://localhost:3128/maven"
        }
    }


@pytest.fixture
def sample_config_password():
    """Provide sample configuration with password authentication."""
    return {
        "infrastructure": {
            "type": "ssh",
            "ssh": {
                "firewall_server": {
                    "host": "192.168.1.100",
                    "port": 22,
                    "user": "test_user",
                    "password": "test_password"
                },
                "load_generators": [
                    {
                        "host": "192.168.1.101",
                        "port": 22,
                        "user": "test_user",
                        "password": "gen_password"
                    }
                ]
            }
        },
        "test": {
            "rps": 1000,
            "duration": "5m"
        }
    }
