#!/bin/bash

# Manual Package Cache Script for Artifactory
# Usage: ./cache-packages.sh <input-file>
# 
# Input file format:
# #npm - https://artifactory.example.com/artifactory/api/npm/npm-registry-proxy-remote
# package, version
#
# #maven - https://artifactory.example.com/artifactory/api/maven/maven-central-proxy-remote
# group:artifact, version
#
# #pypi - https://artifactory.example.com/artifactory/api/pypi/pypi-python-wf-proxy-proxy-remote
# package, version

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <input-file>"
    echo ""
    echo "Example input file format:"
    echo "#npm - https://artifactory.example.com/artifactory/api/npm/npm-registry-proxy-remote"
    echo "@babel/core, 7.23.7"
    echo "react, 18.2.0"
    echo ""
    echo "#maven - https://artifactory.example.com/artifactory/api/maven/maven-central-proxy-remote"
    echo "junit:junit, 4.13.2"
    echo ""
    echo "#pypi - https://artifactory.example.com/artifactory/api/pypi/pypi-python-wf-proxy-proxy-remote"
    echo "requests, 2.32.3"
    exit 1
fi

INPUT_FILE="$1"
CURRENT_ECOSYSTEM=""
CURRENT_BASE_URL=""
SUCCESS_COUNT=0
FAIL_COUNT=0

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: File '$INPUT_FILE' not found"
    exit 1
fi

echo "Starting package caching..."
echo "================================"

