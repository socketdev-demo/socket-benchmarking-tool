"""Package validator for checking metadata and download availability.

This module validates packages by checking if metadata and downloads are available
and don't return 404 errors.
"""

import re
import requests
import warnings
from typing import Dict, List, Any, Optional, Tuple
from base64 import b64encode

# Suppress SSL warnings when verification is disabled
from urllib3.exceptions import InsecureRequestWarning


class PackageValidator:
    """Validates package metadata and download availability."""
    
    def __init__(self, timeout: int = 30, verbose: bool = False, verify_ssl: bool = True, max_version_attempts: int = 5):
        """Initialize package validator.
        
        Args:
            timeout: Request timeout in seconds
            verbose: Enable verbose output
            verify_ssl: Whether to verify SSL certificates (False for self-signed certs)
            max_version_attempts: Maximum number of versions to try per package until finding a valid one (default: 5)
        """
        self.timeout = timeout
        self.verbose = verbose
        self.verify_ssl = verify_ssl
        self.max_version_attempts = max_version_attempts
        
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
            'download_url': None,
            'metadata_url': None
        }
        
        # Check metadata
        try:
            metadata_url = f"{registry_url}/{package_name}"
            result['metadata_url'] = metadata_url
            
            if self.verbose:
                print(f"         Checking metadata: {metadata_url}")
            
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
                        
                        if self.verbose:
                            print(f"         Checking download: {tarball_url}")
                        
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
                                print(f"         Warning: Download check failed for {package_name}@{version}: {e}")
                            result['download_status'] = 0
            elif self.verbose:
                print(f"         Metadata check returned status {response.status_code}")
        except Exception as e:
            if self.verbose:
                print(f"         Warning: Metadata check failed for {package_name}: {e}")
            result['metadata_status'] = 0
        
        return result
    
    def validate_pypi_package(
        self,
        package_name: str,
        version: str,
        registry_url: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_json_api: bool = False
    ) -> Dict[str, Any]:
        """Validate PyPI package metadata and download.
        
        Args:
            package_name: Package name
            version: Package version
            registry_url: Base URL of PyPI registry
            auth_token: Token for authentication
            username: Username for basic auth
            password: Password for basic auth
            use_json_api: Use JSON API (/pypi/{package}/json) instead of Simple API (default: False)
            
        Returns:
            Dict with validation results
        """
        registry_url = registry_url.rstrip('/')
        
        # Use Accept: */* to match curl behavior (some registries like Artifactory are strict)
        headers = {
            'User-Agent': 'pip/23.0 CPython/3.11.0',
            'Accept': '*/*'
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
            'download_url': None,
            'metadata_url': None
        }
        
        # Check metadata
        try:
            if use_json_api:
                # Use JSON API: /pypi/{package}/json
                metadata_url = f"{registry_url}/pypi/{package_name}/json"
            else:
                # Use Simple API (PEP 503): /simple/{package}/
                metadata_url = f"{registry_url}/simple/{package_name}/"
            
            result['metadata_url'] = metadata_url
            
            if self.verbose:
                print(f"         Checking metadata: {metadata_url}")
            
            response = requests.get(metadata_url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            result['metadata_status'] = response.status_code
            
            if response.status_code == 200:
                # Check if it's a valid response or an HTML error page
                content_type = response.headers.get('Content-Type', '').lower()
                
                # For Simple API, validate it's actually HTML with package links, not an error page
                if not use_json_api:
                    # Check for common error indicators in HTML
                    html_lower = response.text.lower()
                    is_error_page = any([
                        '404' in html_lower and 'not found' in html_lower,
                        '404 not found' in html_lower,
                        'error' in html_lower and len(response.text) < 2000,  # Short error pages
                        '<title>404' in html_lower,
                        '<title>error' in html_lower,
                        'page not found' in html_lower,
                    ])
                    
                    if is_error_page:
                        if self.verbose:
                            print(f"         Server returned 200 but content appears to be an error page")
                        result['metadata_status'] = 404  # Treat as 404
                        result['metadata_valid'] = False
                
                if result.get('metadata_status') == 200:
                    result['metadata_valid'] = True
                
                if use_json_api and result['metadata_valid']:
                    # Parse JSON response
                    data = response.json()
                    releases = data.get('releases', {})
                    if version in releases and releases[version]:
                        # Get first wheel or source distribution URL
                        for file_info in releases[version]:
                            download_url = file_info.get('url')
                            if download_url:
                                result['download_url'] = download_url
                                
                                if self.verbose:
                                    print(f"         Checking download: {download_url}")
                                
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
                                        print(f"         Warning: Download check failed for {package_name}@{version}: {e}")
                                    result['download_status'] = 0
                elif result['metadata_valid']:
                    # Parse HTML Simple API response
                    html = response.text
                    
                    if self.verbose:
                        print(f"         Parsing Simple API response for {package_name}@{version}")
                        print(f"         HTML length: {len(html)} bytes")
                    
                    # Find download URLs for the specific version
                    # Simple API often has relative paths like: ../packages/flask/1.0.3/Flask-1.0.3.tar.gz
                    # Note: package names in URLs may have different capitalization than the package name
                    
                    # Look for any link containing a file matching package-version pattern
                    # Try multiple patterns to handle different naming conventions
                    patterns = [
                        # Pattern 1: Match by version in path: .../VERSION/packagename-VERSION.(tar.gz|whl)
                        rf'href="([^"#]*/{re.escape(version)}/[^"#]*?\.(?:tar\.gz|whl))',
                        # Pattern 2: Match filename pattern: packagename-version.(tar.gz|whl) anywhere
                        rf'href="([^"#]*{re.escape(package_name)}-{re.escape(version)}[^"#]*?\.(?:tar\.gz|whl))',
                        # Pattern 3: Single quotes version
                        rf"href='([^'#]*/{re.escape(version)}/[^'#]*?\.(?:tar\.gz|whl))'",
                        # Pattern 4: More lenient - just find href with version in filename
                        rf'href=["\']?([^"\'>\\s#]*-{re.escape(version)}[^"\'>\\s#]*?\.(?:tar\.gz|whl))',
                    ]
                    
                    matches = None
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        if matches:
                            if self.verbose:
                                print(f"         Found {len(matches)} matches with pattern")
                            break
                    
                    if not matches:
                        # Try even more lenient: any .tar.gz or .whl file for this package
                        pattern = rf'{re.escape(package_name)}-[\d\.]+.*?\.(?:tar\.gz|whl)'
                        filenames = re.findall(pattern, html, re.IGNORECASE)
                        if filenames and self.verbose:
                            print(f"         Found filenames but no download URLs: {filenames[:3]}")
                            print(f"         Attempting to construct URLs from filenames...")
                        # Try to find hrefs near these filenames
                        for filename in filenames[:1]:  # Just try the first one
                            href_pattern = rf'href=["\']?([^"\'>\s]*{re.escape(filename)}[^"\'>\s]*)'
                            href_matches = re.findall(href_pattern, html, re.IGNORECASE)
                            if href_matches:
                                matches = href_matches
                                break
                    
                    if matches:
                        # Get the first match
                        download_path = matches[0] if isinstance(matches[0], str) else matches[0][0] if isinstance(matches[0], tuple) else str(matches[0])
                        
                        if self.verbose:
                            print(f"         Download path from HTML: {download_path}")
                        
                        # Construct full URL from relative path
                        if download_path.startswith('http'):
                            download_url = download_path
                        elif download_path.startswith('/'):
                            # Absolute path on same server
                            from urllib.parse import urlparse
                            parsed = urlparse(registry_url)
                            download_url = f"{parsed.scheme}://{parsed.netloc}{download_path}"
                        elif download_path.startswith('../'):
                            # Relative path going up - resolve relative to the simple API URL
                            # /repository/pypi/simple/flask/ + ../packages/... = /repository/pypi/packages/...
                            from urllib.parse import urljoin
                            download_url = urljoin(metadata_url, download_path)
                        else:
                            # Relative path in same directory
                            download_url = f"{metadata_url.rstrip('/')}/{download_path}"
                        
                        result['download_url'] = download_url
                        
                        if self.verbose:
                            print(f"         Checking download: {download_url}")
                        
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
                        except Exception as e:
                            if self.verbose:
                                print(f"         Warning: Download check failed for {package_name}@{version}: {e}")
                            result['download_status'] = 0
                    else:
                        if self.verbose:
                            print(f"         Warning: No download URLs found for {package_name}@{version}")
                            # Show a snippet of the HTML for debugging
                            snippet = html[:500] if len(html) > 500 else html
                            print(f"         HTML snippet: {snippet}...")
                        # download_url remains None, no download validation possible
            elif self.verbose:
                print(f"         Metadata check returned status {response.status_code}")
        except Exception as e:
            if self.verbose:
                print(f"         Warning: Metadata check failed for {package_name}: {e}")
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
            'download_url': None,
            'metadata_url': None
        }
        
        # Check maven-metadata.xml
        try:
            group_path = group_id.replace('.', '/')
            metadata_url = f"{registry_url}/{group_path}/{artifact_id}/maven-metadata.xml"
            result['metadata_url'] = metadata_url
            
            if self.verbose:
                print(f"         Checking metadata: {metadata_url}")
            
            response = requests.get(metadata_url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            result['metadata_status'] = response.status_code
            
            if response.status_code == 200:
                result['metadata_valid'] = True
                
                # Check download (JAR file)
                jar_url = f"{registry_url}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
                result['download_url'] = jar_url
                
                if self.verbose:
                    print(f"         Checking download: {jar_url}")
                
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
                        print(f"         Warning: Download check failed for {group_id}:{artifact_id}@{version}: {e}")
                    result['download_status'] = 0
            elif self.verbose:
                print(f"         Metadata check returned status {response.status_code}")
        except Exception as e:
            if self.verbose:
                print(f"         Warning: Metadata check failed for {group_id}:{artifact_id}: {e}")
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
        print(f"Max version attempts per package: {self.max_version_attempts}")
        
        for i, pkg_info in enumerate(packages_with_versions, 1):
            result = None
            versions_to_try = pkg_info.get('versions', [])[:self.max_version_attempts]
            
            if ecosystem == 'npm':
                pkg_name = pkg_info['name']
                
                if not versions_to_try:
                    versions_to_try = ['latest']
                
                if self.verbose:
                    print(f"  [{i}/{len(packages_with_versions)}] Validating {pkg_name} (trying up to {len(versions_to_try)} versions)...")
                
                # Try versions until we find a valid one
                for attempt, version in enumerate(versions_to_try, 1):
                    if self.verbose and len(versions_to_try) > 1:
                        print(f"      Attempt {attempt}/{len(versions_to_try)}: {pkg_name}@{version}")
                    
                    result = self.validate_npm_package(
                        package_name=pkg_name,
                        version=version,
                        registry_url=registry_url,
                        auth_token=auth_config.get('npm_token'),
                        username=auth_config.get('npm_username'),
                        password=auth_config.get('npm_password')
                    )
                    
                    # If both metadata and download are valid, we found a good version
                    if result['metadata_valid'] and result['download_valid']:
                        if self.verbose and len(versions_to_try) > 1:
                            print(f"      ✓ Found valid version: {version}")
                        break
                    elif self.verbose and len(versions_to_try) > 1:
                        print(f"      ✗ Version {version} failed validation")
                
            elif ecosystem == 'pypi':
                pkg_name = pkg_info['name']
                
                if not versions_to_try:
                    versions_to_try = ['1.0.0']
                
                if self.verbose:
                    print(f"  [{i}/{len(packages_with_versions)}] Validating {pkg_name} (trying up to {len(versions_to_try)} versions)...")
                
                # Try versions until we find a valid one
                for attempt, version in enumerate(versions_to_try, 1):
                    if self.verbose and len(versions_to_try) > 1:
                        print(f"      Attempt {attempt}/{len(versions_to_try)}: {pkg_name}=={version}")
                    
                    result = self.validate_pypi_package(
                        package_name=pkg_name,
                        version=version,
                        registry_url=registry_url,
                        auth_token=auth_config.get('pypi_token'),
                        username=auth_config.get('pypi_username'),
                        password=auth_config.get('pypi_password')
                    )
                    
                    # If both metadata and download are valid, we found a good version
                    if result['metadata_valid'] and result['download_valid']:
                        if self.verbose and len(versions_to_try) > 1:
                            print(f"      ✓ Found valid version: {version}")
                        break
                    elif self.verbose and len(versions_to_try) > 1:
                        print(f"      ✗ Version {version} failed validation")
                
            elif ecosystem == 'maven':
                # Maven metadata uses 'group' and 'artifact' keys
                group_id = pkg_info.get('group', '')
                artifact_id = pkg_info.get('artifact', '')
                
                if not group_id or not artifact_id:
                    invalid_packages.append(pkg_info)
                    continue
                
                pkg_name = f"{group_id}:{artifact_id}"
                
                if not versions_to_try:
                    versions_to_try = ['1.0.0']
                
                if self.verbose:
                    print(f"  [{i}/{len(packages_with_versions)}] Validating {pkg_name} (trying up to {len(versions_to_try)} versions)...")
                
                # Try versions until we find a valid one
                for attempt, version in enumerate(versions_to_try, 1):
                    if self.verbose and len(versions_to_try) > 1:
                        print(f"      Attempt {attempt}/{len(versions_to_try)}: {pkg_name}:{version}")
                    
                    result = self.validate_maven_package(
                        group_id=group_id,
                        artifact_id=artifact_id,
                        version=version,
                        registry_url=registry_url,
                        username=auth_config.get('maven_username'),
                        password=auth_config.get('maven_password')
                    )
                    
                    # If both metadata and download are valid, we found a good version
                    if result['metadata_valid'] and result['download_valid']:
                        if self.verbose and len(versions_to_try) > 1:
                            print(f"      ✓ Found valid version: {version}")
                        break
                    elif self.verbose and len(versions_to_try) > 1:
                        print(f"      ✗ Version {version} failed validation")
            else:
                continue
            
            # If no result was set (unsupported ecosystem), skip this package
            if result is None:
                continue
            
            # Store validation result in package info
            pkg_info['validation'] = result
            
            # Categorize as valid or invalid
            if result['metadata_valid'] and result['download_valid']:
                valid_packages.append(pkg_info)
                if self.verbose:
                    pkg_name = result.get('package', 'unknown')
                    print(f"      ✓ {pkg_name} validated successfully")
            else:
                invalid_packages.append(pkg_info)
                # Show details of validation failure in verbose mode
                pkg_name = result.get('package', 'unknown')
                metadata_url = result.get('metadata_url')
                if not result['metadata_valid']:
                    status = result.get('metadata_status', 'unknown')
                    print(f"      ✗ {pkg_name}: metadata failed (status {status})")
                    if self.verbose and metadata_url:
                        print(f"         URL: {metadata_url}")
                elif not result['download_valid']:
                    status = result.get('download_status', 'unknown')
                    download_url = result.get('download_url', 'N/A')
                    print(f"      ✗ {pkg_name}: download failed (status {status})")
                    if self.verbose and download_url != 'N/A':
                        print(f"         URL: {download_url}")
            
            if not self.verbose and i % 10 == 0:
                print(f"  {ecosystem}: {i}/{len(packages_with_versions)} validated")
        
        print(f"  ✓ Valid packages: {len(valid_packages)}")
        print(f"  ✗ Invalid packages: {len(invalid_packages)}")
        
        return valid_packages, invalid_packages
