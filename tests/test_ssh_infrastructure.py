"""Tests for SSH infrastructure."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from socket_load_test.config import SSHInfraConfig, SSHServerConfig
from socket_load_test.core.infrastructure.ssh import SSHInfrastructure
from socket_load_test.utils.ssh_manager import (
    SSHConnectionError,
    SSHCommandError,
    SSHTransferError,
)


@pytest.fixture
def ssh_config():
    """Create SSH configuration."""
    return SSHInfraConfig(
        firewall_server=SSHServerConfig(
            host="firewall.example.com",
            port=22,
            user="admin",
            password="fw_password",
        ),
        load_generators=[
            SSHServerConfig(
                host="gen1.example.com",
                port=22,
                user="loadtest",
                password="gen1_password",
            ),
            SSHServerConfig(
                host="gen2.example.com",
                port=22,
                user="loadtest",
                password="gen2_password",
            ),
        ],
    )


@pytest.fixture
def ssh_infrastructure(ssh_config):
    """Create SSH infrastructure instance."""
    return SSHInfrastructure(ssh_config)


@pytest.fixture
def mock_ssh_manager():
    """Create mock SSH manager."""
    with patch("socket_load_test.core.infrastructure.ssh.SSHManager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


class TestSSHInfrastructure:
    """Test suite for SSHInfrastructure."""

    def test_init(self, ssh_infrastructure, ssh_config):
        """Test SSHInfrastructure initialization."""
        assert ssh_infrastructure.config == ssh_config
        assert ssh_infrastructure.ssh_manager is not None
        assert ssh_infrastructure._connected is False

    def test_connect(self, ssh_infrastructure, mock_ssh_manager):
        """Test connecting to all nodes."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager

        ssh_infrastructure.connect()

        # Should connect to firewall + 2 load generators = 3 calls
        assert mock_ssh_manager.connect.call_count == 3

        # Verify firewall connection
        first_call = mock_ssh_manager.connect.call_args_list[0]
        assert first_call[1]["host"] == "firewall.example.com"
        assert first_call[1]["user"] == "admin"
        assert first_call[1]["password"] == "fw_password"

        # Verify load generator connections
        second_call = mock_ssh_manager.connect.call_args_list[1]
        assert second_call[1]["host"] == "gen1.example.com"

        third_call = mock_ssh_manager.connect.call_args_list[2]
        assert third_call[1]["host"] == "gen2.example.com"

        assert ssh_infrastructure._connected is True

    def test_connect_failure(self, ssh_infrastructure, mock_ssh_manager):
        """Test connection failure handling."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.connect.side_effect = SSHConnectionError("Connection failed")

        with pytest.raises(SSHConnectionError):
            ssh_infrastructure.connect()

        assert ssh_infrastructure._connected is False

    def test_validate_connectivity_not_connected(self, ssh_infrastructure):
        """Test validate_connectivity when not connected."""
        result = ssh_infrastructure.validate_connectivity()
        assert result is False

    def test_validate_connectivity_success(self, ssh_infrastructure, mock_ssh_manager):
        """Test successful connectivity validation."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        ssh_infrastructure._connected = True

        # Mock successful command execution
        mock_ssh_manager.execute_command.return_value = (
            "connectivity test\n",
            "",
            0,
        )

        result = ssh_infrastructure.validate_connectivity()

        assert result is True
        # Should validate firewall + 2 generators = 3 calls
        assert mock_ssh_manager.execute_command.call_count == 3

    def test_validate_connectivity_failure(self, ssh_infrastructure, mock_ssh_manager):
        """Test connectivity validation with failures."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        ssh_infrastructure._connected = True

        # Mock failed command execution
        mock_ssh_manager.execute_command.return_value = ("", "error", 1)

        result = ssh_infrastructure.validate_connectivity()

        assert result is False

    def test_validate_connectivity_exception(self, ssh_infrastructure, mock_ssh_manager):
        """Test connectivity validation with exception."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        ssh_infrastructure._connected = True

        # Mock exception during command execution
        mock_ssh_manager.execute_command.side_effect = SSHCommandError("Command failed")

        result = ssh_infrastructure.validate_connectivity()

        assert result is False

    def test_setup_monitoring_firewall(self, ssh_infrastructure, mock_ssh_manager):
        """Test setting up monitoring on firewall."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.execute_command.return_value = ("output", "", 0)

        ssh_infrastructure.setup_monitoring(target="firewall")

        # Should execute setup command on firewall
        assert mock_ssh_manager.execute_command.called
        call_args = mock_ssh_manager.execute_command.call_args_list[0]
        assert call_args[1]["host"] == "firewall.example.com"

    def test_setup_monitoring_invalid_target(self, ssh_infrastructure):
        """Test setup_monitoring with invalid target."""
        with pytest.raises(ValueError, match="Invalid target"):
            ssh_infrastructure.setup_monitoring(target="invalid")

    def test_execute_command_firewall(self, ssh_infrastructure, mock_ssh_manager):
        """Test executing command on firewall."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.execute_command.return_value = (
            "output",
            "",
            0,
        )

        result = ssh_infrastructure.execute_command(
            target="firewall",
            cmd="ls -la",
        )

        assert result["stdout"] == "output"
        assert result["exit_code"] == 0

        call_args = mock_ssh_manager.execute_command.call_args[1]
        assert call_args["host"] == "firewall.example.com"
        assert call_args["command"] == "ls -la"

    def test_execute_command_load_generator(self, ssh_infrastructure, mock_ssh_manager):
        """Test executing command on load generator."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.execute_command.return_value = (
            "output",
            "",
            0,
        )

        result = ssh_infrastructure.execute_command(
            target="gen1.example.com",
            cmd="uptime",
        )

        assert result["stdout"] == "output"
        call_args = mock_ssh_manager.execute_command.call_args[1]
        assert call_args["host"] == "gen1.example.com"

    def test_execute_command_background(self, ssh_infrastructure, mock_ssh_manager):
        """Test executing background command."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.execute_command.return_value = ("", "", 0)

        ssh_infrastructure.execute_command(
            target="firewall",
            cmd="long_running_task",
            bg=True,
        )

        call_args = mock_ssh_manager.execute_command.call_args[1]
        # Command should be wrapped with nohup and &
        assert "nohup" in call_args["command"]
        assert "&" in call_args["command"]

    def test_execute_command_invalid_target(self, ssh_infrastructure):
        """Test executing command on invalid target."""
        with pytest.raises(ValueError, match="not found in configuration"):
            ssh_infrastructure.execute_command(
                target="invalid.example.com",
                cmd="ls",
            )

    def test_execute_command_failure(self, ssh_infrastructure, mock_ssh_manager):
        """Test command execution failure."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.execute_command.side_effect = SSHCommandError("Failed")

        with pytest.raises(SSHCommandError):
            ssh_infrastructure.execute_command(
                target="firewall",
                cmd="failing_command",
            )

    def test_transfer_file_firewall(self, ssh_infrastructure, mock_ssh_manager):
        """Test transferring file to firewall."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager

        ssh_infrastructure.transfer_file(
            local="/local/path/file.txt",
            remote="/remote/path/file.txt",
            target="firewall",
        )

        mock_ssh_manager.transfer_file.assert_called_once()
        call_args = mock_ssh_manager.transfer_file.call_args[1]
        assert call_args["host"] == "firewall.example.com"
        assert call_args["local_path"] == "/local/path/file.txt"
        assert call_args["remote_path"] == "/remote/path/file.txt"

    def test_transfer_file_load_generator(self, ssh_infrastructure, mock_ssh_manager):
        """Test transferring file to load generator."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager

        ssh_infrastructure.transfer_file(
            local="/local/script.js",
            remote="/tmp/script.js",
            target="gen2.example.com",
        )

        call_args = mock_ssh_manager.transfer_file.call_args[1]
        assert call_args["host"] == "gen2.example.com"

    def test_transfer_file_invalid_target(self, ssh_infrastructure):
        """Test transferring file to invalid target."""
        with pytest.raises(ValueError, match="not found in configuration"):
            ssh_infrastructure.transfer_file(
                local="/local/file",
                remote="/remote/file",
                target="invalid.example.com",
            )

    def test_transfer_file_failure(self, ssh_infrastructure, mock_ssh_manager):
        """Test file transfer failure."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        mock_ssh_manager.transfer_file.side_effect = SSHTransferError("Transfer failed")

        with pytest.raises(SSHTransferError):
            ssh_infrastructure.transfer_file(
                local="/local/file",
                remote="/remote/file",
                target="firewall",
            )

    def test_get_firewall_endpoint(self, ssh_infrastructure):
        """Test getting firewall endpoint."""
        endpoint = ssh_infrastructure.get_firewall_endpoint()
        assert endpoint == "firewall.example.com:3128"

    def test_get_monitoring_endpoint(self, ssh_infrastructure):
        """Test getting monitoring endpoint."""
        endpoint = ssh_infrastructure.get_monitoring_endpoint()
        assert endpoint == "http://firewall.example.com:9100/metrics"

    def test_get_load_generators(self, ssh_infrastructure):
        """Test getting load generator list."""
        generators = ssh_infrastructure.get_load_generators()
        assert generators == ["gen1.example.com", "gen2.example.com"]

    def test_cleanup(self, ssh_infrastructure, mock_ssh_manager):
        """Test cleanup of SSH connections."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager
        ssh_infrastructure._connected = True

        ssh_infrastructure.cleanup()

        mock_ssh_manager.close_all.assert_called_once()
        assert ssh_infrastructure._connected is False


class TestSSHInfrastructureIntegration:
    """Integration tests for SSHInfrastructure."""

    def test_full_workflow(self, ssh_infrastructure, mock_ssh_manager):
        """Test full workflow: connect, validate, execute, cleanup."""
        ssh_infrastructure.ssh_manager = mock_ssh_manager

        # Mock successful operations
        mock_ssh_manager.execute_command.return_value = ("output", "", 0)

        # Connect
        ssh_infrastructure.connect()
        assert ssh_infrastructure._connected is True

        # Validate
        result = ssh_infrastructure.validate_connectivity()
        assert result is True

        # Execute command
        result = ssh_infrastructure.execute_command("firewall", "echo test")
        assert result["exit_code"] == 0

        # Get endpoints
        assert ssh_infrastructure.get_firewall_endpoint() == "firewall.example.com:3128"
        assert ssh_infrastructure.get_load_generators() == [
            "gen1.example.com",
            "gen2.example.com",
        ]

        # Cleanup
        ssh_infrastructure.cleanup()
        assert ssh_infrastructure._connected is False

    def test_ssh_config_with_key_file(self):
        """Test SSH infrastructure with key file authentication."""
        config = SSHInfraConfig(
            firewall_server=SSHServerConfig(
                host="firewall.example.com",
                user="admin",
                key_file="~/.ssh/id_rsa",
            ),
            load_generators=[
                SSHServerConfig(
                    host="gen1.example.com",
                    user="loadtest",
                    key_file="~/.ssh/loadtest_key",
                ),
            ],
        )

        infra = SSHInfrastructure(config)
        assert infra.config.firewall_server.key_file == "~/.ssh/id_rsa"
        assert infra.config.load_generators[0].key_file == "~/.ssh/loadtest_key"
