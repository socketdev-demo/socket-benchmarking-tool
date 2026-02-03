# Socket Firewall Distributed Load Testing - Setup Guide

Complete guide for setting up distributed load testing across a Proxmox cluster to benchmark Socket Registry Firewall performance.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Proxmox Cluster                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Load Gen 1   │  │ Load Gen 2   │  │ Load Gen 3   │     │
│  │  (k6 test)   │  │  (k6 test)   │  │  (k6 test)   │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          │  HTTP Requests   │                  │
          └──────────────────┴──────────────────┘
                             │
                   ┌─────────▼────────┐
                   │  Socket Firewall │
                   │                  │
                   │  ┌────────────┐  │
                   │  │ Node       │  │◄── System Metrics
                   │  │ Exporter   │  │    (CPU, Memory)
                   │  │ :9100      │  │
                   │  └────────────┘  │
                   └──────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐
    │npm.dougbot│     │pypi.dougbot│    │maven.doug  │
    │   .ai     │     │   .ai      │    │  bot.ai    │
    └───────────┘     └────────────┘    └────────────┘
```

## Prerequisites

### On Your Workstation
- Proxmox VE access
- SSH client
- Python 3.8+

### For Socket Firewall Server
- Root/sudo access
- Ports 9100 open (for monitoring)
- Firewall URLs configured:
  - npm.dougbot.ai
  - pypi.dougbot.ai
  - maven.dougbot.ai

## Part 1: Socket Firewall Server Setup

### 1.1 Install Monitoring (Node Exporter)

SSH into your Socket Firewall server and run:

```bash
# Copy the monitoring setup script to SFW server
scp setup-sfw-monitoring.sh user@sfw-server:~/

# SSH into SFW server
ssh user@sfw-server

# Run the setup script
sudo ./setup-sfw-monitoring.sh
```

This will:
- Install Prometheus Node Exporter
- Configure systemd service
- Open firewall port 9100
- Start metrics collection

### 1.2 Verify Monitoring

```bash
# Check service status
sudo systemctl status node_exporter

# Test metrics endpoint
curl http://localhost:9100/metrics | head -20

# From another machine, verify external access
curl http://SFW_SERVER_IP:9100/metrics | grep node_cpu
```

You should see CPU, memory, network, and load metrics.

## Part 2: Proxmox Load Generator VMs

### 2.1 Create VM Template

1. **Create a new VM in Proxmox:**
   - Name: `load-test-template`
   - OS: Ubuntu 22.04 or Debian 12
   - CPU: 4 cores
   - RAM: 8GB
   - Disk: 32GB
   - Network: Bridge to appropriate VLAN

2. **Install OS and configure:**

```bash
# SSH into the new VM
ssh user@load-gen-vm

# Update system
sudo apt update && sudo apt upgrade -y

# Install k6
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | \
  sudo tee /etc/apt/sources.list.d/k6.list
sudo apt update
sudo apt install k6 -y

# Install Python 3 and required tools
sudo apt install -y python3 python3-pip curl wget git

# Verify installations
k6 version
python3 --version
```

3. **Install load test scripts:**

```bash
# Create working directory
mkdir -p ~/load-testing
cd ~/load-testing

