"""SSH-based infrastructure implementation."""

import logging
from typing import Dict, List, Any

from socket_load_test.config import SSHInfraConfig
from socket_load_test.core.infrastructure.base import BaseInfrastructure
from socket_load_test.utils.ssh_manager import (
    SSHManager,
    SSHConnectionError,
    SSHCommandError,
    SSHTransferError,
)

logger = logging.getLogger(__name__)


class SSHInfrastructure(BaseInfrastructure):
    """SSH-based infrastructure for distributed load testing.

    Manages connections to a Socket Firewall server and multiple load generator
    nodes via SSH. Supports both key-based and password authentication, with
    connection pooling for efficient multi-node operations.

    Attributes:
        config: SSH configuration containing firewall and load generator details.
        ssh_manager: Shared SSH connection pool manager.
        _connected: Whether connections have been established.
    """

    def __init__(self, config: SSHInfraConfig):
        """Initialize SSH infrastructure.

        Args:
            config: SSH configuration object.
        """
        self.config = config
        self.ssh_manager = SSHManager()
        self._connected = False
        logger.debug(
            f"Initialized SSH infrastructure with firewall: "
            f"{config.firewall_server.host}, "
            f"load generators: {len(config.load_generators)}"
        )

    def connect(self) -> None:
        """Establish SSH connections to all nodes.

        Connects to the firewall server and all load generator nodes using
        the credentials from configuration.

        Raises:
            SSHConnectionError: If any connection fails.
        """
        logger.info("Connecting to SSH infrastructure")

        # Connect to firewall server
        fw = self.config.firewall_server
        try:
            self.ssh_manager.connect(
                host=fw.host,
                port=fw.port,
                user=fw.user,
                password=fw.password,
                key_file=fw.key_file,
            )
            logger.info(f"Connected to firewall: {fw.host}")
        except SSHConnectionError as e:
            logger.error(f"Failed to connect to firewall {fw.host}: {e}")
            raise

        # Connect to all load generators
        for i, gen in enumerate(self.config.load_generators):
            try:
                self.ssh_manager.connect(
                    host=gen.host,
                    port=gen.port,
                    user=gen.user,
                    password=gen.password,
                    key_file=gen.key_file,
                )
                logger.info(f"Connected to load generator {i+1}/{len(self.config.load_generators)}: {gen.host}")
            except SSHConnectionError as e:
                logger.error(f"Failed to connect to load generator {gen.host}: {e}")
                raise

        self._connected = True
        logger.info("Successfully connected to all SSH nodes")

    def validate_connectivity(self) -> bool:
        """Validate connectivity to all nodes.

        Tests connectivity by executing a simple command on each node.

        Returns:
            True if all nodes are reachable, False otherwise.
        """
        if not self._connected:
            logger.warning("Not connected. Call connect() first.")
            return False

        logger.info("Validating connectivity to all nodes")
        all_valid = True

        # Validate firewall
        fw = self.config.firewall_server
        try:
            stdout, stderr, exit_code = self.ssh_manager.execute_command(
                host=fw.host,
                port=fw.port,
                user=fw.user,
                command="echo 'connectivity test'",
                timeout=5,
            )
            if exit_code != 0:
                logger.error(f"Firewall {fw.host} connectivity check failed")
                all_valid = False
            else:
                logger.debug(f"Firewall {fw.host} connectivity OK")
        except (SSHConnectionError, SSHCommandError) as e:
            logger.error(f"Firewall {fw.host} connectivity error: {e}")
            all_valid = False

        # Validate load generators
        for gen in self.config.load_generators:
            try:
                stdout, stderr, exit_code = self.ssh_manager.execute_command(
                    host=gen.host,
                    port=gen.port,
                    user=gen.user,
                    command="echo 'connectivity test'",
                    timeout=5,
                )
                if exit_code != 0:
                    logger.error(f"Load generator {gen.host} connectivity check failed")
                    all_valid = False
                else:
                    logger.debug(f"Load generator {gen.host} connectivity OK")
            except (SSHConnectionError, SSHCommandError) as e:
                logger.error(f"Load generator {gen.host} connectivity error: {e}")
                all_valid = False

        logger.info(f"Connectivity validation: {'PASSED' if all_valid else 'FAILED'}")
        return all_valid

    def setup_monitoring(self, target: str = "firewall") -> None:
        """Setup monitoring on target node.

        Args:
            target: Target node type ('firewall' or 'all').

        Raises:
            ValueError: If target is invalid.
            SSHCommandError: If setup fails.
        """
        if target not in ["firewall", "all"]:
            raise ValueError(f"Invalid target: {target}. Must be 'firewall' or 'all'")

        logger.info(f"Setting up monitoring on {target}")

        # Setup script content (basic node_exporter check)
        setup_commands = [
            "command -v node_exporter >/dev/null 2>&1 || echo 'node_exporter not found'",
        ]

        if target in ["firewall", "all"]:
            fw = self.config.firewall_server
            for cmd in setup_commands:
                try:
                    stdout, stderr, exit_code = self.ssh_manager.execute_command(
                        host=fw.host,
                        port=fw.port,
                        user=fw.user,
                        command=cmd,
                    )
                    logger.debug(f"Monitoring setup on firewall: {stdout.strip()}")
                except (SSHConnectionError, SSHCommandError) as e:
                    logger.warning(f"Monitoring setup warning on firewall: {e}")

        logger.info("Monitoring setup complete")

    def execute_command(
        self,
        target: str,
        cmd: str,
        bg: bool = False,
    ) -> Dict[str, Any]:
        """Execute command on target node.

        Args:
            target: Target identifier (hostname or 'firewall').
            cmd: Command to execute.
            bg: Whether to run in background (not fully supported via SSH).

        Returns:
            Dictionary with stdout, stderr, and exit_code.

        Raises:
            SSHCommandError: If command execution fails.
            ValueError: If target is not found.
        """
        # Determine target host
        if target == "firewall":
            host_config = self.config.firewall_server
        else:
            # Find in load generators
            host_config = None
            for gen in self.config.load_generators:
                if gen.host == target:
                    host_config = gen
                    break

            if host_config is None:
                raise ValueError(f"Target '{target}' not found in configuration")

        if bg:
            # For background execution, append nohup and &
            cmd = f"nohup {cmd} > /dev/null 2>&1 &"
            logger.debug(f"Running background command on {target}: {cmd}")

        try:
            stdout, stderr, exit_code = self.ssh_manager.execute_command(
                host=host_config.host,
                port=host_config.port,
                user=host_config.user,
                command=cmd,
            )

            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            }
        except (SSHConnectionError, SSHCommandError) as e:
            logger.error(f"Failed to execute command on {target}: {e}")
            raise SSHCommandError(f"Command execution failed on {target}: {e}") from e

    def transfer_file(
        self,
        local: str,
        remote: str,
        target: str,
    ) -> None:
        """Transfer file to target node.

        Args:
            local: Local file path.
            remote: Remote file path.
            target: Target identifier (hostname or 'firewall').

        Raises:
            SSHTransferError: If file transfer fails.
            ValueError: If target is not found.
        """
        # Determine target host
        if target == "firewall":
            host_config = self.config.firewall_server
        else:
            # Find in load generators
            host_config = None
            for gen in self.config.load_generators:
                if gen.host == target:
                    host_config = gen
                    break

            if host_config is None:
                raise ValueError(f"Target '{target}' not found in configuration")

        try:
            self.ssh_manager.transfer_file(
                host=host_config.host,
                local_path=local,
                remote_path=remote,
                port=host_config.port,
                user=host_config.user,
            )
            logger.info(f"Transferred {local} to {target}:{remote}")
        except (SSHConnectionError, SSHTransferError) as e:
            logger.error(f"Failed to transfer file to {target}: {e}")
            raise SSHTransferError(f"File transfer failed to {target}: {e}") from e

    def get_firewall_endpoint(self) -> str:
        """Get firewall proxy endpoint.

        Returns:
            Firewall endpoint in format 'host:port'.
        """
        fw = self.config.firewall_server
        return f"{fw.host}:3128"  # Default SFW proxy port

    def get_monitoring_endpoint(self) -> str:
        """Get monitoring endpoint for firewall.

        Returns:
            Monitoring endpoint in format 'http://host:port/metrics'.
        """
        fw = self.config.firewall_server
        return f"http://{fw.host}:9100/metrics"  # Default node_exporter port

    def get_load_generators(self) -> List[str]:
        """Get list of load generator identifiers.

        Returns:
            List of load generator hostnames.
        """
        return [gen.host for gen in self.config.load_generators]

    def cleanup(self) -> None:
        """Clean up all SSH connections.

        Closes all active SSH connections in the connection pool.
        """
        logger.info("Cleaning up SSH infrastructure")
        self.ssh_manager.close_all()
        self._connected = False
        logger.info("SSH cleanup complete")
