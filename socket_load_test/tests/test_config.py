"""Tests for configuration management."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
import yaml

from socket_load_test.config import (
    Config,
    GKEInfraConfig,
    InfrastructureConfig,
    MinikubeInfraConfig,
    MonitoringConfig,
    RegistriesConfig,
    ResultsConfig,
    SSHInfraConfig,
    SSHServerConfig,
    TestConfig as TestConfigClass,
    TrafficConfig,
)


class TestSSHServerConfig:
    """Tests for SSHServerConfig."""

    def test_valid_config_with_key_file(self, tmp_path):
        """Test valid SSH server config with key file."""
        key_file = tmp_path / "id_rsa"
        key_file.write_text("fake key")
        
        config = SSHServerConfig(
            host="192.168.1.100",
            port=22,
            user="ubuntu",
            key_file=str(key_file)
        )
        config.validate()

    def test_valid_config_with_password(self):
        """Test valid SSH server config with password."""
        config = SSHServerConfig(
            host="192.168.1.100",
            port=22,
            user="ubuntu",
            password="secret"
        )
        config.validate()

    def test_missing_host(self):
        """Test validation fails without host."""
        config = SSHServerConfig(host="", user="ubuntu", password="secret")
        with pytest.raises(ValueError, match="SSH host is required"):
            config.validate()

    def test_missing_user(self):
        """Test validation fails without user."""
        config = SSHServerConfig(host="192.168.1.100", user="", password="secret")
        with pytest.raises(ValueError, match="SSH user is required"):
            config.validate()

    def test_missing_auth(self):
        """Test validation fails without key_file or password."""
        config = SSHServerConfig(host="192.168.1.100", user="ubuntu")
        with pytest.raises(ValueError, match="Either key_file or password must be provided"):
            config.validate()

    def test_invalid_port(self):
        """Test validation fails with invalid port."""
        config = SSHServerConfig(
            host="192.168.1.100",
            port=70000,
            user="ubuntu",
            password="secret"
        )
        with pytest.raises(ValueError, match="Invalid SSH port"):
            config.validate()

    def test_nonexistent_key_file(self):
        """Test validation fails with nonexistent key file."""
        config = SSHServerConfig(
            host="192.168.1.100",
            user="ubuntu",
            key_file="/nonexistent/key"
        )
        with pytest.raises(ValueError, match="SSH key file not found"):
            config.validate()


class TestSSHInfraConfig:
    """Tests for SSHInfraConfig."""

    def test_valid_config(self, tmp_path):
        """Test valid SSH infrastructure config."""
        key_file = tmp_path / "id_rsa"
        key_file.write_text("fake key")
        
        firewall = SSHServerConfig(
            host="192.168.1.100",
            user="ubuntu",
            key_file=str(key_file)
        )
        gen1 = SSHServerConfig(
            host="192.168.1.101",
            user="ubuntu",
            key_file=str(key_file)
        )
        
        config = SSHInfraConfig(
            firewall_server=firewall,
            load_generators=[gen1]
        )
        config.validate()

    def test_no_load_generators(self, tmp_path):
        """Test validation fails without load generators."""
        key_file = tmp_path / "id_rsa"
        key_file.write_text("fake key")
        
        firewall = SSHServerConfig(
            host="192.168.1.100",
            user="ubuntu",
            key_file=str(key_file)
        )
        
        config = SSHInfraConfig(
            firewall_server=firewall,
            load_generators=[]
        )
        with pytest.raises(ValueError, match="At least one load generator is required"):
            config.validate()


class TestInfrastructureConfig:
    """Tests for InfrastructureConfig."""

    def test_invalid_type(self):
        """Test validation fails with invalid type."""
        config = InfrastructureConfig(type="invalid")
        with pytest.raises(ValueError, match="Invalid infrastructure type"):
            config.validate()

    def test_ssh_type_without_ssh_config(self):
        """Test validation fails for ssh type without ssh config."""
        config = InfrastructureConfig(type="ssh")
        with pytest.raises(ValueError, match="SSH configuration is required"):
            config.validate()

    def test_minikube_type_without_minikube_config(self):
        """Test validation fails for minikube type without config."""
        config = InfrastructureConfig(type="minikube")
        with pytest.raises(ValueError, match="Minikube configuration is required"):
            config.validate()

    def test_gke_type_without_gke_config(self):
        """Test validation fails for gke type without config."""
        config = InfrastructureConfig(type="gke")
        with pytest.raises(ValueError, match="GKE configuration is required"):
            config.validate()


class TestTestConfigClass:
    """Tests for TestConfig."""

    def test_valid_config(self):
        """Test valid test config."""
        config = TestConfigClass(rps=1000, duration="5m")
        config.validate()

    def test_negative_rps(self):
        """Test validation fails with negative RPS."""
        config = TestConfigClass(rps=-100, duration="5m")
        with pytest.raises(ValueError, match="RPS must be positive"):
            config.validate()

    def test_zero_rps(self):
        """Test validation fails with zero RPS."""
        config = TestConfigClass(rps=0, duration="5m")
        with pytest.raises(ValueError, match="RPS must be positive"):
            config.validate()

    def test_invalid_warmup_percent(self):
        """Test validation fails with invalid warmup percent."""
        config = TestConfigClass(rps=1000, duration="5m", warmup_rps_percent=150)
        with pytest.raises(ValueError, match="Warmup RPS percent must be between 0 and 100"):
            config.validate()


class TestTrafficConfigClass:
    """Tests for TrafficConfig."""

    def test_valid_config(self):
        """Test valid traffic config."""
        config = TrafficConfig(npm_ratio=40, pypi_ratio=30, maven_ratio=30)
        config.validate()

    def test_ratios_not_sum_to_100(self):
        """Test validation fails when ratios don't sum to 100."""
        config = TrafficConfig(npm_ratio=40, pypi_ratio=40, maven_ratio=30)
        with pytest.raises(ValueError, match="Traffic ratios must sum to 100"):
            config.validate()

    def test_negative_ratio(self):
        """Test validation fails with negative ratio."""
        config = TrafficConfig(npm_ratio=-10, pypi_ratio=60, maven_ratio=50)
        with pytest.raises(ValueError, match="NPM ratio must be between 0 and 100"):
            config.validate()


