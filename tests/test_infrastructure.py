"""Tests for base infrastructure."""

import pytest
from socket_load_test.core.infrastructure.base import BaseInfrastructure


def test_base_infrastructure_is_abstract():
    """Test that BaseInfrastructure cannot be instantiated."""
    with pytest.raises(TypeError):
        BaseInfrastructure()


class ConcreteInfrastructure(BaseInfrastructure):
    """Concrete implementation for testing."""
    
    def __init__(self):
        self._connected = False
        self._commands_executed = []
        self._files_transferred = []
    
    def connect(self) -> None:
        """Establish connection to infrastructure."""
        self._connected = True
    
    def validate_connectivity(self) -> bool:
        """Validate connectivity to all components."""
        return self._connected
    
    def setup_monitoring(self, target: str) -> None:
        """Setup monitoring on target node."""
        if not self._connected:
            raise ConnectionError("Not connected")
        self._commands_executed.append(f"setup_monitoring:{target}")
    
    def execute_command(self, target: str, cmd: str, bg: bool = False) -> dict:
        """Execute command on target node."""
        if not self._connected:
            raise ConnectionError("Not connected")
        self._commands_executed.append((target, cmd, bg))
        return {
            "stdout": f"Output of {cmd}",
            "stderr": "",
            "exit_code": 0
        }
    
    def transfer_file(self, local: str, remote: str, target: str) -> None:
        """Transfer file to target node."""
        if not self._connected:
            raise ConnectionError("Not connected")
        self._files_transferred.append((local, remote, target))
    
    def get_firewall_endpoint(self) -> str:
        """Get firewall endpoint address."""
        return "192.168.1.100:3128"
    
    def get_monitoring_endpoint(self) -> str:
        """Get monitoring endpoint address."""
        return "192.168.1.100:9100"
    
    def get_load_generators(self) -> list:
        """Get list of load generator identifiers."""
        return ["gen-1", "gen-2"]
    
    def cleanup(self) -> None:
        """Cleanup infrastructure resources."""
        self._connected = False
        self._commands_executed.clear()
        self._files_transferred.clear()


def test_concrete_implementation():
    """Test that concrete implementation works correctly."""
    infra = ConcreteInfrastructure()
    
    # Test connect
    assert not infra.validate_connectivity()
    infra.connect()
    assert infra.validate_connectivity()
    
    # Test execute_command
    result = infra.execute_command("gen-1", "echo hello", bg=False)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    assert ("gen-1", "echo hello", False) in infra._commands_executed
    
    # Test transfer_file
    infra.transfer_file("/local/file.txt", "/remote/file.txt", "gen-1")
    assert ("/local/file.txt", "/remote/file.txt", "gen-1") in infra._files_transferred
    
    # Test setup_monitoring
    infra.setup_monitoring("gen-1")
    assert "setup_monitoring:gen-1" in infra._commands_executed
    
    # Test get_firewall_endpoint
    assert infra.get_firewall_endpoint() == "192.168.1.100:3128"
    
    # Test get_monitoring_endpoint
    assert infra.get_monitoring_endpoint() == "192.168.1.100:9100"
    
    # Test get_load_generators
    generators = infra.get_load_generators()
    assert len(generators) == 2
    assert "gen-1" in generators
    assert "gen-2" in generators
    
    # Test cleanup
    infra.cleanup()
    assert not infra.validate_connectivity()
    assert len(infra._commands_executed) == 0
    assert len(infra._files_transferred) == 0


def test_methods_require_connection():
    """Test that methods require connection."""
    infra = ConcreteInfrastructure()
    
    with pytest.raises(ConnectionError):
        infra.execute_command("gen-1", "test")
    
    with pytest.raises(ConnectionError):
        infra.transfer_file("/local", "/remote", "gen-1")
    
    with pytest.raises(ConnectionError):
        infra.setup_monitoring("gen-1")


def test_execute_command_background():
    """Test background command execution."""
    infra = ConcreteInfrastructure()
    infra.connect()
    
    result = infra.execute_command("gen-1", "long-running-task", bg=True)
    assert result["exit_code"] == 0
    assert ("gen-1", "long-running-task", True) in infra._commands_executed


def test_multiple_file_transfers():
    """Test multiple file transfers."""
    infra = ConcreteInfrastructure()
    infra.connect()
    
    files = [
        ("/local/file1.txt", "/remote/file1.txt", "gen-1"),
        ("/local/file2.txt", "/remote/file2.txt", "gen-2"),
        ("/local/script.sh", "/remote/script.sh", "gen-1"),
    ]
    
    for local, remote, target in files:
        infra.transfer_file(local, remote, target)
    
    assert len(infra._files_transferred) == 3
    for file_transfer in files:
        assert file_transfer in infra._files_transferred


def test_all_abstract_methods_implemented():
    """Test that all abstract methods are implemented."""
    required_methods = [
        'connect',
        'validate_connectivity',
        'setup_monitoring',
        'execute_command',
        'transfer_file',
        'get_firewall_endpoint',
        'get_monitoring_endpoint',
        'get_load_generators',
        'cleanup',
    ]
    
    for method in required_methods:
        assert hasattr(BaseInfrastructure, method)
        assert callable(getattr(BaseInfrastructure, method))
