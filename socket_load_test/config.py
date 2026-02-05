"""
Configuration management for Socket Firewall Load Test.

This module provides the Config class for loading, validating, and managing
test configuration from YAML/JSON files with environment variable overrides.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


@dataclass
class SSHServerConfig:
    """SSH server configuration."""
    
    host: str
    port: int = 22
    user: str = "root"
    key_file: Optional[str] = None
    password: Optional[str] = None

    def validate(self) -> None:
        """Validate SSH server configuration."""
        if not self.host:
            raise ValueError("SSH host is required")
        if not self.user:
            raise ValueError("SSH user is required")
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid SSH port: {self.port}")
        if not self.key_file and not self.password:
            raise ValueError("Either key_file or password must be provided")
        if self.key_file and not Path(self.key_file).expanduser().exists():
            raise ValueError(f"SSH key file not found: {self.key_file}")


@dataclass
class SSHInfraConfig:
    """SSH infrastructure configuration."""
    
    firewall_server: SSHServerConfig
    load_generators: List[SSHServerConfig] = field(default_factory=list)

    def validate(self) -> None:
        """Validate SSH infrastructure configuration."""
        self.firewall_server.validate()
        if not self.load_generators:
            raise ValueError("At least one load generator is required")
        for gen in self.load_generators:
            gen.validate()


@dataclass
class MinikubeInfraConfig:
    """Minikube infrastructure configuration."""
    
    profile: str = "minikube"
    context: Optional[str] = None

    def validate(self) -> None:
        """Validate Minikube configuration."""
        if not self.profile:
            raise ValueError("Minikube profile is required")


@dataclass
class GKEInfraConfig:
    """GKE infrastructure configuration."""
    
    project_id: str
    cluster_name: str
    zone: str
    credentials_file: Optional[str] = None

    def validate(self) -> None:
        """Validate GKE configuration."""
        if not self.project_id:
            raise ValueError("GKE project_id is required")
        if not self.cluster_name:
            raise ValueError("GKE cluster_name is required")
        if not self.zone:
            raise ValueError("GKE zone is required")
        if self.credentials_file and not Path(self.credentials_file).exists():
            raise ValueError(f"GKE credentials file not found: {self.credentials_file}")


@dataclass
class InfrastructureConfig:
    """Infrastructure configuration."""
    
    type: str  # ssh, minikube, or gke
    ssh: Optional[SSHInfraConfig] = None
    minikube: Optional[MinikubeInfraConfig] = None
    gke: Optional[GKEInfraConfig] = None

    def validate(self) -> None:
        """Validate infrastructure configuration."""
        valid_types = ["ssh", "minikube", "gke"]
        if self.type not in valid_types:
            raise ValueError(f"Invalid infrastructure type: {self.type}. Must be one of {valid_types}")
        
        if self.type == "ssh":
            if not self.ssh:
                raise ValueError("SSH configuration is required when type is 'ssh'")
            self.ssh.validate()
        elif self.type == "minikube":
            if not self.minikube:
                raise ValueError("Minikube configuration is required when type is 'minikube'")
            self.minikube.validate()
        elif self.type == "gke":
            if not self.gke:
                raise ValueError("GKE configuration is required when type is 'gke'")
            self.gke.validate()


@dataclass
class TestConfig:
    """Test execution configuration."""
    
    rps: int
    duration: str
    test_id: Optional[str] = None
    warmup: bool = True
    warmup_duration: str = "30s"
    warmup_rps_percent: int = 10
    no_docker: bool = False

    def validate(self) -> None:
        """Validate test configuration."""
        if self.rps <= 0:
            raise ValueError("RPS must be positive")
        if not self.duration:
            raise ValueError("Duration is required")
        if self.warmup_rps_percent < 0 or self.warmup_rps_percent > 100:
            raise ValueError("Warmup RPS percent must be between 0 and 100")


@dataclass
class RegistriesConfig:
    """Registries configuration."""
    
    npm_url: Optional[str] = None
    pypi_url: Optional[str] = None
    maven_url: Optional[str] = None
    cache_hit_percent: int = 30
    base_url: Optional[str] = None
    npm_path: Optional[str] = None
    pypi_path: Optional[str] = None
    maven_path: Optional[str] = None
    ecosystems: List[str] = field(default_factory=lambda: ['npm', 'pypi', 'maven'])
    
    # NPM Authentication (supports Bearer token or Basic auth username/password)
    npm_token: Optional[str] = None  # Bearer token for npm registry
    npm_username: Optional[str] = None  # Basic auth username
    npm_password: Optional[str] = None  # Basic auth password
    
    # PyPI Authentication (supports token or username/password, both use Basic auth)
    pypi_token: Optional[str] = None  # Token for PyPI registry (will use Basic auth: Authorization: Basic base64(__token__:token))
    pypi_username: Optional[str] = None  # Basic auth username
    pypi_password: Optional[str] = None  # Basic auth password
    
    # Maven Authentication (username/password only, uses Basic auth)
    maven_username: Optional[str] = None  # Basic auth username
    maven_password: Optional[str] = None  # Basic auth password

    def __post_init__(self):
        """Build URLs from base_url + paths if individual URLs not provided."""
        if self.base_url:
            base = self.base_url.rstrip('/')
            
            # Build npm_url from base + path
            if not self.npm_url and self.npm_path:
                path = self.npm_path if self.npm_path.startswith('/') else '/' + self.npm_path
                self.npm_url = f"{base}{path}"
            
            # Build pypi_url from base + path
            if not self.pypi_url and self.pypi_path:
                path = self.pypi_path if self.pypi_path.startswith('/') else '/' + self.pypi_path
                self.pypi_url = f"{base}{path}"
            
            # Build maven_url from base + path
            if not self.maven_url and self.maven_path:
                path = self.maven_path if self.maven_path.startswith('/') else '/' + self.maven_path
                self.maven_url = f"{base}{path}"

    def validate(self) -> None:
        """Validate registries configuration."""
        # Validate only selected ecosystems
        if 'npm' in self.ecosystems and not self.npm_url:
            raise ValueError("npm_url is required when npm ecosystem is selected (or provide base_url + npm_path)")
        if 'pypi' in self.ecosystems and not self.pypi_url:
            raise ValueError("pypi_url is required when pypi ecosystem is selected (or provide base_url + pypi_path)")
        if 'maven' in self.ecosystems and not self.maven_url:
            raise ValueError("maven_url is required when maven ecosystem is selected (or provide base_url + maven_path)")
        if self.cache_hit_percent < 0 or self.cache_hit_percent > 100:
            raise ValueError("Cache hit percent must be between 0 and 100")


@dataclass
class TrafficConfig:
    """Traffic distribution configuration."""
    
    cache_ratio: int = 30
    npm_ratio: int = 40
    pypi_ratio: int = 30
    maven_ratio: int = 30
    metadata_only: bool = False
    ecosystems: List[str] = field(default_factory=lambda: ['npm', 'pypi', 'maven'])

    def __post_init__(self):
        """Auto-balance traffic ratios based on selected ecosystems."""
        # Only consider selected ecosystems
        num_ecosystems = len(self.ecosystems)
        if num_ecosystems == 0:
            return
        
        # Calculate equal distribution
        equal_share = 100 // num_ecosystems
        remainder = 100 % num_ecosystems
        
        # Reset all ratios to 0 first
        self.npm_ratio = 0
        self.pypi_ratio = 0
        self.maven_ratio = 0
        
        # Distribute equally among selected ecosystems
        for i, ecosystem in enumerate(self.ecosystems):
            share = equal_share + (1 if i < remainder else 0)
            if ecosystem == 'npm':
                self.npm_ratio = share
            elif ecosystem == 'pypi':
                self.pypi_ratio = share
            elif ecosystem == 'maven':
                self.maven_ratio = share

    def validate(self) -> None:
        """Validate traffic configuration."""
        if self.cache_ratio < 0 or self.cache_ratio > 100:
            raise ValueError("Cache ratio must be between 0 and 100")
        
        # Validate only selected ecosystem ratios
        if 'npm' in self.ecosystems:
            if self.npm_ratio < 0 or self.npm_ratio > 100:
                raise ValueError("NPM ratio must be between 0 and 100")
        else:
            self.npm_ratio = 0
            
        if 'pypi' in self.ecosystems:
            if self.pypi_ratio < 0 or self.pypi_ratio > 100:
                raise ValueError("PyPI ratio must be between 0 and 100")
        else:
            self.pypi_ratio = 0
            
        if 'maven' in self.ecosystems:
            if self.maven_ratio < 0 or self.maven_ratio > 100:
                raise ValueError("Maven ratio must be between 0 and 100")
        else:
            self.maven_ratio = 0
        
        # Sum only selected ecosystem ratios
        total = 0
        if 'npm' in self.ecosystems:
            total += self.npm_ratio
        if 'pypi' in self.ecosystems:
            total += self.pypi_ratio
        if 'maven' in self.ecosystems:
            total += self.maven_ratio
            
        if total != 100 and len(self.ecosystems) > 0:
            raise ValueError(f"Traffic ratios for selected ecosystems must sum to 100, got {total}")


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    
    enabled: bool = True
    interval_seconds: int = 5
    node_exporter_port: int = 9100

    def validate(self) -> None:
        """Validate monitoring configuration."""
        if self.interval_seconds < 1:
            raise ValueError("Monitoring interval must be at least 1 second")
        if self.node_exporter_port < 1 or self.node_exporter_port > 65535:
            raise ValueError(f"Invalid node_exporter_port: {self.node_exporter_port}")


@dataclass
class ResultsConfig:
    """Results configuration."""
    
    output_dir: str = "./load-test-results"
    auto_generate_html: bool = True
    auto_aggregate: bool = True

    def validate(self) -> None:
        """Validate results configuration."""
        if not self.output_dir:
            raise ValueError("output_dir is required")


class Config:
    """Main configuration class for Socket Firewall Load Test."""

    def __init__(
        self,
        infrastructure: InfrastructureConfig,
        test: TestConfig,
        registries: RegistriesConfig,
        traffic: Optional[TrafficConfig] = None,
        monitoring: Optional[MonitoringConfig] = None,
        results: Optional[ResultsConfig] = None,
    ):
        """
        Initialize configuration.

        Args:
            infrastructure: Infrastructure configuration
            test: Test execution configuration
            registries: Registries configuration
            traffic: Traffic distribution configuration (optional)
            monitoring: Monitoring configuration (optional)
            results: Results configuration (optional)
        """
        self.infrastructure = infrastructure
        self.test = test
        self.registries = registries
        self.traffic = traffic or TrafficConfig()
        self.monitoring = monitoring or MonitoringConfig()
        self.results = results or ResultsConfig()

    def validate(self) -> None:
        """Validate all configuration sections."""
        self.infrastructure.validate()
        self.test.validate()
        self.registries.validate()
        self.traffic.validate()
        self.monitoring.validate()
        self.results.validate()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "infrastructure": asdict(self.infrastructure),
            "test": asdict(self.test),
            "registries": asdict(self.registries),
            "traffic": asdict(self.traffic),
            "monitoring": asdict(self.monitoring),
            "results": asdict(self.results),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """
        Create Config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            Config instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Parse infrastructure
        infra_data = data.get("infrastructure", {})
        infra_type = infra_data.get("type")
        
        ssh_config = None
        minikube_config = None
        gke_config = None
        
        if infra_type == "ssh":
            ssh_data = infra_data.get("ssh", {})
            firewall_server = SSHServerConfig(**ssh_data.get("firewall_server", {}))
            load_generators = [
                SSHServerConfig(**gen) for gen in ssh_data.get("load_generators", [])
            ]
            ssh_config = SSHInfraConfig(
                firewall_server=firewall_server,
                load_generators=load_generators
            )
        elif infra_type == "minikube":
            minikube_config = MinikubeInfraConfig(**infra_data.get("minikube", {}))
        elif infra_type == "gke":
            gke_config = GKEInfraConfig(**infra_data.get("gke", {}))
        
        infrastructure = InfrastructureConfig(
            type=infra_type,
            ssh=ssh_config,
            minikube=minikube_config,
            gke=gke_config
        )
        
        # Parse other configs
        test = TestConfig(**data.get("test", {}))
        registries = RegistriesConfig(**data.get("registries", {}))
        traffic = TrafficConfig(**data.get("traffic", {})) if "traffic" in data else None
        monitoring = MonitoringConfig(**data.get("monitoring", {})) if "monitoring" in data else None
        results = ResultsConfig(**data.get("results", {})) if "results" in data else None
        
        return cls(
            infrastructure=infrastructure,
            test=test,
            registries=registries,
            traffic=traffic,
            monitoring=monitoring,
            results=results
        )

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Config":
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            raise ValueError(f"Empty configuration file: {path}")
        
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "Config":
        """
        Load configuration from JSON file.

        Args:
            path: Path to JSON configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        if not data:
            raise ValueError(f"Empty configuration file: {path}")
        
        return cls.from_dict(data)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Config":
        """
        Load configuration from file (auto-detect YAML/JSON).

        Args:
            path: Path to configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is unsupported or invalid
        """
        path = Path(path)
        suffix = path.suffix.lower()
        
        if suffix in ['.yaml', '.yml']:
            return cls.from_yaml(path)
        elif suffix == '.json':
            return cls.from_json(path)
        else:
            raise ValueError(f"Unsupported configuration file format: {suffix}")

    def apply_env_overrides(self) -> None:
        """
        Apply environment variable overrides to configuration.

        Environment variables follow the pattern:
        SOCKET_LOADTEST_<SECTION>_<KEY>=value
        
        Examples:
            SOCKET_LOADTEST_TEST_RPS=1000
            SOCKET_LOADTEST_REGISTRIES_NPM_URL=http://localhost:3128
            SOCKET_LOADTEST_MONITORING_ENABLED=false
        """
        # Test overrides
        if rps := os.getenv("SOCKET_LOADTEST_TEST_RPS"):
            self.test.rps = int(rps)
        if duration := os.getenv("SOCKET_LOADTEST_TEST_DURATION"):
            self.test.duration = duration
        if test_id := os.getenv("SOCKET_LOADTEST_TEST_ID"):
            self.test.test_id = test_id
        if warmup := os.getenv("SOCKET_LOADTEST_TEST_WARMUP"):
            self.test.warmup = warmup.lower() in ["true", "1", "yes"]
        
        # Registry overrides
        if npm_url := os.getenv("SOCKET_LOADTEST_REGISTRIES_NPM_URL"):
            self.registries.npm_url = npm_url
        if pypi_url := os.getenv("SOCKET_LOADTEST_REGISTRIES_PYPI_URL"):
            self.registries.pypi_url = pypi_url
        if maven_url := os.getenv("SOCKET_LOADTEST_REGISTRIES_MAVEN_URL"):
            self.registries.maven_url = maven_url
        if cache_hit := os.getenv("SOCKET_LOADTEST_REGISTRIES_CACHE_HIT_PERCENT"):
            self.registries.cache_hit_percent = int(cache_hit)
        
        # Traffic overrides
        if cache_ratio := os.getenv("SOCKET_LOADTEST_TRAFFIC_CACHE_RATIO"):
            self.traffic.cache_ratio = int(cache_ratio)
        if npm_ratio := os.getenv("SOCKET_LOADTEST_TRAFFIC_NPM_RATIO"):
            self.traffic.npm_ratio = int(npm_ratio)
        if pypi_ratio := os.getenv("SOCKET_LOADTEST_TRAFFIC_PYPI_RATIO"):
            self.traffic.pypi_ratio = int(pypi_ratio)
        if maven_ratio := os.getenv("SOCKET_LOADTEST_TRAFFIC_MAVEN_RATIO"):
            self.traffic.maven_ratio = int(maven_ratio)
        if metadata_only := os.getenv("SOCKET_LOADTEST_TRAFFIC_METADATA_ONLY"):
            self.traffic.metadata_only = metadata_only.lower() in ["true", "1", "yes"]
        
        # Monitoring overrides
        if enabled := os.getenv("SOCKET_LOADTEST_MONITORING_ENABLED"):
            self.monitoring.enabled = enabled.lower() in ["true", "1", "yes"]
        if interval := os.getenv("SOCKET_LOADTEST_MONITORING_INTERVAL_SECONDS"):
            self.monitoring.interval_seconds = int(interval)
        if port := os.getenv("SOCKET_LOADTEST_MONITORING_NODE_EXPORTER_PORT"):
            self.monitoring.node_exporter_port = int(port)
        
        # Results overrides
        if output_dir := os.getenv("SOCKET_LOADTEST_RESULTS_OUTPUT_DIR"):
            self.results.output_dir = output_dir
        if auto_html := os.getenv("SOCKET_LOADTEST_RESULTS_AUTO_GENERATE_HTML"):
            self.results.auto_generate_html = auto_html.lower() in ["true", "1", "yes"]
        if auto_agg := os.getenv("SOCKET_LOADTEST_RESULTS_AUTO_AGGREGATE"):
            self.results.auto_aggregate = auto_agg.lower() in ["true", "1", "yes"]

    def save_yaml(self, path: Union[str, Path]) -> None:
        """
        Save configuration to YAML file.

        Args:
            path: Path to save YAML file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    def save_json(self, path: Union[str, Path]) -> None:
        """
        Save configuration to JSON file.

        Args:
            path: Path to save JSON file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
