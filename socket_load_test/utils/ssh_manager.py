"""SSH connection manager with connection pooling and SFTP support."""

import logging
import os
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

import paramiko
from paramiko.client import SSHClient
from paramiko.ssh_exception import (
    AuthenticationException,
    SSHException,
)

from socket_load_test.utils.validation import validate_hostname, validate_port

logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    """Raised when SSH connection fails."""

    pass


class SSHCommandError(Exception):
    """Raised when SSH command execution fails."""

    pass


class SSHTransferError(Exception):
    """Raised when file transfer fails."""

    pass


class SSHManager:
    """Manages SSH connections with connection pooling and SFTP support.

    This class provides a connection pool for SSH connections to multiple hosts,
    supporting both password and key-based authentication. It handles connection
    lifecycle, command execution, and file transfers.

    Attributes:
        _connections: Dictionary mapping host identifiers to SSHClient instances.
        _lock: Thread lock for connection pool operations.
    """

    def __init__(self):
        """Initialize the SSH manager with an empty connection pool."""
        self._connections: Dict[str, SSHClient] = {}
        self._lock = Lock()

    def _get_host_key(
        self, host: str, port: int = 22, user: str = "root"
    ) -> str:
        """Generate a unique key for a host connection.

        Args:
            host: Hostname or IP address.
            port: SSH port number.
            user: Username for authentication.

        Returns:
            Unique string key for the connection.
        """
        return f"{user}@{host}:{port}"

    def connect(
        self,
        host: str,
        port: int = 22,
        user: str = "root",
        password: Optional[str] = None,
        key_file: Optional[str] = None,
        timeout: int = 10,
    ) -> SSHClient:
        """Establish or retrieve SSH connection.

        Args:
            host: Hostname or IP address.
            port: SSH port number (default: 22).
            user: Username for authentication (default: root).
            password: Password for authentication (optional).
            key_file: Path to SSH private key file (optional).
            timeout: Connection timeout in seconds (default: 10).

        Returns:
            Connected SSHClient instance.

        Raises:
            SSHConnectionError: If connection fails.
            ValueError: If neither password nor key_file is provided.
        """
        validate_hostname(host, "host")
        validate_port(port, "port")

        if not password and not key_file:
            raise ValueError("Either password or key_file must be provided")

        host_key = self._get_host_key(host, port, user)

        with self._lock:
            # Return existing connection if available and active
            if host_key in self._connections:
                client = self._connections[host_key]
                try:
                    # Test if connection is still alive
                    transport = client.get_transport()
                    if transport and transport.is_active():
                        logger.debug(f"Reusing existing connection to {host_key}")
                        return client
                    else:
                        # Connection is dead, remove it
                        logger.debug(f"Removing dead connection to {host_key}")
                        del self._connections[host_key]
                except Exception:
                    # Connection is invalid, remove it
                    del self._connections[host_key]

            # Create new connection
            client = SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Prepare connection kwargs
                connect_kwargs = {
                    "hostname": host,
                    "port": port,
                    "username": user,
                    "timeout": timeout,
                }

                # Add authentication method
                if key_file:
                    # Validate key file exists and has correct permissions
                    key_path = Path(key_file).expanduser()
                    if not key_path.exists():
                        raise SSHConnectionError(f"SSH key file not found: {key_file}")

                    # Check permissions (should be 600)
                    if os.name != "nt":  # Unix-like systems
                        mode = key_path.stat().st_mode & 0o777
                        if mode != 0o600:
                            logger.warning(
                                f"SSH key {key_file} has permissions {oct(mode)}, "
                                "should be 600 for security"
                            )

                    connect_kwargs["key_filename"] = str(key_path)
                    logger.debug(f"Connecting to {host_key} using key file")
                else:
                    connect_kwargs["password"] = password
                    logger.debug(f"Connecting to {host_key} using password")

                # Connect
                client.connect(**connect_kwargs)
                logger.info(f"Successfully connected to {host_key}")

                # Store in pool
                self._connections[host_key] = client
                return client

            except AuthenticationException as e:
                raise SSHConnectionError(
                    f"Authentication failed for {host_key}: {e}"
                ) from e
            except SSHException as e:
                raise SSHConnectionError(f"SSH error connecting to {host_key}: {e}") from e
            except Exception as e:
                raise SSHConnectionError(
                    f"Failed to connect to {host_key}: {e}"
                ) from e

    def execute_command(
        self,
        host: str,
        command: str,
        port: int = 22,
        user: str = "root",
        timeout: int = 30,
    ) -> Tuple[str, str, int]:
        """Execute a command over SSH.

        Args:
            host: Hostname or IP address.
            command: Command to execute.
            port: SSH port number (default: 22).
            user: Username for authentication (default: root).
            timeout: Command execution timeout in seconds (default: 30).

        Returns:
            Tuple of (stdout, stderr, exit_code).

        Raises:
            SSHCommandError: If command execution fails.
            SSHConnectionError: If connection is not established.
        """
        host_key = self._get_host_key(host, port, user)

        with self._lock:
            if host_key not in self._connections:
                raise SSHConnectionError(
                    f"No active connection to {host_key}. Call connect() first."
                )
            client = self._connections[host_key]

        try:
            logger.debug(f"Executing command on {host_key}: {command[:100]}")
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)

            # Read output
            stdout_data = stdout.read().decode("utf-8", errors="replace")
            stderr_data = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()

            if exit_code != 0:
                logger.warning(
                    f"Command on {host_key} exited with code {exit_code}: "
                    f"{stderr_data[:200]}"
                )
            else:
                logger.debug(f"Command on {host_key} completed successfully")

            return stdout_data, stderr_data, exit_code

        except Exception as e:
            raise SSHCommandError(
                f"Failed to execute command on {host_key}: {e}"
            ) from e

    def transfer_file(
        self,
        host: str,
        local_path: str,
        remote_path: str,
        port: int = 22,
        user: str = "root",
    ) -> None:
        """Transfer a file to remote host via SFTP.

        Args:
            host: Hostname or IP address.
            local_path: Path to local file.
            remote_path: Destination path on remote host.
            port: SSH port number (default: 22).
            user: Username for authentication (default: root).

        Raises:
            SSHTransferError: If file transfer fails.
            SSHConnectionError: If connection is not established.
            FileNotFoundError: If local file doesn't exist.
        """
        host_key = self._get_host_key(host, port, user)

        # Validate local file exists
        local_file = Path(local_path).expanduser()
        if not local_file.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        with self._lock:
            if host_key not in self._connections:
                raise SSHConnectionError(
                    f"No active connection to {host_key}. Call connect() first."
                )
            client = self._connections[host_key]

        try:
            logger.debug(f"Transferring {local_path} to {host_key}:{remote_path}")
            sftp = client.open_sftp()

            # Create remote directory if it doesn't exist
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    # Directory doesn't exist, create it
                    logger.debug(f"Creating remote directory: {remote_dir}")
                    self._create_remote_directory(sftp, remote_dir)

            # Transfer file
            sftp.put(str(local_file), remote_path)
            logger.info(f"Successfully transferred {local_path} to {host_key}:{remote_path}")

            sftp.close()

        except Exception as e:
            raise SSHTransferError(
                f"Failed to transfer file to {host_key}: {e}"
            ) from e

    def _create_remote_directory(self, sftp, remote_dir: str) -> None:
        """Recursively create remote directory.

        Args:
            sftp: Active SFTP client.
            remote_dir: Remote directory path to create.
        """
        dirs = []
        while remote_dir and remote_dir != "/":
            dirs.append(remote_dir)
            remote_dir = os.path.dirname(remote_dir)

        # Create directories from root to leaf
        for directory in reversed(dirs):
            try:
                sftp.stat(directory)
            except FileNotFoundError:
                sftp.mkdir(directory)

    def close(
        self, host: str, port: int = 22, user: str = "root"
    ) -> None:
        """Close SSH connection to a specific host.

        Args:
            host: Hostname or IP address.
            port: SSH port number (default: 22).
            user: Username for authentication (default: root).
        """
        host_key = self._get_host_key(host, port, user)

        with self._lock:
            if host_key in self._connections:
                try:
                    self._connections[host_key].close()
                    logger.debug(f"Closed connection to {host_key}")
                except Exception as e:
                    logger.warning(f"Error closing connection to {host_key}: {e}")
                finally:
                    del self._connections[host_key]

    def close_all(self) -> None:
        """Close all SSH connections in the pool."""
        with self._lock:
            for host_key, client in list(self._connections.items()):
                try:
                    client.close()
                    logger.debug(f"Closed connection to {host_key}")
                except Exception as e:
                    logger.warning(f"Error closing connection to {host_key}: {e}")
            self._connections.clear()
            logger.info("Closed all SSH connections")

    def get_active_connections(self) -> list[str]:
        """Get list of active connection identifiers.

        Returns:
            List of host keys for active connections.
        """
        with self._lock:
            return list(self._connections.keys())

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close all connections."""
        self.close_all()
        return False

