# Socket Firewall Load Testing Framework

Distributed load testing framework for Socket Firewall with comprehensive reporting and system metrics collection.

## Overview

This framework provides tools to run distributed load tests against Socket Firewall instances, collect system metrics, and generate detailed HTML reports with performance analytics.

### Key Features

- **Distributed Testing**: Coordinate tests across multiple load generators
- **Multi-Ecosystem Support**: Test npm, PyPI, and Maven registries simultaneously
- **System Metrics**: Real-time CPU, memory, network, and load average tracking
- **Comprehensive Reporting**: HTML reports with graphs, percentiles, and RPS breakdown
- **Cache Simulation**: Configurable cache hit percentage for realistic scenarios

## Components

### Core Files

| File | Purpose |
|------|---------|
| `run-distributed-test.sh` | Main test coordinator - runs k6 tests and collects metrics |
| `socket-firewall-loadtest-distributed.js` | k6 load test script for multi-ecosystem testing |
| `setup-sfw-monitoring.sh` | Sets up Prometheus Node Exporter on SFW server |
| `generate-comprehensive-report.py` | Generates detailed HTML reports from test results |
| `generate-report-simple.py` | Simple wrapper for quick report generation |
| `aggregate-results.py` | Helper to view and aggregate results from multiple generators |

### Reference Configurations

The `socket_files/` directory contains reference Docker Compose configurations for different resource tiers:

| Configuration | Resources | Expected Throughput | Use Case |
|---------------|-----------|---------------------|----------|
| `socket.yml.1cpu-1gb` | 1 CPU, 768M RAM | ~500 RPS | Small dev/test environments |
| `socket.yml.2cpu-2gb` | 2 CPU, 1792M RAM | ~1,000-2,000 RPS | Standard dev/staging |
| `socket.yml.4cpu-4gb` | 4 CPU, 3840M RAM | ~5,000-10,000 RPS | Production environments |
| `socket.yml.8cpu-8gb` | 8 CPU, 7936M RAM | ~15,000-20,000 RPS | High-volume production |
| `socket.yml.optimized` | Tuning parameters | - | Resource optimization settings |

See [socket_files/README.md](socket_files/README.md) for detailed configuration documentation.

## Prerequisites

### On Load Generator Machines

**Required:**
- bash - Shell scripting
- curl - HTTP client
- Python 3.6+ - For report generation

