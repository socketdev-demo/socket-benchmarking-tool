"""Metadata fetcher for package registries.

This module fetches package metadata (versions, download URLs) from upstream
registries and caches them to files for reuse in load tests.
"""

import json
import os
import sys
import requests
import warnings
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .package_validator import PackageValidator

# Suppress SSL warnings when verification is disabled
from urllib3.exceptions import InsecureRequestWarning


class MetadataFetcher:
    """Fetches and caches package metadata from registries."""
    
    def __init__(self, output_dir: str = "./metadata-cache", verify_ssl: bool = True):
        """Initialize metadata fetcher.
        
        Args:
            output_dir: Directory to store metadata cache files
            verify_ssl: Whether to verify SSL certificates (False for self-signed certs)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verify_ssl = verify_ssl
        self.validator = PackageValidator(verify_ssl=verify_ssl)
        
        # Suppress SSL warnings if verification is disabled
        if not verify_ssl:
            warnings.filterwarnings('ignore', category=InsecureRequestWarning)
        
    def get_cache_filename(self, ecosystem: str) -> Path:
        """Get the cache filename for an ecosystem.
        
        Args:
            ecosystem: Ecosystem name (npm, pypi, maven)
            
        Returns:
            Path to the cache file
        """
        return self.output_dir / f"repeat_file_{ecosystem}.json"
    
    def fetch_npm_metadata(
        self,
        packages: List[str],
        registry_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_versions: int = 5,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch metadata for npm packages.
        
        Args:
            packages: List of package names
            registry_url: Base URL of npm registry
            auth_token: Bearer token for authentication
            username: Username for basic auth
            password: Password for basic auth
            max_versions: Maximum number of versions to fetch per package
            verbose: Enable verbose output
            
        Returns:
            List of package metadata dictionaries
        """
        metadata = []
        registry_url = registry_url.rstrip('/')
        
        headers = {
            'User-Agent': 'npm/10.0.0 node/v20.0.0',
            'Accept': 'application/json'
        }
        
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        elif username and password:
            from base64 import b64encode
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        print(f"\nFetching metadata for {len(packages)} npm packages...")
        
        for i, pkg in enumerate(packages, 1):
            try:
                url = f"{registry_url}/{pkg}"
                response = requests.get(url, headers=headers, timeout=30, verify=self.verify_ssl)
                
                if response.status_code == 200:
                    data = response.json()
                    versions = list(data.get('versions', {}).keys())[:max_versions]
                    
                    if not versions:
                        versions = ['latest']
                    
                    metadata.append({
                        'name': pkg,
                        'versions': versions
                    })
                    
                    if verbose and i % 20 == 0:
                        print(f"  npm: {i}/{len(packages)} packages fetched")
                else:
                    # Use fallback
                    metadata.append({
                        'name': pkg,
                        'versions': ['latest']
                    })
                    if verbose:
                        print(f"  Warning: Could not fetch {pkg} (status {response.status_code})")
                        
            except Exception as e:
                # Use fallback
                metadata.append({
                    'name': pkg,
                    'versions': ['latest']
                })
                if verbose:
                    print(f"  Warning: Error fetching {pkg}: {e}")
        
        print(f"  ✓ Fetched metadata for {len(metadata)} npm packages")
        return metadata
    
    def fetch_pypi_metadata(
        self,
        packages: List[str],
        registry_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_versions: int = 5,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch metadata for PyPI packages.
        
        Args:
            packages: List of package names
            registry_url: Base URL of PyPI registry
            auth_token: Token for authentication
            username: Username for basic auth
            password: Password for basic auth
            max_versions: Maximum number of versions to fetch per package
            verbose: Enable verbose output
            
        Returns:
            List of package metadata dictionaries
        """
        metadata = []
        registry_url = registry_url.rstrip('/')
        
        # Use Accept: */* to match curl behavior (some registries like Artifactory are strict)
        headers = {
            'User-Agent': 'pip/23.0 CPython/3.11.0',
            'Accept': '*/*'  # Changed from 'application/json' to match curl
        }
        
        if auth_token:
            from base64 import b64encode
            credentials = b64encode(f'__token__:{auth_token}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        elif username and password:
            from base64 import b64encode
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        print(f"\nFetching metadata for {len(packages)} PyPI packages...")
        
        for i, pkg in enumerate(packages, 1):
            try:
                url = f"{registry_url}/pypi/{pkg}/json"
                
                if verbose:
                    print(f"  Requesting: {url}")
                    print(f"  Headers: {', '.join(f'{k}: {v[:10]}...' if k == 'Authorization' else f'{k}: {v}' for k, v in headers.items())}")
                
                response = requests.get(url, headers=headers, timeout=30, verify=self.verify_ssl)
                
                if verbose:
                    print(f"  Response: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    all_versions = list(data.get('releases', {}).keys())
                    versions = all_versions[-max_versions:] if len(all_versions) > max_versions else all_versions
                    
                    if not versions:
                        versions = ['1.0.0']
                    
                    metadata.append({
                        'name': pkg,
                        'versions': versions
                    })
                    
                    if verbose and i % 20 == 0:
                        print(f"  pypi: {i}/{len(packages)} packages fetched")
                else:
                    # Use fallback
                    metadata.append({
                        'name': pkg,
                        'versions': ['1.0.0']
                    })
                    if verbose:
                        print(f"  Warning: Could not fetch {pkg} (status {response.status_code})")
                        
            except Exception as e:
                # Use fallback
                metadata.append({
                    'name': pkg,
                    'versions': ['1.0.0']
                })
                if verbose:
                    print(f"  Warning: Error fetching {pkg}: {e}")
        
        print(f"  ✓ Fetched metadata for {len(metadata)} PyPI packages")
        return metadata
    
    def fetch_maven_metadata(
        self,
        packages: List[str],
        registry_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_versions: int = 5,
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch metadata for Maven packages.
        
        Args:
            packages: List of package coordinates (group:artifact format)
            registry_url: Base URL of Maven registry
            username: Username for basic auth
            password: Password for basic auth
            max_versions: Maximum number of versions to fetch per package
            verbose: Enable verbose output
            
        Returns:
            List of package metadata dictionaries
        """
        metadata = []
        registry_url = registry_url.rstrip('/')
        
        headers = {
            'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
            'Accept': 'application/xml'
        }
        
        if username and password:
            from base64 import b64encode
            credentials = b64encode(f'{username}:{password}'.encode()).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        print(f"\nFetching metadata for {len(packages)} Maven packages...")
        
        for i, coords in enumerate(packages, 1):
            try:
                # Parse group:artifact
                parts = coords.split(':')
                if len(parts) != 2:
                    raise ValueError(f"Invalid Maven coordinates: {coords}")
                
                group, artifact = parts
                group_path = group.replace('.', '/')
                
                # Fetch maven-metadata.xml
                url = f"{registry_url}/{group_path}/{artifact}/maven-metadata.xml"
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    # Parse XML to extract versions
                    import re
                    version_matches = re.findall(r'<version>([^<]+)</version>', response.text)
                    versions = version_matches[-max_versions:] if len(version_matches) > max_versions else version_matches
                    
                    if not versions:
                        versions = ['1.0.0']
                    
                    metadata.append({
                        'group': group,
                        'artifact': artifact,
                        'versions': versions
                    })
                    
                    if verbose and i % 20 == 0:
                        print(f"  maven: {i}/{len(packages)} packages fetched")
                else:
                    # Use fallback
                    metadata.append({
                        'group': group,
                        'artifact': artifact,
                        'versions': ['1.0.0']
                    })
                    if verbose:
                        print(f"  Warning: Could not fetch {coords} (status {response.status_code})")
                        
            except Exception as e:
                # Use fallback
                try:
                    group, artifact = coords.split(':')
                    metadata.append({
                        'group': group,
                        'artifact': artifact,
                        'versions': ['1.0.0']
                    })
                except:
                    pass
                
                if verbose:
                    print(f"  Warning: Error fetching {coords}: {e}")
        
        print(f"  ✓ Fetched metadata for {len(metadata)} Maven packages")
        return metadata
    
    def save_metadata(
        self,
        ecosystem: str,
        metadata: List[Dict[str, Any]],
        test_config: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Save metadata to a cache file.
        
        Args:
            ecosystem: Ecosystem name (npm, pypi, maven)
            metadata: Package metadata to save
            test_config: Optional test configuration to include
            
        Returns:
            Path to the saved cache file
        """
        cache_file = self.get_cache_filename(ecosystem)
        
        cache_data = {
            'ecosystem': ecosystem,
            'timestamp': datetime.now().isoformat(),
            'package_count': len(metadata),
            'metadata': metadata
        }
        
        if test_config:
            cache_data['test_config'] = test_config
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"  ✓ Saved {ecosystem} metadata to {cache_file}")
        return cache_file
    
    def load_metadata(self, ecosystem: str) -> Optional[Dict[str, Any]]:
        """Load metadata from cache file.
        
        Args:
            ecosystem: Ecosystem name (npm, pypi, maven)
            
        Returns:
            Cached metadata dictionary or None if not found
        """
        cache_file = self.get_cache_filename(ecosystem)
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load cache file {cache_file}: {e}", file=sys.stderr)
            return None
    
    def fetch_and_cache_all(
        self,
        ecosystems: List[str],
        packages: Dict[str, List[str]],
        registry_urls: Dict[str, str],
        auth_config: Optional[Dict[str, Any]] = None,
        max_versions: int = 5,
        verbose: bool = False
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch and cache metadata for all ecosystems.
        
        Args:
            ecosystems: List of ecosystem names to fetch
            packages: Dictionary mapping ecosystem to package list
            registry_urls: Dictionary mapping ecosystem to registry URL
            auth_config: Optional authentication configuration
            max_versions: Maximum versions per package
            verbose: Enable verbose output
            
        Returns:
            Dictionary mapping ecosystem to metadata list
        """
        auth_config = auth_config or {}
        all_metadata = {}
        
        print("\n" + "=" * 60)
        print("FETCHING PACKAGE METADATA FROM REGISTRIES")
        print("=" * 60)
        
        for ecosystem in ecosystems:
            if ecosystem not in packages or not packages[ecosystem]:
                continue
            
            ecosystem_packages = packages[ecosystem]
            registry_url = registry_urls.get(ecosystem)
            
            if not registry_url:
                print(f"Warning: No registry URL for {ecosystem}, skipping")
                continue
            
            if ecosystem == 'npm':
                metadata = self.fetch_npm_metadata(
                    packages=ecosystem_packages,
                    registry_url=registry_url,
                    auth_token=auth_config.get('npm_token'),
                    username=auth_config.get('npm_username'),
                    password=auth_config.get('npm_password'),
                    max_versions=max_versions,
                    verbose=verbose
                )
            elif ecosystem == 'pypi':
                metadata = self.fetch_pypi_metadata(
                    packages=ecosystem_packages,
                    registry_url=registry_url,
                    auth_token=auth_config.get('pypi_token'),
                    username=auth_config.get('pypi_username'),
                    password=auth_config.get('pypi_password'),
                    max_versions=max_versions,
                    verbose=verbose
                )
            elif ecosystem == 'maven':
                metadata = self.fetch_maven_metadata(
                    packages=ecosystem_packages,
                    registry_url=registry_url,
                    username=auth_config.get('maven_username'),
                    password=auth_config.get('maven_password'),
                    max_versions=max_versions,
                    verbose=verbose
                )
            else:
                print(f"Warning: Unknown ecosystem {ecosystem}, skipping")
                continue
            
            all_metadata[ecosystem] = metadata
            self.save_metadata(ecosystem, metadata)
        
        print("\n" + "=" * 60)
        print("METADATA FETCH COMPLETE")
        print("=" * 60)
        
        return all_metadata
    
    def validate_and_cache_packages(
        self,
        ecosystems: List[str],
        metadata: Dict[str, List[Dict[str, Any]]],
        registry_urls: Dict[str, str],
        auth_config: Optional[Dict[str, Any]] = None,
        verbose: bool = False
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Validate packages and separate into valid and invalid.
        
        Args:
            ecosystems: List of ecosystem names
            metadata: Dictionary of metadata by ecosystem
            registry_urls: Dictionary mapping ecosystem to registry URL
            auth_config: Optional authentication configuration
            verbose: Enable verbose output
            
        Returns:
            Dictionary mapping ecosystem to {valid: [...], invalid: [...]}
        """
        auth_config = auth_config or {}
        validation_results = {}
        
        print("\n" + "=" * 60)
        print("VALIDATING PACKAGE DOWNLOADS")
        print("=" * 60)
        
        for ecosystem in ecosystems:
            if ecosystem not in metadata or not metadata[ecosystem]:
                continue
            
            registry_url = registry_urls.get(ecosystem)
            if not registry_url:
                print(f"Warning: No registry URL for {ecosystem}, skipping validation")
                continue
            
            # Validate packages
            valid, invalid = self.validator.validate_packages(
                ecosystem=ecosystem,
                packages_with_versions=metadata[ecosystem],
                registry_url=registry_url,
                auth_config=auth_config
            )
            
            validation_results[ecosystem] = {
                'valid': valid,
                'invalid': invalid
            }
            
            # Save validation results
            self.save_validation_results(ecosystem, validation_results[ecosystem])
        
        print("\n" + "=" * 60)
        print("VALIDATION COMPLETE")
        print("=" * 60)
        
        return validation_results
    
    def save_validation_results(
        self,
        ecosystem: str,
        results: Dict[str, List[Dict[str, Any]]]
    ) -> Path:
        """Save validation results to cache file.
        
        Args:
            ecosystem: Ecosystem name
            results: Validation results with 'valid' and 'invalid' keys
            
        Returns:
            Path to the cache file
        """
        cache_file = self.output_dir / f"validation_{ecosystem}.json"
        
        cache_data = {
            'ecosystem': ecosystem,
            'timestamp': datetime.now().isoformat(),
            'valid_count': len(results['valid']),
            'invalid_count': len(results['invalid']),
            'valid': results['valid'],
            'invalid': results['invalid']
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"  ✓ Saved {ecosystem} validation results to {cache_file}")
        return cache_file
    
    def load_validation_results(
        self,
        ecosystem: str
    ) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Load validation results from cache file.
        
        Args:
            ecosystem: Ecosystem name
            
        Returns:
            Validation results dictionary or None if not found
        """
        cache_file = self.output_dir / f"validation_{ecosystem}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    'valid': data.get('valid', []),
                    'invalid': data.get('invalid', [])
                }
        except Exception as e:
            print(f"Warning: Could not load validation file {cache_file}: {e}", file=sys.stderr)
            return None
