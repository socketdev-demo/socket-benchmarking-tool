"""Base infrastructure interface for socket-load-test."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseInfrastructure(ABC):
    """Abstract base class for infrastructure providers.
    
    Defines the interface for managing different infrastructure types
    (SSH, Minikube, GKE) for load testing.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to infrastructure.
        
        Raises:
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    def validate_connectivity(self) -> bool:
        """Validate connectivity to all components.
        
        Returns:
            True if all components are reachable
            
        Raises:
            ValidationError: If validation fails
        """
        pass

    @abstractmethod
    def setup_monitoring(self, target: str) -> None:
        """Setup monitoring on target node.
        
        Args:
            target: Target node identifier
            
        Raises:
            SetupError: If monitoring setup fails
        """
        pass

    @abstractmethod
    def execute_command(
        self, target: str, cmd: str, bg: bool = False
    ) -> Dict[str, Any]:
        """Execute command on target node.
        
        Args:
            target: Target node identifier
            cmd: Command to execute
            bg: Run in background if True
            
        Returns:
            Dict with keys: stdout, stderr, exit_code
            
        Raises:
            ExecutionError: If command execution fails
        """
        pass

    @abstractmethod
    def transfer_file(self, local: str, remote: str, target: str) -> None:
        """Transfer file to target node.
        
        Args:
            local: Local file path
            remote: Remote file path
            target: Target node identifier
            
        Raises:
            TransferError: If file transfer fails
        """
        pass

    @abstractmethod
    def get_firewall_endpoint(self) -> str:
        """Get firewall endpoint address.
        
        Returns:
            Firewall endpoint (host:port)
        """
        pass

    @abstractmethod
    def get_monitoring_endpoint(self) -> str:
        """Get monitoring endpoint address.
        
        Returns:
            Monitoring endpoint (host:port)
        """
        pass

    @abstractmethod
    def get_load_generators(self) -> List[str]:
        """Get list of load generator identifiers.
        
        Returns:
            List of load generator node identifiers
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup infrastructure resources.
        
        Should be called when testing is complete.
        """
        pass
