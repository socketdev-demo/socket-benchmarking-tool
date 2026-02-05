# Private Registry Authentication Guide

This guide explains how to configure authentication for private npm, PyPI, and Maven registries in the Socket Firewall Load Test framework.

## Authentication Methods

**Important:** This framework uses the standard authentication methods for each ecosystem:

| Ecosystem | Method | Authorization Header Format |
|-----------|--------|---------------------------|
| **npm** | Bearer Token | `Bearer YOUR_TOKEN` for tokens<br>`Basic base64(username:password)` for credentials |
| **PyPI** | Basic Auth | `Basic base64(__token__:YOUR_TOKEN)` for tokens<br>`Basic base64(username:password)` for credentials |
| **Maven** | Basic Auth | `Basic base64(username:password)` only |

**Note:** NPM uses Bearer token authentication while PyPI and Maven use Basic authentication.

## Quick Start

### NPM with Bearer Token

```bash
export NPM_TOKEN="your-npm-token-value"
socket-load-test test \
  --rps 1000 \
  --duration 5m \
  --ecosystems npm \
  --npm-url "https://npm.private.com" \
  --npm-token "${NPM_TOKEN}" \
  --no-docker
```

**How it works:** The token is automatically formatted as `Authorization: Bearer YOUR_TOKEN`

### PyPI with Token

```bash
export PYPI_TOKEN="pypi-your-token-value"
socket-load-test test \
  --rps 1000 \
  --duration 5m \
  --ecosystems pypi \
  --pypi-url "https://pypi.private.com" \
  --pypi-token "${PYPI_TOKEN}" \
  --no-docker
```

**How it works:** The token is automatically formatted as `Authorization: Basic base64(__token__:YOUR_TOKEN)`

### Maven with Basic Auth

```bash
export MAVEN_USERNAME="maven-user"
export MAVEN_PASSWORD="maven-pass"
socket-load-test test \
  --rps 1000 \
  --duration 5m \
  --ecosystems maven \
  --maven-url "https://maven.private.com" \
  --maven-username "${MAVEN_USERNAME}" \
  --maven-password "${MAVEN_PASSWORD}" \
  --no-docker
```

### All Ecosystems with Mixed Auth

```bash
# Set credentials
export NPM_TOKEN="npm_token_value"
export PYPI_TOKEN="pypi-token-value"
export MAVEN_USERNAME="maven-user"
export MAVEN_PASSWORD="maven-pass"

# Run test
socket-load-test test \
  --rps 5000 \
  --duration 10m \
  --ecosystems npm,pypi,maven \
  --npm-url "https://npm.private.com" \
  --npm-token "${NPM_TOKEN}" \
  --pypi-url "https://pypi.private.com" \
  --pypi-token "${PYPI_TOKEN}" \
  --maven-url "https://maven.private.com" \
  --maven-username "${MAVEN_USERNAME}" \
  --maven-password "${MAVEN_PASSWORD}" \
  --no-docker
```

## Configuration File Examples

### Example 1: NPM Token Authentication

```yaml
# config-npm-token.yaml
test:
  rps: 2000
  duration: 10m
  test_id: npm-private-test

registries:
  npm_url: https://npm.private.company.com
  npm_token: ${NPM_TOKEN}
  ecosystems: ['npm']
  cache_hit_percent: 30

traffic:
  npm_ratio: 100
  metadata_only: false

results:
  output_dir: ./npm-test-results
  auto_generate_html: true
```

Run with:
```bash
export NPM_TOKEN="your-token"
socket-load-test test --config config-npm-token.yaml --no-docker
```

### Example 2: All Ecosystems with Authentication

```yaml
# config-all-auth.yaml
test:
  rps: 5000
  duration: 10m
  test_id: all-private-registries

registries:
  # Registry URLs
  npm_url: https://npm.private.company.com
  pypi_url: https://pypi.private.company.com
  maven_url: https://maven.private.company.com
  
  # NPM - Bearer Token
  npm_token: ${NPM_TOKEN}
  
  # PyPI - Basic Auth
  pypi_username: ${PYPI_USERNAME}
  pypi_password: ${PYPI_PASSWORD}
  
  # Maven - Basic Auth
  maven_username: ${MAVEN_USERNAME}
  maven_password: ${MAVEN_PASSWORD}
  
  # Configuration
  ecosystems: ['npm', 'pypi', 'maven']
  cache_hit_percent: 30

traffic:
  npm_ratio: 40
  pypi_ratio: 30
  maven_ratio: 30
  metadata_only: false

results:
  output_dir: ./private-registry-results
  auto_generate_html: true
```

Run with:
```bash
# Set environment variables
export NPM_TOKEN="your-npm-token"
export PYPI_USERNAME="pypi-user"
export PYPI_PASSWORD="pypi-pass"
export MAVEN_USERNAME="maven-user"
export MAVEN_PASSWORD="maven-pass"

# Run test
socket-load-test test --config config-all-auth.yaml --no-docker
```

