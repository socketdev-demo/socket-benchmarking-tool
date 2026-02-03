"""Tests for SSH manager."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import paramiko

from socket_load_test.utils.ssh_manager import (
    SSHManager,
    SSHConnectionError,
    SSHCommandError,
    SSHTransferError,
)


@pytest.fixture
def ssh_manager():
    """Create SSH manager instance."""
    return SSHManager()


@pytest.fixture
def mock_ssh_client():
    """Create mock SSH client with transport."""
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    return client


class TestSSHManager:
    """Test suite for SSHManager."""

    def test_init(self, ssh_manager):
        """Test SSHManager initialization."""
        assert ssh_manager._connections == {}
        assert ssh_manager._lock is not None

    def test_get_host_key(self, ssh_manager):
        """Test host key generation."""
        key = ssh_manager._get_host_key("test.example.com", 22, "root")
        assert key == "root@test.example.com:22"

        key = ssh_manager._get_host_key("192.168.1.1", 2222, "admin")
        assert key == "admin@192.168.1.1:2222"

    def test_connect_requires_auth(self, ssh_manager):
        """Test that connect requires either password or key."""
        with pytest.raises(ValueError, match="Either password or key_file must be provided"):
            ssh_manager.connect(host="test.example.com")

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_connect_with_password(self, mock_client_class, ssh_manager, mock_ssh_client):
        """Test connecting with password."""
        mock_client_class.return_value = mock_ssh_client

        client = ssh_manager.connect(
            host="test.example.com",
            user="testuser",
            password="secret123",
        )

        assert client == mock_ssh_client
        mock_ssh_client.set_missing_host_key_policy.assert_called_once()
        mock_ssh_client.connect.assert_called_once()

        call_kwargs = mock_ssh_client.connect.call_args[1]
        assert call_kwargs["hostname"] == "test.example.com"
        assert call_kwargs["username"] == "testuser"
        assert call_kwargs["password"] == "secret123"
        assert call_kwargs["port"] == 22

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    @patch("socket_load_test.utils.ssh_manager.Path")
    def test_connect_with_key(self, mock_path, mock_client_class, ssh_manager, mock_ssh_client):
        """Test connecting with SSH key."""
        mock_client_class.return_value = mock_ssh_client

        # Mock key file path
        mock_key_path = MagicMock()
        mock_key_path.exists.return_value = True
        mock_key_path.stat.return_value.st_mode = 0o100600  # -rw-------
        mock_key_path.__str__.return_value = "/home/user/.ssh/id_rsa"
        mock_path.return_value.expanduser.return_value = mock_key_path

        client = ssh_manager.connect(
            host="test.example.com",
            user="testuser",
            key_file="~/.ssh/id_rsa",
        )

        assert client == mock_ssh_client
        call_kwargs = mock_ssh_client.connect.call_args[1]
        assert "key_filename" in call_kwargs
        assert call_kwargs["key_filename"] == "/home/user/.ssh/id_rsa"

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    @patch("socket_load_test.utils.ssh_manager.Path")
    def test_connect_key_not_found(self, mock_path, mock_client_class, ssh_manager):
        """Test connecting with non-existent key file."""
        mock_key_path = MagicMock()
        mock_key_path.exists.return_value = False
        mock_path.return_value.expanduser.return_value = mock_key_path

        with pytest.raises(SSHConnectionError, match="SSH key file not found"):
            ssh_manager.connect(
                host="test.example.com",
                key_file="/nonexistent/key",
            )

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_connect_authentication_failed(self, mock_client_class, ssh_manager):
        """Test connection with authentication failure."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(SSHConnectionError, match="Authentication failed"):
            ssh_manager.connect(
                host="test.example.com",
                password="wrongpass",
            )

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_connection_pooling(self, mock_client_class, ssh_manager, mock_ssh_client):
        """Test that connections are pooled and reused."""
        mock_client_class.return_value = mock_ssh_client

        # First connection
        client1 = ssh_manager.connect(
            host="test.example.com",
            password="secret",
        )

        # Second connection to same host should reuse
        client2 = ssh_manager.connect(
            host="test.example.com",
            password="secret",
        )

        assert client1 == client2
        # Connect should only be called once
        assert mock_ssh_client.connect.call_count == 1

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_multiple_hosts(self, mock_client_class, ssh_manager):
        """Test connecting to multiple hosts."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_client_class.side_effect = [mock_client1, mock_client2]

        transport1 = MagicMock()
        transport1.is_active.return_value = True
        mock_client1.get_transport.return_value = transport1

        transport2 = MagicMock()
        transport2.is_active.return_value = True
        mock_client2.get_transport.return_value = transport2

        # Connect to first host
        client1 = ssh_manager.connect(host="host1.com", password="pass1")

        # Connect to second host
        client2 = ssh_manager.connect(host="host2.com", password="pass2")

        assert client1 != client2
        assert len(ssh_manager.get_active_connections()) == 2

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_execute_command(self, mock_client_class, ssh_manager, mock_ssh_client):
        """Test command execution."""
        mock_client_class.return_value = mock_ssh_client

        # Connect first
        ssh_manager.connect(host="test.example.com", password="secret")

        # Mock command execution
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"command output"
        mock_stdout.channel.recv_exit_status.return_value = 0

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)

        # Execute command
        stdout, stderr, exit_code = ssh_manager.execute_command(
            host="test.example.com",
            command="echo test",
        )

        assert stdout == "command output"
        assert stderr == ""
        assert exit_code == 0
        mock_ssh_client.exec_command.assert_called_once()

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_execute_command_not_connected(self, mock_client_class, ssh_manager):
        """Test executing command without connection."""
        with pytest.raises(SSHConnectionError, match="No active connection"):
            ssh_manager.execute_command(
                host="test.example.com",
                command="echo test",
            )

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_execute_command_with_error(self, mock_client_class, ssh_manager, mock_ssh_client):
        """Test command execution that returns error."""
        mock_client_class.return_value = mock_ssh_client
        ssh_manager.connect(host="test.example.com", password="secret")

        # Mock failed command
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 1

        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"command failed"

        mock_ssh_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        stdout, stderr, exit_code = ssh_manager.execute_command(
            host="test.example.com",
            command="false",
        )

        assert exit_code == 1
        assert stderr == "command failed"

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    @patch("socket_load_test.utils.ssh_manager.Path")
    def test_transfer_file(self, mock_path_class, mock_client_class, ssh_manager, mock_ssh_client):
        """Test file transfer."""
        mock_client_class.return_value = mock_ssh_client

        # Mock local file
        mock_local_path = MagicMock()
        mock_local_path.exists.return_value = True
        mock_local_path.__str__.return_value = "/local/file.txt"
        mock_path_class.return_value.expanduser.return_value = mock_local_path

        # Mock SFTP
        mock_sftp = MagicMock()
        mock_ssh_client.open_sftp.return_value = mock_sftp

        # Connect and transfer
        ssh_manager.connect(host="test.example.com", password="secret")
        ssh_manager.transfer_file(
            host="test.example.com",
            local_path="/local/file.txt",
            remote_path="/remote/file.txt",
        )

        mock_sftp.put.assert_called_once_with("/local/file.txt", "/remote/file.txt")
        mock_sftp.close.assert_called_once()

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    @patch("socket_load_test.utils.ssh_manager.Path")
    def test_transfer_file_not_found(self, mock_path_class, mock_client_class, ssh_manager):
        """Test transferring non-existent file."""
        mock_local_path = MagicMock()
        mock_local_path.exists.return_value = False
        mock_path_class.return_value.expanduser.return_value = mock_local_path

        with pytest.raises(FileNotFoundError, match="Local file not found"):
            ssh_manager.transfer_file(
                host="test.example.com",
                local_path="/nonexistent/file.txt",
                remote_path="/remote/file.txt",
            )

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_close_connection(self, mock_client_class, ssh_manager, mock_ssh_client):
        """Test closing a specific connection."""
        mock_client_class.return_value = mock_ssh_client

        # Connect
        ssh_manager.connect(host="test.example.com", password="secret")
        assert len(ssh_manager.get_active_connections()) == 1

        # Close
        ssh_manager.close(host="test.example.com")
        assert len(ssh_manager.get_active_connections()) == 0
        mock_ssh_client.close.assert_called_once()

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_close_all_connections(self, mock_client_class, ssh_manager):
        """Test closing all connections."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_client_class.side_effect = [mock_client1, mock_client2]

        transport1 = MagicMock()
        transport1.is_active.return_value = True
        mock_client1.get_transport.return_value = transport1

        transport2 = MagicMock()
        transport2.is_active.return_value = True
        mock_client2.get_transport.return_value = transport2

        # Connect to multiple hosts
        ssh_manager.connect(host="host1.com", password="pass1")
        ssh_manager.connect(host="host2.com", password="pass2")

        assert len(ssh_manager.get_active_connections()) == 2

        # Close all
        ssh_manager.close_all()
        assert len(ssh_manager.get_active_connections()) == 0
        mock_client1.close.assert_called_once()
        mock_client2.close.assert_called_once()

    @patch("socket_load_test.utils.ssh_manager.SSHClient")
    def test_context_manager(self, mock_client_class, mock_ssh_client):
        """Test using SSHManager as context manager."""
        mock_client_class.return_value = mock_ssh_client

        with SSHManager() as manager:
            manager.connect(host="test.example.com", password="secret")
            assert len(manager.get_active_connections()) == 1

        # After context, all connections should be closed
        mock_ssh_client.close.assert_called_once()

    def test_get_active_connections(self, ssh_manager):
        """Test getting active connections list."""
        assert ssh_manager.get_active_connections() == []