class TestRegistriesConfigClass:
    """Tests for RegistriesConfig."""

    def test_valid_config(self):
        """Test valid registries config."""
        config = RegistriesConfig(
            npm_url="http://localhost:3128",
            pypi_url="http://localhost:3128",
            maven_url="http://localhost:3128"
        )
        config.validate()

    def test_missing_npm_url(self):
        """Test validation fails without npm_url."""
        config = RegistriesConfig(
            npm_url="",
            pypi_url="http://localhost:3128",
            maven_url="http://localhost:3128"
        )
        with pytest.raises(ValueError, match="npm_url is required"):
            config.validate()

    def test_invalid_cache_hit_percent(self):
        """Test validation fails with invalid cache_hit_percent."""
        config = RegistriesConfig(
            npm_url="http://localhost:3128",
            pypi_url="http://localhost:3128",
            maven_url="http://localhost:3128",
            cache_hit_percent=150
        )
        with pytest.raises(ValueError, match="Cache hit percent must be between 0 and 100"):
            config.validate()


class TestConfig:
    """Tests for Config class."""

    @pytest.fixture
    def valid_ssh_config_dict(self, tmp_path):
        """Fixture for valid SSH config dictionary."""
        key_file = tmp_path / "id_rsa"
        key_file.write_text("fake key")
        
        return {
            "infrastructure": {
                "type": "ssh",
                "ssh": {
                    "firewall_server": {
                        "host": "192.168.1.100",
                        "user": "ubuntu",
                        "key_file": str(key_file)
                    },
                    "load_generators": [
                        {
                            "host": "192.168.1.101",
                            "user": "ubuntu",
                            "key_file": str(key_file)
                        }
                    ]
                }
            },
            "test": {
                "rps": 1000,
                "duration": "5m"
            },
            "registries": {
                "npm_url": "http://localhost:3128",
                "pypi_url": "http://localhost:3128",
                "maven_url": "http://localhost:3128"
            }
        }

    def test_from_dict(self, valid_ssh_config_dict):
        """Test creating config from dictionary."""
        config = Config.from_dict(valid_ssh_config_dict)
        assert config.infrastructure.type == "ssh"
        assert config.test.rps == 1000
        assert config.test.duration == "5m"
        config.validate()

    def test_from_yaml(self, valid_ssh_config_dict):
        """Test loading config from YAML file."""
        with TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "config.yaml"
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(valid_ssh_config_dict, f)
            
            config = Config.from_yaml(yaml_file)
            assert config.infrastructure.type == "ssh"
            assert config.test.rps == 1000
            config.validate()

    def test_from_json(self, valid_ssh_config_dict):
        """Test loading config from JSON file."""
        with TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "config.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(valid_ssh_config_dict, f)
            
            config = Config.from_json(json_file)
            assert config.infrastructure.type == "ssh"
            assert config.test.rps == 1000
            config.validate()

    def test_from_file_yaml(self, valid_ssh_config_dict):
        """Test loading config from file (YAML auto-detect)."""
        with TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "config.yml"
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(valid_ssh_config_dict, f)
            
            config = Config.from_file(yaml_file)
            assert config.infrastructure.type == "ssh"
            config.validate()

    def test_from_file_json(self, valid_ssh_config_dict):
        """Test loading config from file (JSON auto-detect)."""
        with TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "config.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(valid_ssh_config_dict, f)
            
            config = Config.from_file(json_file)
            assert config.infrastructure.type == "ssh"
            config.validate()

    def test_from_file_invalid_extension(self):
        """Test from_file fails with unsupported file format."""
        with TemporaryDirectory() as tmpdir:
            txt_file = Path(tmpdir) / "config.txt"
            txt_file.write_text("invalid")
            
            with pytest.raises(ValueError, match="Unsupported configuration file format"):
                Config.from_file(txt_file)

    def test_from_file_not_found(self):
        """Test from_file fails with nonexistent file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            Config.from_file("/nonexistent/config.yaml")

    def test_to_dict(self, valid_ssh_config_dict):
        """Test converting config to dictionary."""
        config = Config.from_dict(valid_ssh_config_dict)
        config_dict = config.to_dict()
        
        assert config_dict["infrastructure"]["type"] == "ssh"
        assert config_dict["test"]["rps"] == 1000
        assert config_dict["registries"]["npm_url"] == "http://localhost:3128"

    def test_save_yaml(self, valid_ssh_config_dict):
        """Test saving config to YAML file."""
        config = Config.from_dict(valid_ssh_config_dict)
        
        with TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "output.yaml"
            config.save_yaml(yaml_file)
            
            assert yaml_file.exists()
            
            # Load and verify
            loaded = Config.from_yaml(yaml_file)
            assert loaded.test.rps == 1000
            loaded.validate()

    def test_save_json(self, valid_ssh_config_dict):
        """Test saving config to JSON file."""
        config = Config.from_dict(valid_ssh_config_dict)
        
        with TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "output.json"
            config.save_json(json_file)
            
            assert json_file.exists()
            
            # Load and verify
            loaded = Config.from_json(json_file)
            assert loaded.test.rps == 1000
            loaded.validate()

    def test_apply_env_overrides(self, valid_ssh_config_dict):
        """Test applying environment variable overrides."""
        config = Config.from_dict(valid_ssh_config_dict)
        
        with patch.dict(os.environ, {
            "SOCKET_LOADTEST_TEST_RPS": "2000",
            "SOCKET_LOADTEST_TEST_DURATION": "10m",
            "SOCKET_LOADTEST_REGISTRIES_NPM_URL": "http://custom:3128",
            "SOCKET_LOADTEST_MONITORING_ENABLED": "false",
            "SOCKET_LOADTEST_TRAFFIC_NPM_RATIO": "50",
            "SOCKET_LOADTEST_TRAFFIC_PYPI_RATIO": "30",
            "SOCKET_LOADTEST_TRAFFIC_MAVEN_RATIO": "20",
            "SOCKET_LOADTEST_RESULTS_AUTO_GENERATE_HTML": "false",
        }):
            config.apply_env_overrides()
        
        assert config.test.rps == 2000
        assert config.test.duration == "10m"
        assert config.registries.npm_url == "http://custom:3128"
        assert config.monitoring.enabled is False
        assert config.traffic.npm_ratio == 50
        assert config.traffic.pypi_ratio == 30
        assert config.traffic.maven_ratio == 20
        assert config.results.auto_generate_html is False

    def test_default_values(self, valid_ssh_config_dict):
        """Test default values are applied."""
        config = Config.from_dict(valid_ssh_config_dict)
        
        # Check defaults
        assert config.traffic.cache_ratio == 30
        assert config.traffic.npm_ratio == 40
        assert config.traffic.pypi_ratio == 30
        assert config.traffic.maven_ratio == 30
        assert config.traffic.metadata_only is False
        assert config.monitoring.enabled is True
        assert config.monitoring.interval_seconds == 5
        assert config.monitoring.node_exporter_port == 9100
        assert config.results.output_dir == "./load-test-results"
        assert config.results.auto_generate_html is True
        assert config.results.auto_aggregate is True

    def test_minikube_config(self):
        """Test Minikube infrastructure config."""
        config_dict = {
            "infrastructure": {
                "type": "minikube",
                "minikube": {
                    "profile": "test-profile",
                    "context": "test-context"
                }
            },
            "test": {"rps": 1000, "duration": "5m"},
            "registries": {
                "npm_url": "http://localhost:3128",
                "pypi_url": "http://localhost:3128",
                "maven_url": "http://localhost:3128"
            }
        }
        
        config = Config.from_dict(config_dict)
        assert config.infrastructure.type == "minikube"
        assert config.infrastructure.minikube.profile == "test-profile"
        config.validate()

    def test_gke_config(self):
        """Test GKE infrastructure config."""
        config_dict = {
            "infrastructure": {
                "type": "gke",
                "gke": {
                    "project_id": "my-project",
                    "cluster_name": "my-cluster",
                    "zone": "us-central1-a"
                }
            },
            "test": {"rps": 1000, "duration": "5m"},
            "registries": {
                "npm_url": "http://localhost:3128",
                "pypi_url": "http://localhost:3128",
                "maven_url": "http://localhost:3128"
            }
        }
        
        config = Config.from_dict(config_dict)
        assert config.infrastructure.type == "gke"
        assert config.infrastructure.gke.project_id == "my-project"
        config.validate()