**Choose ONE:**
- [k6](https://k6.io/docs/getting-started/installation/) (for `--no-docker` local execution)
- Docker (for traditional Docker-based execution)

Install k6 for local execution:
```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6

# Windows
winget install k6 --source winget
# Or use Chocolatey: choco install k6
```

**💡 Tip:** Use `--no-docker` flag if you have k6 installed locally for faster startup and simpler setup.

**Platform Notes:**
- ✅ **Linux/macOS**: All features fully supported
- ✅ **Windows**: Python CLI (`socket-load-test`) works natively with `--no-docker`
  - Shell scripts (`.sh`) require WSL, Git Bash, or Cygwin
  - **Recommended for Windows:** Use the Python CLI instead of bash scripts
  - k6 runs natively on Windows (install via `winget` or `choco`)
  
**Windows Installation (using Git Bash):**
```powershell
# 1. Install Python (if not already installed)
winget install Python.Python.3.12

# 2. Install k6 (requires Admin)
winget install k6 --source winget
# Or with Chocolatey: choco install k6

# 3. Install the package (in Git Bash)
pip install -e .

# 4. Verify installations
python --version    # Should show Python 3.6+
k6 version          # Should show k6 version
socket-load-test --help  # Should show CLI help
```

**Windows Installation WITHOUT Admin Rights:**
```bash
# 1. Download k6 portable executable (in Git Bash or PowerShell)
curl -L https://github.com/grafana/k6/releases/download/v0.51.0/k6-v0.51.0-windows-amd64.zip -o k6.zip

# 2. Extract and add to PATH
unzip k6.zip
mkdir -p ~/bin
mv k6-v0.51.0-windows-amd64/k6.exe ~/bin/
export PATH="$HOME/bin:$PATH"  # Add to ~/.bashrc for persistence

# 3. Verify k6 works
k6 version

# 4. Install the package
pip install --user -e .

# 5. Verify
socket-load-test --help
```

**Note:** If you don't have admin rights, use the portable k6 executable. Just download the ZIP, extract `k6.exe`, and place it in a directory in your PATH (like `C:\Users\YourName\bin` or `~/bin`).

**Running tests on Windows with Git Bash:**
```bash
# Option 1: Use Python CLI (recommended)
socket-load-test test --rps 1000 --duration 60s --no-docker --host firewall.example.com

# Option 2: Use bash scripts (works in Git Bash)
./run-distributed-test.sh --rps 1000 --duration 5m --no-docker
```

**Windows without Git Bash (PowerShell with Admin):**
```powershell
# Install k6 (PowerShell as Administrator)
winget install k6 --source winget

# Run tests using Python CLI
socket-load-test test --rps 1000 --duration 60s --no-docker --host firewall.example.com
```

### On Socket Firewall Server

- Prometheus Node Exporter (installed via `setup-sfw-monitoring.sh`)

## Setup

### 1. Setup Monitoring on SFW Server

Run this on your Socket Firewall server to enable system metrics collection:

```bash
sudo ./setup-sfw-monitoring.sh
```

This installs and configures Prometheus Node Exporter on port 9100.

Verify it's working:
```bash
curl http://YOUR_SFW_IP:9100/metrics | grep node_cpu
```

### 2. Configure Firewall Domains/URLs

The load test targets Socket Firewall proxy endpoints for npm, PyPI, and Maven registries.

**Option 1: Using Environment Variables**

Set these on your load generator machine(s):

```bash
# Required - Firewall endpoint URLs
export NPM_URL="https://npm.your-firewall-domain.com"
export PYPI_URL="https://pypi.your-firewall-domain.com"
export MAVEN_URL="https://maven.your-firewall-domain.com"

# Required - For system metrics collection
export SFW_MONITOR_URL="http://YOUR_SFW_IP:9100"

# Optional (with defaults)
export CACHE_HIT_PCT="30"
export RESULTS_DIR="./load-test-results"
export LOAD_GEN_ID="gen-$(hostname)"
```

**Option 2: Using Command-Line Arguments (Python CLI)**

```bash
# Specify each URL individually
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --no-docker \
  --npm-url "https://npm.your-firewall-domain.com" \
  --pypi-url "https://pypi.your-firewall-domain.com" \
  --maven-url "https://maven.your-firewall-domain.com"

# Use --base-url with custom paths for each registry
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --no-docker \
  --base-url "https://firewall.company.com" \
  --npm-path "/npm" \
  --pypi-path "/simple" \
  --maven-path "/maven2"
# This creates:
#   NPM:   https://firewall.company.com/npm
#   PyPI:  https://firewall.company.com/simple
#   Maven: https://firewall.company.com/maven2

# Mix base-url with custom paths and URL overrides
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --no-docker \
  --base-url "https://firewall.company.com" \
  --npm-path "/registry/npm" \
  --pypi-path "/index/pypi/simple" \
  --maven-url "https://custom-maven.company.com/repository"
```

**Option 3: Using Configuration File**

Create a `config.yaml`:

```yaml
# Option A: Specify each URL individually
registries:
  npm_url: "https://npm.your-firewall-domain.com"
  pypi_url: "https://pypi.your-firewall-domain.com"
  maven_url: "https://maven.your-firewall-domain.com"
  cache_hit_percent: 30

# Option B: Use base_url with custom paths
registries:
  base_url: "https://firewall.company.com"
  npm_path: "/npm"
  pypi_path: "/simple"
  maven_path: "/maven2"
  cache_hit_percent: 30

# Option C: Mix base_url, paths, and URL overrides
registries:
  base_url: "https://firewall.company.com"
  npm_path: "/custom/npm/path"
  pypi_path: "/Example Command |
|------------|-----------------|
| **Subdomain-based** | `--npm-url https://npm.firewall.com --pypi-url https://pypi.firewall.com --maven-url https://maven.firewall.com` |
| **Standard paths** | `--base-url https://firewall.com --npm-path /npm --pypi-path /pypi --maven-path /maven` |
| **Custom paths** | `--base-url https://firewall.com --npm-path /registry/npm --pypi-path /simple --maven-path /maven2` |
| **Mixed setup** | `--base-url https://firewall.com --npm-path /npm --maven-url https://maven.external.com` |
| **Port-based** | `--npm-url https://firewall.com:8001 --pypi-url https://firewall.com:8002 --maven-url https://firewall.com:8003` |
| **Local testing** | `--base-url http://localhost:8080 --npm-path /npm --pypi-path /pypi --maven-path 
  node_exporter_url: "http://YOUR_SFW_IP:9100"
```

Then run:
```bash
socket-load-test test --config config.yaml --rps 1000 --duration 60s --no-docker
```

**Common Setups:**

| Setup Type | NPM URL | PyPI URL | Maven URL |
|------------|---------|----------|-----------|
| Single domain with paths | `https://firewall.company.com/npm` | `https://firewall.company.com/pypi` | `https://firewall.company.com/maven` |
| Subdomains | `https://npm.firewall.company.com` | `https://pypi.firewall.company.com` | `https://maven.firewall.company.com` |
| Port-based | `https://firewall.company.com:8001` | `https://firewall.company.com:8002` | `https://firewall.company.com:8003` |
| Local testing | `http://localhost:8080/npm` | `http://localhost:8080/pypi` | `http://localhost:8080/maven` |

**Testing Your Configuration:**

```bash
# Verify firewall endpoints are accessible
curl -I $NPM_URL/express
curl -I $PYPI_URL/simple/requests/
curl -I $MAVEN_URL/maven2/org/apache/maven/maven/
```

### 3. Private Registry Authentication

The load test framework supports authentication for private registries across all 3 ecosystems (npm, PyPI, and Maven).

**Authentication Method Per Ecosystem:**

| Ecosystem | Token Auth Method | Username/Password Method | Details |
|-----------|------------------|-------------------------|---------|
| **npm**   | Basic Auth (recommended) | Basic Auth | Tokens use format: `Authorization: Basic base64(_token:token_value)` |
| **PyPI**  | Basic Auth (recommended) | Basic Auth | Tokens use format: `Authorization: Basic base64(__token__:token_value)` |
| **Maven** | N/A | Basic Auth only | Standard Basic authentication |

**Important:** 
- NPM tokens are sent using Basic authentication with the format `_token:YOUR_TOKEN` (base64 encoded)
- PyPI tokens are sent using Basic authentication with the format `__token__:YOUR_TOKEN` (base64 encoded)
- This matches the standard authentication methods used by npm and pip clients

#### NPM Authentication

**Option 1: Token (Recommended)**
```bash
# Via environment variable
export NPM_TOKEN="npm_your-token-here"

# Via CLI
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --npm-url "https://npm.private.com" \
  --npm-token "${NPM_TOKEN}"

# Via config file
registries:
  npm_url: "https://npm.private.com"
  npm_token: ${NPM_TOKEN}  # References environment variable
```

**Note:** The npm token will be automatically encoded as `Basic base64(_token:YOUR_TOKEN)` in the Authorization header.

**Option 2: Basic Authentication**
```bash
# Via environment variables
export NPM_USERNAME="your-username"
export NPM_PASSWORD="your-password"

# Via CLI
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --npm-url "https://npm.private.com" \
  --npm-username "${NPM_USERNAME}" \
  --npm-password "${NPM_PASSWORD}"

# Via config file
registries:
  npm_url: "https://npm.private.com"
  npm_username: ${NPM_USERNAME}
  npm_password: ${NPM_PASSWORD}
```

#### PyPI Authentication

**Option 1: Token (Recommended)**
```bash
# Via environment variable
export PYPI_TOKEN="pypi-your-token-value"

# Via CLI
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --pypi-url "https://pypi.private.com" \
  --pypi-token "${PYPI_TOKEN}"

# Via config file
registries:
  pypi_url: "https://pypi.private.com"
  pypi_token: ${PYPI_TOKEN}
```

**Note:** The PyPI token will be automatically encoded as `Basic base64(__token__:YOUR_TOKEN)` in the Authorization header, which is the standard method used by pip.

**Option 2: Basic Authentication**
```bash
# Via environment variables
export PYPI_USERNAME="your-username"
export PYPI_PASSWORD="your-password"

# Via CLI
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --pypi-url "https://pypi.private.com" \
  --pypi-username "${PYPI_USERNAME}" \
  --pypi-password "${PYPI_PASSWORD}"

# Via config file
registries:
  pypi_url: "https://pypi.private.com"
  pypi_username: ${PYPI_USERNAME}
  pypi_password: ${PYPI_PASSWORD}
```

#### Maven Authentication

Maven only supports **Basic Authentication** (username/password).

```bash
# Via environment variables
export MAVEN_USERNAME="your-maven-user"
export MAVEN_PASSWORD="your-maven-password"

# Via CLI
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --maven-url "https://maven.private.com" \
  --maven-username "${MAVEN_USERNAME}" \
  --maven-password "${MAVEN_PASSWORD}"

# Via config file
registries:
  maven_url: "https://maven.private.com"
  maven_username: ${MAVEN_USERNAME}
  maven_password: ${MAVEN_PASSWORD}
```

#### Complete Example: All Ecosystems with Authentication

**Using config file (recommended for multiple ecosystems):**

```yaml
# config.yaml
infrastructure:
  type: ssh
  ssh:
    firewall_server:
      host: 192.168.1.100
      port: 22
      user: admin
      key_file: ~/.ssh/id_rsa
    load_generators:
      - host: 192.168.1.101
        port: 22
        user: loadgen
        key_file: ~/.ssh/id_rsa

test:
  rps: 5000
  duration: 10m
  test_id: private-registry-test

registries:
  # Registry URLs
  npm_url: https://npm.private.company.com
  pypi_url: https://pypi.private.company.com
  maven_url: https://maven.private.company.com
  
  # NPM Authentication (Bearer token)
  npm_token: ${NPM_TOKEN}
  
  # PyPI Authentication (Basic auth with __token__: prefix)
  pypi_token: ${PYPI_TOKEN}
  
  # Maven Authentication (Basic auth)
  maven_username: ${MAVEN_USERNAME}
  maven_password: ${MAVEN_PASSWORD}
  
  # Ecosystem selection
  ecosystems: ['npm', 'pypi', 'maven']
  cache_hit_percent: 30

traffic:
  npm_ratio: 40
  pypi_ratio: 30
  maven_ratio: 30
  metadata_only: false

monitoring:
  enabled: true
  interval_seconds: 5

results:
  output_dir: ./private-registry-results
  auto_generate_html: true
```

Then run with:
```bash
# Set environment variables
export NPM_TOKEN="your-npm-token"
export PYPI_USERNAME="pypi-user"
export PYPI_PASSWORD="pypi-pass"
export MAVEN_USERNAME="maven-user"
export MAVEN_PASSWORD="maven-pass"

# Run the test
socket-load-test test --config config.yaml
```

**Using CLI arguments:**

```bash
socket-load-test test \
  --rps 5000 \
  --duration 10m \
  --npm-url "https://npm.private.com" \
  --npm-token "${NPM_TOKEN}" \
  --pypi-url "https://pypi.private.com" \
  --pypi-username "${PYPI_USERNAME}" \
  --pypi-password "${PYPI_PASSWORD}" \
  --maven-url "https://maven.private.com" \
  --maven-username "${MAVEN_USERNAME}" \
  --maven-password "${MAVEN_PASSWORD}" \
  --no-docker
```

**Security Best Practices:**

1. **Never hardcode credentials** in config files or scripts
2. **Use environment variables** to store sensitive credentials
3. **Use a secrets manager** (e.g., AWS Secrets Manager, HashiCorp Vault) in production
4. **Rotate credentials regularly**
5. **Use tokens instead of passwords** when possible (npm, PyPI)
6. **Restrict token permissions** to read-only access for load testing
7. **Review logs** to ensure credentials are not exposed (they're automatically filtered)

See `examples/config-examples.yaml` for more authentication configuration examples.

## Usage

### Running a Load Test

**Basic usage (local execution without Docker):**
```bash
./run-distributed-test.sh --rps 1000 --duration 5m --no-docker
```custom paths:
```bash
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --no-docker \
  --base-url "https://firewall.company.com" \
  --npm-path "/npm" \
  --pypi-path "/simple" \
  --maven-path "/maven2
  --no-docker \
  --base-url "https://firewall.company.com"
```

Or with individual URLs:
```bash
socket-load-test test \
  --rps 1000 \
  --duration 60s \
  --no-docker \
  --host firewall.example.com
```

**With Docker (traditional mode):**
```bash
./run-distributed-test.sh --rps 1000 --duration 5m
```

**With custom test ID:**
```bash
./run-distributed-test.sh --rps 5000 --duration 1h --test-id prod-test-001 --no-docker
```

**Skip warmup phase:**
```bash
./run-distributed-test.sh --rps 1000 --duration 5m --skip-warmup --no-docker
```

### Command-line Options

```
--rps <value>       Target requests per second (required)
--duration <value>  Test duration (default: 5m)
                    Examples: 30s, 5m, 1h
--test-id <value>   Custom test ID (default: test-YYYYMMDD-HHMMSS)
--skip-warmup       Skip 30-second warmup phase
--no-docker         Run k6 locally without Docker (requires k6 installed)
--help              Show help message
```

### Local vs Docker Execution

**Local Mode (`--no-docker`):**
- ✅ Runs k6 directly on your machine
- ✅ No Docker installation required
- ✅ Faster startup time
- ✅ Great for development and quick tests
- ✅ **Works on Windows, macOS, and Linux**
- ⚠️ Requires k6 to be installed locally

**Docker Mode (default):**
- ✅ Consistent environment across machines
- ✅ No need to install k6 separately
- ✅ Better for remote execution
- ⚠️ Requires Docker installation
- ⚠️ On Windows, requires Docker Desktop or WSL2

### Running Distributed Tests

To distribute load across multiple machines:

1. **On each load generator**, run the same test with unique `LOAD_GEN_ID`:
   ```bash
   # Machine 1 (using local k6)
   export LOAD_GEN_ID="gen-01"
   ./run-distributed-test.sh --rps 2000 --duration 5m --test-id my-test --no-docker
   
   # Machine 2 (using local k6)
   export LOAD_GEN_ID="gen-02"
   ./run-distributed-test.sh --rps 2000 --duration 5m --test-id my-test --no-docker
   
   # Machine 3 (using Docker)
   export LOAD_GEN_ID="gen-03"
   ./run-distributed-test.sh --rps 2000 --duration 5m --test-id my-test
```
   ```

2. **After all complete**, copy all results to one machine:
   ```bash
   # On machine 1
   scp gen-02:/path/to/load-test-results/my-test_* ./load-test-results/
   scp gen-03:/path/to/load-test-results/my-test_* ./load-test-results/
   ```

3. **Generate combined report**:
   ```bash
   ./generate-report-simple.py my-test 6000
   # Total RPS = 2000 + 2000 + 2000 = 6000
   ```

### Generating Reports

#### Quick Report (Recommended)

Simple wrapper that auto-creates config and generates report:

```bash
./generate-report-simple.py test-20260109-173015 1000
```

Arguments:
- `test-id`: The test identifier (from `--test-id` or auto-generated)
- `rps`: Target RPS (optional, tries to auto-detect from test ID)

#### Generate HTML Reports

Use the `--generate-html-report` flag to automatically create a comprehensive HTML report after test completion:

```bash
socket-load-test test \
  --rps 1000 \
  --duration 120s \
  --base-url https://sfw.dougbot.ai \
  --npm-path /npm \
  --pypi-path /pypi \
  --maven-path /maven \
  --ecosystems npm,pypi,maven \
  --no-docker \
  --generate-html-report \
  --html-report-path ./reports
```

#### Custom Package Lists

Use the `--packages` flag to specify custom packages to test instead of the defaults:

```bash
# Create a custom packages file
cat > my-packages.json <<EOF
{
  "npm": ["react", "vue", "express", "lodash"],
  "pypi": ["requests", "flask", "django"],
  "maven": ["org.springframework.boot:spring-boot-starter-web"]
}
EOF

socket-load-test test \
  --rps 100 \
  --duration 60s \
  --base-url https://sfw.dougbot.ai \
  --npm-path /npm \
  --ecosystems npm \
  --no-docker \
  --packages my-packages.json \
  --verbose
```

The `--verbose` flag shows which packages and versions will be tested before the test begins.

Opens in browser:
```bash
firefox reports/load-test-report-2-minute.html
# or
python3 -m http.server 8000
# Then visit: http://localhost:8000/reports/load-test-report-2-minute.html
```

### Viewing Results

List available tests:
```bash
./aggregate-results.py test-20260109-173015
```

This shows all result files for a test ID across load generators.

## Output Files

Each test produces:

```
load-test-results/
├── {test_id}_{load_gen_id}_k6_results.json      # k6 raw metrics
├── {test_id}_{load_gen_id}_k6_summary.txt       # k6 summary stats
├── {test_id}_{load_gen_id}_system_metrics.jsonl # CPU/Memory/Network
└── {test_id}_{load_gen_id}.log                  # Test execution log
```

After report generation:
```
load-test-report-5-minute.html  # Comprehensive HTML report
```

## Report Contents

The comprehensive HTML report includes:

### Overall Summary
- Total requests, RPS, duration
- Error rate and success rate
- P50, P95, P99 latency percentiles
- System resource usage (CPU, memory, load)

### Per-RPS Sections
- Request distribution across ecosystems (npm, PyPI, Maven)
- Cache hit vs. miss rates
- Latency breakdown (metadata vs. download)
- Error details
- Timeline graphs

### System Metrics
- CPU utilization over time
- Memory usage trends
- Network throughput
- Load average (1m, 5m, 15m)

### Performance Graphs
- Request rate timeline
- Latency percentiles over time
- Error rate timeline
- System resource usage timeline

## Examples

### Single 5-minute test at 1000 RPS
```bash
export SFW_MONITOR_URL="http://10.0.1.50:9100"
./run-distributed-test.sh --rps 1000 --duration 5m

# After completion
./generate-report-simple.py test-20260109-173015 1000
```

### 1-hour sustained load test
```bash
export SFW_MONITOR_URL="http://10.0.1.50:9100"
./run-distributed-test.sh --rps 5000 --duration 1h --test-id sustained-5k

# After completion
./generate-report-simple.py sustained-5k 5000
```

### Distributed test: 10,000 RPS across 5 machines
```bash
# On each of 5 machines (each targeting 2000 RPS)
export SFW_MONITOR_URL="http://10.0.1.50:9100"
export LOAD_GEN_ID="gen-0X"  # X = 1,2,3,4,5
./run-distributed-test.sh --rps 2000 --duration 5m --test-id dist-10k

# Copy all results to one machine
# Then generate report
./generate-report-simple.py dist-10k 10000
```

### Cache hit testing
```bash
# 30% cache hit (default)
export CACHE_HIT_PCT="30"
./run-distributed-test.sh --rps 1000 --duration 5m

# 70% cache hit (high cache scenario)
export CACHE_HIT_PCT="70"
./run-distributed-test.sh --rps 1000 --duration 5m --test-id high-cache
```

## Troubleshooting

### No results found
```bash
# List all test IDs
ls -1 load-test-results/*_k6_results.json | sed 's/.*\///' | sed 's/_.*$//' | sort -u
```

### Monitoring endpoint not responding
```bash
# On SFW server
sudo systemctl status node_exporter
curl http://localhost:9100/metrics | grep node_cpu

# Check firewall
sudo ufw status | grep 9100
```

### k6 errors
```bash
# Check connectivity
curl -I https://sfw.dougbot.ai/npm/react
curl -I https://sfw.dougbot.ai/pypi/simple/requests/

# Verify k6 installation
k6 version
```

### Report generation fails
```bash
# Check Python version
python3 --version  # Should be 3.6+

# Verify results exist
ls -la load-test-results/test-20260109-173015_*
```

## Test Workflow

The test script performs these steps:

1. **Dependency Check**: Verifies k6, curl are installed
2. **Connectivity Test**: Checks npm, PyPI, Maven endpoints are reachable
3. **Warmup Phase** (optional): 30-second test at 10% target RPS
4. **Metrics Collection Start**: Begins polling SFW server every 5 seconds
5. **Main Load Test**: Runs k6 test at target RPS for specified duration
6. **Metrics Collection Stop**: Stops polling and saves metrics
7. **Results Saved**: Writes k6 results, summary, system metrics, and logs

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Load Generator  │     │ Load Generator  │     │ Load Generator  │
│   Machine 1     │     │   Machine 2     │     │   Machine N     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │    k6 HTTP Requests   │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  Socket Firewall       │
                    │  (with Node Exporter)  │
                    └────────────────────────┘
                                 │
                                 │ Metrics polling (every 5s)
                                 │
                    ┌────────────────────────┐
                    │  node_exporter:9100    │
                    │  - CPU metrics         │
                    │  - Memory metrics      │
                    │  - Network metrics     │
                    │  - Load average        │
                    └────────────────────────┘
```

## Testing Configurations

### Docker Compose Resource Tiers

When deploying Socket Firewall for testing, use the reference configurations in `socket_files/`:

#### 1 CPU / 1GB RAM Configuration
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 768M      # Leave 256M for OS
    reservations:
      cpus: '0.5'
      memory: 512M
```
**Test with:** `--rps 500 --duration 5m`

#### 2 CPU / 2GB RAM Configuration
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1792M     # Leave 256M for OS (2048-256)
    reservations:
      cpus: '1.0'
      memory: 1280M
```
**Test with:** `--rps 1000 --duration 5m` or `--rps 2000 --duration 5m`

#### 4 CPU / 4GB RAM Configuration
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 3840M     # Leave 256M for OS (4096-256)
    reservations:
      cpus: '2.0'
      memory: 2560M
```
**Test with:** `--rps 5000 --duration 5m` or `--rps 10000 --duration 5m`

#### 8 CPU / 8GB RAM Configuration
```yaml
deploy:
  resources:
    limits:
      cpus: '8.0'
      memory: 7936M     # Leave 256M for OS (8192-256)
    reservations:
      cpus: '4.0'
      memory: 5120M
```
**Test with:** `--rps 15000 --duration 5m` or `--rps 20000 --duration 5m`

### Configuration Principles

- **Memory limits:** Always reserve ~256MB for OS overhead
- **CPU reservations:** 50% of limit ensures minimum guaranteed performance
- **Memory reservations:** ~64-67% of limit provides buffer for burst traffic
- **Progressive testing:** Start at lower RPS, increase gradually while monitoring metrics

### Recommended Testing Progression

1. **Deploy** Socket Firewall with chosen tier configuration
2. **Start small:** Begin with 500 RPS regardless of tier
3. **Monitor metrics:** CPU, memory, error rate, latency
4. **Increase load:** Double RPS if metrics are healthy (<80% CPU, <0.1% errors)
5. **Find ceiling:** Stop when CPU >80% or errors >0.1%
6. **Document:** Record max sustainable RPS for the configuration

For complete configuration details, see [socket_files/README.md](socket_files/README.md).

## Tips

- **Start small**: Begin with low RPS (500-1000) to validate setup
- **Monitor resources**: Watch `htop` on SFW server during tests
- **Network bandwidth**: Ensure adequate bandwidth for high RPS tests
- **Distributed tests**: Use multiple machines for tests exceeding 10,000 RPS
- **Cache warming**: Run a warmup test first for more realistic cache behavior
- **Results retention**: Archive old results to keep directory clean

## License

Internal Socket.dev tooling