### Example 3: Using Base URL with Authentication

```yaml
# config-base-url-auth.yaml
test:
  rps: 3000
  duration: 5m

registries:
  # Single base URL with paths
  base_url: https://firewall.company.com
  npm_path: /npm
  pypi_path: /simple
  maven_path: /maven2
  
  # Authentication (same for all)
  npm_username: ${REGISTRY_USERNAME}
  npm_password: ${REGISTRY_PASSWORD}
  pypi_username: ${REGISTRY_USERNAME}
  pypi_password: ${REGISTRY_PASSWORD}
  maven_username: ${REGISTRY_USERNAME}
  maven_password: ${REGISTRY_PASSWORD}
  
  ecosystems: ['npm', 'pypi', 'maven']

traffic:
  npm_ratio: 33
  pypi_ratio: 33
  maven_ratio: 34
```

## Authentication Methods

### NPM Registry

**Method 1: Bearer Token (Recommended)**
- Most secure
- Used by npm v7+ 
- Set via `--npm-token` or `npm_token` in config

**Method 2: Basic Authentication**
- Compatible with older registries
- Set via `--npm-username` and `--npm-password`
- Automatically base64 encoded in requests

### PyPI Registry

**Method 1: Bearer Token**
- Modern PyPI registries support this
- Set via `--pypi-token` or `pypi_token` in config

**Method 2: Basic Authentication (Common)**
- Most PyPI registries use this
- Set via `--pypi-username` and `--pypi-password`
- Automatically base64 encoded in requests

### Maven Registry

**Only supports Basic Authentication**
- Set via `--maven-username` and `--maven-password`
- Standard for Maven repositories
- Automatically base64 encoded in requests

## Security Best Practices

1. **Never commit credentials to version control**
   ```yaml
   # ✅ GOOD - Use environment variables
   npm_token: ${NPM_TOKEN}
   
   # ❌ BAD - Hardcoded credentials
   npm_token: "hardcoded-token-123"
   ```

2. **Use read-only tokens for load testing**
   - Limit token permissions to package download only
   - Don't use publish or admin tokens

3. **Rotate credentials regularly**
   - Change tokens/passwords on a regular schedule
   - Use temporary tokens for testing when possible

4. **Use a secrets manager in production**
   ```bash
   # Example with AWS Secrets Manager
   export NPM_TOKEN=$(aws secretsmanager get-secret-value \
     --secret-id npm-load-test-token \
     --query SecretString \
     --output text)
   ```

5. **Review logs carefully**
   - Credentials are automatically filtered from logs
   - Still verify no accidental exposure

6. **Restrict network access**
   - Run load tests from trusted networks
   - Use VPN or private networks for sensitive registries

## Troubleshooting

### Authentication Failures

**401 Unauthorized Error:**
- Verify credentials are correct
- Check if token has expired
- Ensure environment variables are set correctly
- Try using basic auth instead of token (or vice versa)

**403 Forbidden Error:**
- Token/credentials may lack necessary permissions
- Ensure read access to packages
- Check registry firewall rules

**Verify Authentication:**
```bash
# Test NPM with token
curl -H "Authorization: Bearer ${NPM_TOKEN}" https://npm.private.com/express

# Test NPM with basic auth
curl -u "${NPM_USERNAME}:${NPM_PASSWORD}" https://npm.private.com/express

# Test PyPI with basic auth
curl -u "${PYPI_USERNAME}:${PYPI_PASSWORD}" https://pypi.private.com/simple/requests/

# Test Maven with basic auth
curl -u "${MAVEN_USERNAME}:${MAVEN_PASSWORD}" https://maven.private.com/maven2/
```

### Environment Variables Not Loading

**Check variable is set:**
```bash
echo $NPM_TOKEN  # Should show your token
```

**Export in your shell:**
```bash
export NPM_TOKEN="your-token"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

**Using .env file:**
```bash
# Create .env file
cat > .env << EOF
NPM_TOKEN=your-npm-token
PYPI_USERNAME=pypi-user
PYPI_PASSWORD=pypi-pass
MAVEN_USERNAME=maven-user
MAVEN_PASSWORD=maven-pass
EOF

# Load and run
source .env
socket-load-test test --config config.yaml --no-docker
```

### k6 Not Finding Credentials

If you're seeing authentication errors during the test:

1. Verify environment variables are exported before running
2. Check the k6 script has the credentials by looking at the generated script
3. Ensure no typos in credential variable names
4. Try using config file instead of CLI arguments

## Additional Resources

- See `examples/config-examples.yaml` for more examples
- Read the main README.md for full configuration options
- Check Socket Firewall documentation for registry setup
