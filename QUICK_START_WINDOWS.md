# Quick Start Guide - Windows

Get started with Socket Firewall Load Testing on Windows in 3 simple steps.

## Prerequisites

- Python 3.6+ (check: `python --version`)
- Git Bash or PowerShell

## Step 1: Unzip the Tool

```bash
unzip firewall-load-test-windows.zip
cd firewall-load-test
```

## Step 2: Install k6 (No Admin Required)

Download and extract k6 portable executable:

```bash
# Download k6
curl -L https://github.com/grafana/k6/releases/download/v0.51.0/k6-v0.51.0-windows-amd64.zip -o k6.zip

# Extract k6
unzip k6.zip

# Create bin directory and move k6
mkdir -p ~/bin
mv k6-v0.51.0-windows-amd64/k6.exe ~/bin/

# Add to PATH (for current session)
export PATH="$HOME/bin:$PATH"

# Make it permanent - add to ~/.bashrc (Git Bash) or your profile
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc

# Verify k6 is installed
k6 version
```

## Step 3: Install the Python Package

```bash
pip install --user -e .
```

**Add Python user scripts to PATH:**

When using `pip install --user`, scripts are installed to a user directory that may not be in your PATH. Add it:

```bash
# Find your user scripts directory
python -m site --user-base

# This typically returns: C:\Users\<YourName>\AppData\Roaming\Python\Python3XX
# The scripts are in: C:\Users\<YourName>\AppData\Roaming\Python\Python3XX\Scripts

# Add to PATH for current session (Git Bash)
export PATH="$APPDATA/Python/Python313/Scripts:$PATH"

# Or for PowerShell:
$env:Path += ";$env:APPDATA\Python\Python313\Scripts"

# Make it permanent in Git Bash - add to ~/.bashrc:
echo 'export PATH="$APPDATA/Python/Python313/Scripts:$PATH"' >> ~/.bashrc

# Verify installation
socket-load-test --help
```

**Note:** Replace `Python313` with your Python version (e.g., `Python312`, `Python311`).

## Run Your First Test

```bash
socket-load-test test \
  --rps 10 \
  --duration 60s \
  --no-docker \
  --npm-url "https://npm.your-firewall.com" \
  --pypi-url "https://pypi.your-firewall.com" \
  --maven-url "https://maven.your-firewall.com"
```

Or use path-based configuration:

```bash
socket-load-test test \
  --rps 10 \
  --duration 60s \
  --no-docker \
  --base-url "https://firewall.company.com" \
  --npm-path "/npm" \
  --pypi-path "/simple" \
  --maven-path "/maven2"
```

## Results

Test results are saved to `./load-test-results/` by default.

## Common Issues

**"k6 not found"**
- Make sure `~/bin` is in your PATH
- Run: `export PATH="$HOME/bin:$PATH"`
- Or restart Git Bash after updating `.bashrc`

**"No module named 'click'"**
- Install dependencies: `pip install --user -r requirements.txt`

**"Permission denied" when installing**
- Use `--user` flag: `pip install --user -e .`

**NPM registry authentication issues** *(Resolved example - admin-supported)*
- **Issue discovered:** February 2, 2026 - Authentication failures when testing npm registries through Socket Firewall
- **Root cause:** Misconfigured `.npmrc` file with incorrect registry URL format or malformed authentication tokens
- **How it manifests:** 
  - 401/403 errors during npm package requests in load tests
  - k6 test failures showing "authentication required" or "unauthorized" responses
  - Works in browser/Postman but fails in automated testing
- **Solution implemented:**
  1. Verify `.npmrc` format: Registry URL must match firewall URL exactly
     ```
     registry=https://npm.your-firewall.com/
     //npm.your-firewall.com/:_authToken=<your-token>
     ```
  2. Ensure no trailing slashes in token configuration line
  3. Check that token has correct permissions for package access
  4. Test authentication: `npm ping --registry=https://npm.your-firewall.com`
- **Admin note:** This is a documented configuration issue that can be resolved without escalation. Check client's `.npmrc` against firewall URL configuration and regenerate tokens if needed.

**OpenShift/Harness deployment delays** *(Working - optimization opportunity)*
- **Environment:** Customer using OpenShift with Harness for container orchestration
- **Issue:** New container versions taking 9-10 minutes to deploy, causing significant delays during testing/updates
- **Impact:** 
  - Extended iteration cycles when testing configuration changes
  - Delays in applying Socket Firewall updates
  - Reduced agility for troubleshooting and rollbacks
- **Current status:** Functional but slow - deployments complete successfully
- **Optimization opportunities:**
  - Review Harness pipeline stages for unnecessary steps or sequential operations that could be parallelized
  - Check OpenShift resource quotas and pod scheduling delays
  - Consider container image size optimization to reduce pull times
  - Evaluate health check timeouts and readiness probe intervals
  - Implement image layer caching strategies in build pipeline
- **Recommended investigation:** Profile the deployment pipeline to identify the bottleneck (image pull, health checks, or Harness workflow overhead)

## Next Steps

- Read [README.md](README.md) for full documentation
- Customize test parameters (`--rps`, `--duration`, etc.)
- Set up monitoring (see [SETUP.md](SETUP.md))
- Generate reports: `python generate-comprehensive-report.py`

## Need Help?

See the full [README.md](README.md) for:
- Detailed configuration options
- Distributed testing setup
- Report generation
- Troubleshooting guide
