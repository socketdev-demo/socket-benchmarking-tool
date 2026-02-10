"""Package validator for checking metadata and download availability.

This module validates packages by checking if metadata and downloads are available
and don't return 404 errors.
"""

import requests
import warnings
from typing import Dict, List, Any, Optional, Tuple
from base64 import b64encode

# Suppress SSL warnings when verification is disabled
from urllib3.exceptions import InsecureRequestWarning


class PackageValidator:
    """Validates package metadata and download availability."""
    
    def __init__(self, timeout: int = 30, verbose: bool = False, verify_ssl: bool = True):
        """Initialize package validator.
        
        Args:
            timeout: Request timeout in seconds
            verbose: Enable verbose output
            verify_ssl: Whether to verify SSL certificates (False for self-signed certs)
        """
        self.timeout = timeout
        self.verbose = verbose
        self.verify_ssl = verify_ssl
        
        # Suppress SSL warnings if verification is disabled
        if not verify_ssl:
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)
    
    def validate_npm_package(
        self,
        package_name: str,
        version: str,
        registry_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate NPM package metadata and download.
        
        Args:
            package_name: Package name
            version: Package version
            registry_url: Base URL of npm registry
            auth_token: Bearer token for authentication
            username: Username for basic auth
            password: Password for basic auth
            
        Returns:
            Dict with validation results including metadata_valid and download_valid
        """
        registry_url = registry_url.rstrip('/')
        
        headers = {
            'User-Agent': 'npm/10.0.0 node/v20.0.0',
            'Accept': 'application/json'
        }
        
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        elif username and password:
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        result = {
            'package': package_name,
            'version': version,
            'ecosystem': 'npm',
            'metadata_valid': False,
            'download_valid': False,
            'metadata_status': None,
            'download_status': None,
            'download_url': None
        }
        
        # Check metadata
        try:
            metadata_url = f"{registry_url}/{package_name}"
            response = requests.get(metadata_url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            result['metadata_status'] = response.status_code
            
            if response.status_code == 200:
                result['metadata_valid'] = True
                data = response.json()
                
                # Extract download URL from metadata
                versions_data = data.get('versions', {})
                if version in versions_data:
                    dist = versions_data[version].get('dist', {})
                    tarball_url = dist.get('tarball')
                    if tarball_url:
                        result['download_url'] = tarball_url
                        
                        # Validate download URL
                        try:
                            download_response = requests.head(
                                tarball_url,
                                headers=headers,
                                timeout=self.timeout,
                                allow_redirects=True,
                                verify=self.verify_ssl
                            )
                            result['download_status'] = download_response.status_code
                            result['download_valid'] = download_response.status_code == 200
                        except Exception as e:
                            if self.verbose:
                                print(f"    Warning: Download check failed for {package_name}@{version}: {e}")
                            result['download_status'] = 0
        except Exception as e:
            if self.verbose:
                print(f"    Warning: Metadata check failed for {package_name}: {e}")
            result['metadata_status'] = 0
        
        return result
    
    def validate_pypi_package(
        self,
        package_name: str,
        version: str,
        registry_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate PyPI package metadata and download.
        
        Args:
            package_name: Package name
            version: Package version
            registry_url: Base URL of PyPI registry
            auth_token: Token for authentication
            username: Username for basic auth
            password: Password for basic auth
            
        Returns:
            Dict with validation results
        """
        registry_url = registry_url.rstrip('/')
        
        # Use Accept: */* to match curl behavior (some registries like Artifactory are strict)
        headers = {
            'User-Agent': 'pip/23.0 CPython/3.11.0',
            'Accept': '*/*'  # Changed from 'application/json' to match curl
        }
        
        if auth_token:
            credentials = b64encode(f'__token__:{auth_token}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        elif username and password:
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        result = {
            'package': package_name,
            'version': version,
            'ecosystem': 'pypi',
            'metadata_valid': False,
            'download_valid': False,
            'metadata_status': None,
            'download_status': None,
            'download_url': None
        }
        
        # Check JSON metadata
        try:
            metadata_url = f"{registry_url}/pypi/{package_name}/json"
            response = requests.get(metadata_url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            result['metadata_status'] = response.status_code
            
            if response.status_code == 200:
                result['metadata_valid'] = True
                data = response.json()
                
                # Extract download URL from metadata
                releases = data.get('releases', {})
                if version in releases and releases[version]:
                    # Get first wheel or source distribution URL
                    for file_info in releases[version]:
                        download_url = file_info.get('url')
                        if download_url:
                            result['download_url'] = download_url
                            
                            # Validate download URL
                            try:
                                download_response = requests.head(
                                    download_url,
                                    headers=headers,
                                    timeout=self.timeout,
                                    allow_redirects=True,
                                    verify=self.verify_ssl
                                )
                                result['download_status'] = download_response.status_code
                                result['download_valid'] = download_response.status_code == 200
                                break  # Only check one file
                            except Exception as e:
                                if self.verbose:
                                    print(f"    Warning: Download check failed for {package_name}@{version}: {e}")
                                result['download_status'] = 0
        except Exception as e:
            if self.verbose:
                print(f"    Warning: Metadata check failed for {package_name}: {e}")
            result['metadata_status'] = 0
        
        return result
    
    def validate_maven_package(
        self,
        group_id: str,
        artifact_id: str,
        version: str,
        registry_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate Maven package metadata and download.
        
        Args:
            group_id: Maven group ID
            artifact_id: Maven artifact ID
            version: Package version
            registry_url: Base URL of Maven registry
            username: Username for basic auth
            password: Password for basic auth
            
        Returns:
            Dict with validation results
        """
        registry_url = registry_url.rstrip('/')
        
        headers = {
            'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
            'Accept': 'application/xml'
        }
        
        if username and password:
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        result = {
            'package': f'{group_id}:{artifact_id}',
            'version': version,
            'ecosystem': 'maven',
            'metadata_valid': False,
            'download_valid': False,
            'metadata_status': None,
            'download_status': None,
            'download_url': None
        }
        
        # Check metadata
        try:
            group_path = group_id.replace('.', '/')
            metadata_url = f"{registry_url}/{group_path}/{artifact_id}/maven-metadata.xml"
            response = requests.get(metadata_url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            result['metadata_status'] = response.status_code
            
            if response.status_code == 200:
                result['metadata_valid'] = True
                
                # Check download (JAR file)
                jar_url = f"{registry_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
                result['download_url'] = jar_url
                
                try:
                    download_response = requests.head(
                        jar_url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=True,
                        verify=self.verify_ssl
                    )
                    result['download_status'] = download_response.status_code
                    result['download_valid'] = download_response.status_code == 200
                except Exception as e:
                    if self.verbose:
                        print(f"    Warning: Download check failed for {group_id}:{artifact_id}@{version}: {e}")
                    result['download_status'] = 0
        except Exception as e:
            if self.verbose:
                print(f"    Warning: Metadata check failed for {group_id}:{artifact_id}: {e}")
            result['metadata_status'] = 0
        
        return result
    
    def validate_packages(
        self,
        ecosystem: str,
        packages_with_versions: List[Dict[str, Any]],
        registry_url: str,
        auth_config: Optional[Dict[str, Optional[str]]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate a list of packages and separate into valid and invalid.
        
        Args:
            ecosystem: Ecosystem name (npm, pypi, maven)
            packages_with_versions: List of packages with versions
            registry_url: Registry URL
            auth_config: Authentication configuration
            
        Returns:
            Tuple of (valid_packages, invalid_packages)
        """
        if auth_config is None:
            auth_config = {}
        
        valid_packages = []
        invalid_packages = []
        
        print(f"\nValidating {len(packages_with_versions)} {ecosystem} packages...")
        
        for i, pkg_info in enumerate(packages_with_versions, 1):
            if ecosystem == 'npm':
                # Take first version to validate
                version = pkg_info['versions'][0] if pkg_info['versions'] else 'latest'
                result = self.validate_npm_package(
                    package_name=pkg_info['name'],
                    version=version,
                    registry_url=registry_url,
                    auth_token=auth_config.get('npm_token'),
                    username=auth_config.get('npm_username'),
                    password=auth_config.get('npm_password')
                )
            elif ecosystem == 'pypi':
                version = pkg_info['versions'][0] if pkg_info['versions'] else '1.0.0'
                result = self.validate_pypi_package(
                    package_name=pkg_info['name'],
                    version=version,
                    registry_url=registry_url,
                    auth_token=auth_config.get('pypi_token'),
                    username=auth_config.get('pypi_username'),
                    password=auth_config.get('pypi_password')
                )
            elif ecosystem == 'maven':
                version = pkg_info['versions'][0] if pkg_info['versions'] else '1.0.0'
                coords = pkg_info['name'].split(':')
                if len(coords) != 2:
                    invalid_packages.append(pkg_info)
                    continue
                
                result = self.validate_maven_package(
                    group_id=coords[0],
                    artifact_id=coords[1],
                    version=version,
                    registry_url=registry_url,
                    username=auth_config.get('maven_username'),
                    password=auth_config.get('maven_password')
                )
            else:
                continue
            
            # Store validation result in package info
            pkg_info['validation'] = result
            
            # Categorize as valid or invalid
            if result['metadata_valid'] and result['download_valid']:
                valid_packages.append(pkg_info)
            else:
                invalid_packages.append(pkg_info)
            
            if self.verbose and i % 10 == 0:
                print(f"  {ecosystem}: {i}/{len(packages_with_versions)} validated")
        
        print(f"  ✓ Valid packages: {len(valid_packages)}")
        print(f"  ✗ Invalid packages: {len(invalid_packages)}")
        
        return valid_packages, invalid_packages