# Copy all test scripts to this directory
# (Use scp or git to transfer files)
```

4. **Make scripts executable:**

```bash
chmod +x *.sh *.py
```

5. **Clean and convert to template:**

```bash
# Clean up
sudo apt clean
sudo rm -rf /tmp/*
history -c

# Shutdown
sudo shutdown -h now
```

6. **In Proxmox UI:**
   - Right-click VM → Convert to Template

### 2.2 Clone VMs from Template

Clone the template to create multiple load generators:

```bash
# From Proxmox host or using pvesh
qm clone TEMPLATE_ID NEW_VM_ID --name load-gen-1
qm clone TEMPLATE_ID NEW_VM_ID --name load-gen-2
qm clone TEMPLATE_ID NEW_VM_ID --name load-gen-3
```

Or use Proxmox UI:
- Right-click template → Clone
- Create 3-5 VMs: `load-gen-1`, `load-gen-2`, `load-gen-3`, etc.

### 2.3 Configure Each Load Generator

Start each VM and configure:

```bash
# SSH into each load generator
ssh user@load-gen-1

# Set unique hostname
sudo hostnamectl set-hostname load-gen-1

# Verify connectivity to Socket Firewall
curl -I https://npm.dougbot.ai/react
curl -I https://pypi.dougbot.ai/simple/requests/
curl -I https://maven.dougbot.ai/org/springframework/boot/spring-boot-starter-web/maven-metadata.xml

# Verify monitoring endpoint access
curl http://SFW_SERVER_IP:9100/metrics | grep node_cpu
```

Repeat for all load generators.

## Part 3: Running Load Tests

### 3.1 Environment Configuration

On each load generator, create an environment file:

```bash
cd ~/load-testing
cat > .env <<EOF
# Socket Firewall URLs
export NPM_URL="https://npm.dougbot.ai"
export PYPI_URL="https://pypi.dougbot.ai"
export MAVEN_URL="https://maven.dougbot.ai"

# Monitoring
export SFW_MONITOR_URL="http://YOUR_SFW_SERVER_IP:9100"

# Test Configuration
export CACHE_HIT_PCT="30"
export RESULTS_DIR="./load-test-results"
export LOAD_GEN_ID="gen-$(hostname)"

# RPS levels to test
export RPS_LEVELS="500 1000 5000 10000"
EOF

# Load environment
source .env
```

### 3.2 Test Connectivity

Run the smoke test on one load generator:

```bash
cd ~/load-testing
source .env
./smoke-test.sh
```

All checks should pass.

### 3.3 Single RPS Test (Practice Run)

Test with a single RPS level first:

```bash
# Run a quick 30-second test at 500 RPS
./run-distributed-test.sh --rps 500 --duration 30s --skip-warmup
```

Check results:
```bash
ls -lh load-test-results/
```

### 3.4 Run Two-Phase Tests

#### Option A: Single Load Generator

For smaller tests, one load generator might be sufficient:

```bash
# Run both phases (5-min and 1-hour tests)
./run-two-phase-tests.sh

# Or run only Phase 1 (5-minute tests)
./run-two-phase-tests.sh --phase1-only
```

#### Option B: Distributed Across Multiple Load Generators

For high RPS (5000+), use multiple load generators:

**On load-gen-1:**
```bash
cd ~/load-testing
source .env

# Split RPS across generators
# For 10,000 RPS target, each generator does 3,333 RPS
./run-distributed-test.sh \
  --rps 3333 \
  --duration 5m \
  --test-id test-10000rps-5min-20250109
```

**On load-gen-2:**
```bash
cd ~/load-testing
source .env

./run-distributed-test.sh \
  --rps 3333 \
  --duration 5m \
  --test-id test-10000rps-5min-20250109
```

**On load-gen-3:**
```bash
cd ~/load-testing
source .env

./run-distributed-test.sh \
  --rps 3334 \
  --duration 5m \
  --test-id test-10000rps-5min-20250109
```

**Note:** Use the same `test_id` across all generators so results can be aggregated.

### 3.5 Automated Distributed Execution

Create a coordination script on your workstation:

```bash
#!/bin/bash
# run-distributed-coordinated.sh

LOAD_GENS=("load-gen-1" "load-gen-2" "load-gen-3")
SSH_USER="user"
TEST_ID="test-10000rps-5min-$(date +%Y%m%d-%H%M%S)"
TOTAL_RPS=10000
NUM_GENS=${#LOAD_GENS[@]}
RPS_PER_GEN=$((TOTAL_RPS / NUM_GENS))

echo "Starting distributed test: $TEST_ID"
echo "Total RPS: $TOTAL_RPS across $NUM_GENS generators"
echo "RPS per generator: $RPS_PER_GEN"

for i in "${!LOAD_GENS[@]}"; do
  HOST="${LOAD_GENS[$i]}"
  
  # Adjust last generator for rounding
  if [ $i -eq $((NUM_GENS - 1)) ]; then
    RPS_PER_GEN=$((TOTAL_RPS - (RPS_PER_GEN * (NUM_GENS - 1))))
  fi
  
  echo "Starting on $HOST with $RPS_PER_GEN RPS..."
  
  ssh $SSH_USER@$HOST "cd ~/load-testing && source .env && ./run-distributed-test.sh --rps $RPS_PER_GEN --duration 5m --test-id $TEST_ID --skip-warmup" &
done

wait
echo "All tests complete!"
```

Run it:
```bash
chmod +x run-distributed-coordinated.sh
./run-distributed-coordinated.sh
```

## Part 4: Collecting and Analyzing Results

### 4.1 Collect Results from All Load Generators

From your workstation:

```bash
# Create results directory
mkdir -p aggregated-results

# Collect from all load generators
for host in load-gen-1 load-gen-2 load-gen-3; do
  echo "Collecting from $host..."
  rsync -avz user@$host:~/load-testing/load-test-results/ ./aggregated-results/
done
```

### 4.2 Generate Reports

Copy results to a machine with the report scripts:

```bash
# Create report config for Phase 1 (5-minute tests)
cat > phase1-config.json <<EOF
[
  {"test_id": "test-500rps-5min-20250109", "rps": 500},
  {"test_id": "test-1000rps-5min-20250109", "rps": 1000},
  {"test_id": "test-5000rps-5min-20250109", "rps": 5000},
  {"test_id": "test-10000rps-5min-20250109", "rps": 10000}
]
EOF

# Generate Phase 1 report
python3 generate-comprehensive-report.py phase1-config.json aggregated-results

# This creates: load-test-report-5-minute.html
```

Repeat for Phase 2 (1-hour tests):

```bash
cat > phase2-config.json <<EOF
[
  {"test_id": "test-500rps-1h-20250109", "rps": 500},
  {"test_id": "test-1000rps-1h-20250109", "rps": 1000},
  {"test_id": "test-5000rps-1h-20250109", "rps": 5000},
  {"test_id": "test-10000rps-1h-20250109", "rps": 10000}
]
EOF

python3 generate-comprehensive-report.py phase2-config.json aggregated-results
```

### 4.3 View Reports

Open the HTML files in a browser:

```bash
# Copy to a web-accessible location or open locally
firefox load-test-report-5-minute.html
firefox load-test-report-1-hour.html
```

## Part 5: Understanding the Reports

### Report Structure

Each report contains:

1. **Test Overview**
   - Test type (5-minute or 1-hour)
   - Ecosystems tested
   - Traffic mix and cache simulation
   - RPS levels tested

2. **Summary Metrics**
   - Total requests across all tests
   - Max RPS achieved
   - Total errors
   - Average error rate

3. **Per-RPS Sections** (one for each RPS level):
   - Performance summary table
   - System resource utilization (CPU, Memory, Load)
   - Request distribution by ecosystem
   - Response time details (min, avg, median, p95, p99, max)
   - Performance graphs:
     - Response time distribution
     - CPU usage over time
     - Memory usage over time

### Key Metrics to Watch

**Good Performance Indicators:**
- Error rate < 1%
- P95 latency < 500ms
- P99 latency < 1000ms
- CPU usage < 80% average
- Memory usage stable

**Warning Signs:**
- Error rate 1-5%
- P95 latency 500-1000ms
- CPU usage > 80%
- Memory usage climbing

**Poor Performance:**
- Error rate > 5%
- P95 latency > 1000ms
- CPU usage consistently > 90%
- Memory exhaustion

## Part 6: Troubleshooting

### Load Generators Can't Reach Firewall

```bash
# Check DNS resolution
nslookup npm.dougbot.ai
nslookup pypi.dougbot.ai
nslookup maven.dougbot.ai

# Check connectivity
curl -v https://npm.dougbot.ai/react

# Check SSL certificates
openssl s_client -connect npm.dougbot.ai:443 -servername npm.dougbot.ai
```

### Can't Collect System Metrics

```bash
# On Socket Firewall server, check node_exporter
sudo systemctl status node_exporter
sudo journalctl -u node_exporter -n 50

# Check firewall
sudo ufw status
curl http://localhost:9100/metrics

# From load generator
curl http://SFW_SERVER_IP:9100/metrics | head
```

### k6 Tests Failing

```bash
# Check k6 version
k6 version

# Run with verbose logging
k6 run --verbose socket-firewall-loadtest-distributed.js

# Check test script exists
ls -lh socket-firewall-loadtest-distributed.js
```

### High Error Rates

- Check Socket Firewall logs
- Verify upstream registry connectivity from SFW
- Check SFW resource limits (CPU, memory, connections)
- Reduce RPS and gradually increase

### Report Generation Fails

```bash
# Check Python version
python3 --version

# Verify results files exist
ls -lh load-test-results/

# Check JSON config syntax
cat phase1-config.json | python3 -m json.tool

# Run with error output
python3 generate-comprehensive-report.py phase1-config.json . 2>&1 | tee report-errors.log
```

## Part 7: Best Practices

### Before Testing

1. **Baseline**: Run a low-RPS test first (500 RPS) to establish baseline
2. **Verify**: Check all connectivity before high-RPS tests
3. **Warm-up**: Don't skip warm-up phase for realistic results
4. **Clean**: Clear any cached data on SFW if testing cache behavior

### During Testing

1. **Monitor**: Watch Socket Firewall logs and metrics in real-time
2. **Document**: Note any anomalies or manual interventions
3. **Isolate**: Avoid other traffic to SFW during tests

### After Testing

1. **Analyze**: Review reports thoroughly
2. **Compare**: Compare 5-minute vs 1-hour results for stability
3. **Archive**: Save all results and reports with clear naming
4. **Tune**: Adjust SFW configuration based on findings

## Part 8: Scaling Guidelines

### For Very High RPS (20K+)

1. **More Load Generators**: Add more Proxmox VMs
2. **Bigger VMs**: Increase CPU/RAM per load generator
3. **Network**: Ensure network isn't the bottleneck
4. **Coordination**: Use the distributed coordination script

### RPS Distribution Recommendations

| Target RPS | Load Generators | RPS per Generator |
|-----------|----------------|------------------|
| 500       | 1              | 500              |
| 1,000     | 1              | 1,000            |
| 5,000     | 2-3            | 1,667-2,500      |
| 10,000    | 3-4            | 2,500-3,333      |
| 20,000    | 5-6            | 3,333-4,000      |
| 50,000    | 10-12          | 4,167-5,000      |

## Part 9: Quick Reference

### Common Commands

```bash
# Start single test
./run-distributed-test.sh --rps 1000 --duration 5m

# Start two-phase tests
./run-two-phase-tests.sh

# Check test progress
tail -f load-test-results/*.log

# View results
ls -lh load-test-results/

# Generate report
python3 generate-comprehensive-report.py config.json .
```

### File Locations

- Test scripts: `~/load-testing/`
- Results: `~/load-testing/load-test-results/`
- Reports: `load-test-report-*.html`
- Logs: `load-test-results/*.log`

### URLs and Ports

- npm: https://npm.dougbot.ai
- PyPI: https://pypi.dougbot.ai
- Maven: https://maven.dougbot.ai
- Node Exporter: http://SFW_IP:9100/metrics

## Support

For issues or questions:
1. Check troubleshooting section
2. Review logs in `load-test-results/*.log`
3. Verify connectivity with smoke test
4. Check Socket Firewall server logs