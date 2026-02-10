#!/usr/bin/env python3
"""Debug script to compare PyPI request headers between curl and Python requests."""

import requests
import base64
import sys
from urllib.parse import urlparse

def test_pypi_request(url, username, password, verbose=True):
    """
    Test PyPI metadata request and show all request/response headers.
    
    Args:
        url: Full URL to test (e.g., https://artifactory.example.com/artifactory/api/pypi/pypi-remote/pypi/joblib/json)
        username: Username for basic auth
        password: Password for basic auth
        verbose: Print detailed information
    """
    
    # Prepare headers matching curl as closely as possible
    headers_options = {
        'standard_pip': {
            'User-Agent': 'pip/23.0 CPython/3.11.0',
            'Accept': 'application/json'
        },
        'curl_like': {
            'User-Agent': 'curl/8.13.0',
            'Accept': '*/*'
        },
        'minimal': {
            'Accept': '*/*'
        }
    }
    
    # Encode credentials
    credentials = base64.b64encode(f'{username}:{password}'.encode()).decode()
    auth_header = f'Basic {credentials}'
    
    print("=" * 80)
    print(f"Testing URL: {url}")
    print(f"Username: {username}")
    print(f"Password: {'*' * len(password)}")
    print("=" * 80)
    print()
    
    # Parse URL to get host
    parsed = urlparse(url)
    
    for header_name, base_headers in headers_options.items():
        print(f"\n{'=' * 80}")
        print(f"Test: {header_name.upper()} headers")
        print(f"{'=' * 80}")
        
        # Add authorization
        headers = base_headers.copy()
        headers['Authorization'] = auth_header
        
        # Explicitly set Host header (some servers require this)
        headers['Host'] = parsed.netloc.split(':')[0]  # Without port
        
        print("\nRequest Headers:")
        for key, value in headers.items():
            if key == 'Authorization':
                print(f"  {key}: Basic <redacted>")
            else:
                print(f"  {key}: {value}")
        
        try:
            # Make request with explicit headers
            print(f"\nSending GET request to {url}")
            response = requests.get(
                url, 
                headers=headers,
                timeout=30,
                verify=True  # Change to False if using self-signed certs
            )
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Reason: {response.reason}")
            
            print("\nResponse Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            
            if response.status_code == 401:
                print("\n⚠️  401 UNAUTHORIZED - Authentication failed")
                print("Response body:")
                print(response.text[:500])
            elif response.status_code == 404:
                print("\n✓ Authentication successful (404 means package not found, auth worked)")
            elif response.status_code == 200:
                print("\n✓ SUCCESS")
                print("Response preview:")
                print(response.text[:200])
            else:
                print(f"\nResponse body preview:")
                print(response.text[:500])
                
        except requests.exceptions.SSLError as e:
            print(f"\n❌ SSL Error: {e}")
            print("Try running with verify=False or fix SSL certificates")
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
    
    # Additional debug: Show what requests library actually sends
    print(f"\n\n{'=' * 80}")
    print("DEBUGGING: Actual request sent by requests library")
    print(f"{'=' * 80}")
    
    # Use a hook to capture the actual request
    def print_request(r, *args, **kwargs):
        print("\nActual request headers sent:")
        for key, value in r.headers.items():
            if key.lower() == 'authorization':
                print(f"  {key}: Basic <redacted>")
            else:
                print(f"  {key}: {value}")
    
    headers = {
        'User-Agent': 'pip/23.0 CPython/3.11.0',
        'Accept': 'application/json',
        'Authorization': auth_header
    }
    
    try:
        response = requests.get(
            url, 
            headers=headers,
            hooks={'response': print_request},
            timeout=30
        )
        print(f"\nFinal Status: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python debug_pypi_headers.py <url> <username> <password>")
        print()
        print("Example:")
        print("  python debug_pypi_headers.py \\")
        print('    "https://artifactory.example.com/artifactory/api/pypi/pypi-remote/pypi/joblib/json" \\')
        print('    "myuser" \\')
        print('    "your-password"')
        sys.exit(1)
    
    url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    test_pypi_request(url, username, password)
    
    print("\n" + "=" * 80)
    print("COMPARISON WITH CURL")
    print("=" * 80)
    print("\nYour working curl command uses:")
    print("  User-Agent: curl/8.13.0")
    print("  Accept: */*")
    print("  Authorization: Basic <credentials>")
    print()
    print("If one of the tests above works but others don't,")
    print("update the headers in metadata_fetcher.py to match the working ones.")


if __name__ == '__main__':
    main()
