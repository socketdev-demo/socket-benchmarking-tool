#!/usr/bin/env python3
"""Debug script to test Maven authentication.

This script helps diagnose Maven authentication issues by testing:
1. Metadata request (maven-metadata.xml)
2. Download request (.jar file)
3. With and without authentication headers
"""

import requests
import sys
from base64 import b64encode

def test_maven_auth(base_url, username, password, group, artifact, version):
    """Test Maven authentication for metadata and download requests."""
    
    print("="*70)
    print("MAVEN AUTHENTICATION DEBUG")
    print("="*70)
    print(f"Base URL: {base_url}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print(f"Package: {group}:{artifact}@{version}")
    print("="*70)
    
    # Construct URLs
    group_path = group.replace('.', '/')
    metadata_url = f"{base_url}/{group_path}/{artifact}/maven-metadata.xml"
    jar_url = f"{base_url}/{group_path}/{artifact}/{version}/{artifact}-{version}.jar"
    
    # Prepare auth headers
    credentials = b64encode(f'{username}:{password}'.encode()).decode()
    auth_headers = {
        'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
        'Accept': 'application/xml',
        'Authorization': f'Basic {credentials}'
    }
    
    no_auth_headers = {
        'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
        'Accept': 'application/xml'
    }
    
    print(f"\nAuth Header: Authorization: Basic {credentials[:20]}...")
    print("\n" + "="*70)
    
    # Test 1: Metadata request WITHOUT auth
    print("\n1. METADATA REQUEST (WITHOUT AUTH)")
    print(f"   URL: {metadata_url}")
    try:
        response = requests.get(metadata_url, headers=no_auth_headers, timeout=30, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Metadata request WITH auth
    print("\n2. METADATA REQUEST (WITH AUTH)")
    print(f"   URL: {metadata_url}")
    try:
        response = requests.get(metadata_url, headers=auth_headers, timeout=30, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✓ Success - metadata fetched")
        else:
            print(f"   ✗ Failed - Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: JAR download WITHOUT auth (HEAD request)
    print("\n3. JAR DOWNLOAD REQUEST (WITHOUT AUTH - HEAD)")
    print(f"   URL: {jar_url}")
    try:
        response = requests.head(jar_url, headers=no_auth_headers, timeout=30, allow_redirects=True, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code != 200:
            print(f"   Response: {response.text[:200] if response.text else 'No content'}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: JAR download WITH auth (HEAD request)
    print("\n4. JAR DOWNLOAD REQUEST (WITH AUTH - HEAD)")
    print(f"   URL: {jar_url}")
    try:
        response = requests.head(jar_url, headers=auth_headers, timeout=30, allow_redirects=True, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✓ Success - JAR exists")
            print(f"   Content-Length: {response.headers.get('Content-Length', 'unknown')}")
        else:
            print(f"   ✗ Failed")
            print(f"   Headers: {dict(response.headers)}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 5: JAR download WITH auth (GET request - first 100 bytes)
    print("\n5. JAR DOWNLOAD REQUEST (WITH AUTH - GET)")
    print(f"   URL: {jar_url}")
    try:
        response = requests.get(jar_url, headers=auth_headers, timeout=30, stream=True, verify=False)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            # Read first 100 bytes
            chunk = next(response.iter_content(100), None)
            if chunk:
                print(f"   ✓ Success - downloaded {len(chunk)} bytes")
            response.close()
        else:
            print(f"   ✗ Failed - Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "="*70)
    print("DIAGNOSIS COMPLETE")
    print("="*70)
    
    print("\nRECOMMENDATIONS:")
    print("- If metadata WITH auth succeeds but download fails:")
    print("  → Check if JAR URLs require different authentication")
    print("- If both fail with auth:")
    print("  → Verify credentials are correct")
    print("  → Check if IP/user is whitelisted")
    print("- If requests without auth return 401:")
    print("  → This is expected - authentication is required")
    print("- If some requests work and some don't:")
    print("  → May indicate redirect issues or path-specific auth rules")
    print("="*70)


if __name__ == '__main__':
    # Example usage
    if len(sys.argv) < 6:
        print("Usage: python debug_maven_auth.py <base_url> <username> <password> <group:artifact> <version>")
        print("\nExample:")
        print("  python debug_maven_auth.py \\")
        print("    https://nexus.example.com/repository/REPO_NAME \\")
        print("    myuser mypass \\")
        print("    commons-codec:commons-codec \\")
        print("    1.1")
        sys.exit(1)
    
    base_url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    coords = sys.argv[4]
    version = sys.argv[5]
    
    parts = coords.split(':')
    if len(parts) != 2:
        print(f"Error: Package must be in format 'group:artifact', got: {coords}")
        sys.exit(1)
    
    group, artifact = parts
    
    test_maven_auth(base_url, username, password, group, artifact, version)