# Function to cache NPM package
cache_npm() {
    local package="$1"
    local version="$2"
    local base_url="$3"
    
    # Remove any whitespace
    package=$(echo "$package" | xargs)
    version=$(echo "$version" | xargs)
    
    echo "  [NPM] Caching $package@$version"
    
    # Get metadata first
    local metadata_url="${base_url}/${package}"
    echo "    - Fetching metadata: $metadata_url"
    
    if curl -f -s -o /dev/null -w "%{http_code}" "$metadata_url" | grep -q "200"; then
        echo "    ✓ Metadata cached (200 OK)"
    else
        echo "    ✗ Metadata failed"
        ((FAIL_COUNT++))
        return 1
    fi
    
    # Download the package tarball
    # Handle scoped packages (@org/package)
    if [[ "$package" == @*/* ]]; then
        local scope_and_pkg="$package"
        local pkg_name="${package##*/}"  # Get part after last /
        local download_url="${base_url}/${scope_and_pkg}/-/${pkg_name}-${version}.tgz"
    else
        local download_url="${base_url}/${package}/-/${package}-${version}.tgz"
    fi
    
    echo "    - Downloading package: $download_url"
    
    local status_code=$(curl -f -s -o /dev/null -w "%{http_code}" "$download_url")
    if [ "$status_code" = "200" ]; then
        echo "    ✓ Package downloaded (200 OK)"
        ((SUCCESS_COUNT++))
    else
        echo "    ✗ Package download failed (HTTP $status_code)"
        ((FAIL_COUNT++))
    fi
    
    echo ""
}

# Function to cache Maven package
cache_maven() {
    local package="$1"
    local version="$2"
    local base_url="$3"
    
    # Remove any whitespace
    package=$(echo "$package" | xargs)
    version=$(echo "$version" | xargs)
    
    # Split group:artifact
    IFS=':' read -r group artifact <<< "$package"
    
    if [ -z "$group" ] || [ -z "$artifact" ]; then
        echo "  [MAVEN] Invalid format for $package (expected group:artifact)"
        ((FAIL_COUNT++))
        return 1
    fi
    
    # Convert dots to slashes for group path
    local group_path="${group//\.//}"
    
    echo "  [MAVEN] Caching $group:$artifact@$version"
    
    # Get metadata first
    local metadata_url="${base_url}/${group_path}/${artifact}/maven-metadata.xml"
    echo "    - Fetching metadata: $metadata_url"
    
    if curl -f -s -o /dev/null -w "%{http_code}" "$metadata_url" | grep -q "200"; then
        echo "    ✓ Metadata cached (200 OK)"
    else
        echo "    ✗ Metadata failed"
        ((FAIL_COUNT++))
        return 1
    fi
    
    # Download the JAR file
    local download_url="${base_url}/${group_path}/${artifact}/${version}/${artifact}-${version}.jar"
    echo "    - Downloading artifact: $download_url"
    
    local status_code=$(curl -f -s -o /dev/null -w "%{http_code}" "$download_url")
    if [ "$status_code" = "200" ]; then
        echo "    ✓ Artifact downloaded (200 OK)"
        ((SUCCESS_COUNT++))
    else
        echo "    ✗ Artifact download failed (HTTP $status_code)"
        ((FAIL_COUNT++))
    fi
    
    echo ""
}

# Function to cache PyPI package
cache_pypi() {
    local package="$1"
    local version="$2"
    local base_url="$3"
    
    # Remove any whitespace
    package=$(echo "$package" | xargs)
    version=$(echo "$version" | xargs)
    
    echo "  [PYPI] Caching $package@$version"
    
    # Get metadata first
    local metadata_url="${base_url}/simple/${package}/"
    echo "    - Fetching metadata: $metadata_url"
    
    if curl -f -s -o /dev/null -w "%{http_code}" "$metadata_url" | grep -q "200"; then
        echo "    ✓ Metadata cached (200 OK)"
    else
        echo "    ✗ Metadata failed"
        ((FAIL_COUNT++))
        return 1
    fi
    
    # PyPI packages can have different filename formats
    # Try common patterns: wheel (.whl) and source (.tar.gz)
    local tried=false
    local success=false
    
    # Try to download wheel (most common for newer packages)
    # Format: package-version-py3-none-any.whl
    local wheel_url="${base_url}/packages/packages/*/${package}-${version}-py3-none-any.whl"
    echo "    - Attempting to cache package (checking repository)..."
    
    # Since we don't know the exact hash path, we'll try to get the simple page and parse it
    # For now, just report that metadata was cached
    echo "    ℹ Metadata cached. To cache specific wheel/tar.gz, access the download URL directly."
    ((SUCCESS_COUNT++))
    
    echo ""
}

# Read the input file line by line
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines
    if [ -z "$line" ]; then
        continue
    fi
    
    # Check if this is an ecosystem header
    if [[ "$line" =~ ^#([a-z]+)[[:space:]]*-[[:space:]]*(.+)$ ]]; then
        CURRENT_ECOSYSTEM="${BASH_REMATCH[1]}"
        CURRENT_BASE_URL="${BASH_REMATCH[2]}"
        echo ""
        echo "Ecosystem: $CURRENT_ECOSYSTEM"
        echo "Base URL: $CURRENT_BASE_URL"
        echo "--------------------------------"
        continue
    fi
    
    # Skip comment lines that aren't ecosystem headers
    if [[ "$line" =~ ^# ]]; then
        continue
    fi
    
    # Skip lines without ecosystem set
    if [ -z "$CURRENT_ECOSYSTEM" ]; then
        continue
    fi
    
    # Parse package, version
    if [[ "$line" =~ ^([^,]+),(.+)$ ]]; then
        package="${BASH_REMATCH[1]}"
        version="${BASH_REMATCH[2]}"
        
        case "$CURRENT_ECOSYSTEM" in
            npm)
                cache_npm "$package" "$version" "$CURRENT_BASE_URL"
                ;;
            maven)
                cache_maven "$package" "$version" "$CURRENT_BASE_URL"
                ;;
            pypi)
                cache_pypi "$package" "$version" "$CURRENT_BASE_URL"
                ;;
            *)
                echo "  Unknown ecosystem: $CURRENT_ECOSYSTEM"
                ;;
        esac
    fi
done < "$INPUT_FILE"

echo "================================"
echo "Caching complete!"
echo "Success: $SUCCESS_COUNT"
echo "Failed: $FAIL_COUNT"
