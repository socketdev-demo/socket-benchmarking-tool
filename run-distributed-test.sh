#!/bin/bash

# Distributed Load Test Coordinator for Socket Firewall
# Runs k6 load tests while collecting system metrics from SFW server

set -e

# Configuration
NPM_URL="${NPM_URL:-https://npm.dougbot.ai}"
PYPI_URL="${PYPI_URL:-https://pypi.dougbot.ai}"
MAVEN_URL="${MAVEN_URL:-https://maven.dougbot.ai}"
SFW_MONITOR_URL="${SFW_MONITOR_URL:-}"
CACHE_HIT_PCT="${CACHE_HIT_PCT:-30}"
RESULTS_DIR="${RESULTS_DIR:-./load-test-results}"
LOAD_GEN_ID="${LOAD_GEN_ID:-gen-$(hostname)}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Usage
usage() {
  cat <<EOF
Usage: $0 [OPTIONS]

Distributed Load Test Coordinator for Socket Firewall

Required Environment Variables:
  SFW_MONITOR_URL    Socket Firewall monitoring endpoint (e.g., http://sfw-server:9100)

Optional Environment Variables:
  NPM_URL            npm registry URL (default: https://npm.dougbot.ai)
  PYPI_URL           PyPI registry URL (default: https://pypi.dougbot.ai)
  MAVEN_URL          Maven registry URL (default: https://maven.dougbot.ai)
  CACHE_HIT_PCT      Cache hit percentage (default: 30)
  RESULTS_DIR        Results directory (default: ./load-test-results)
  LOAD_GEN_ID        Load generator ID (default: gen-<hostname>)

Options:
  --rps <value>      Target RPS (required)
  --duration <value> Test duration (default: 5m)
  --test-id <value>  Test ID for grouping results (default: auto-generated)
  --skip-warmup      Skip warmup phase
  --help             Show this help message

Examples:
  # Run 1000 RPS test for 5 minutes
  SFW_MONITOR_URL=http://10.0.0.10:9100 $0 --rps 1000 --duration 5m

  # Run 5000 RPS test for 1 hour with custom test ID
  SFW_MONITOR_URL=http://10.0.0.10:9100 $0 --rps 5000 --duration 1h --test-id prod-test-001

EOF
  exit 1
}

# Parse arguments
TARGET_RPS=""
DURATION="5m"
TEST_ID="test-$(date +%Y%m%d-%H%M%S)"
SKIP_WARMUP=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --rps)
      TARGET_RPS="$2"
      shift 2
      ;;
    --duration)
      DURATION="$2"
      shift 2
      ;;
    --test-id)
      TEST_ID="$2"
      shift 2
      ;;
    --skip-warmup)
      SKIP_WARMUP=true
      shift
      ;;
    --help)
      usage
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      usage
      ;;
  esac
done

# Validate required parameters
if [ -z "$TARGET_RPS" ]; then
  echo -e "${RED}Error: --rps is required${NC}"
  usage
fi

if [ -z "$SFW_MONITOR_URL" ]; then
  echo -e "${RED}Error: SFW_MONITOR_URL environment variable is required${NC}"
  usage
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

# Logging
LOG_FILE="$RESULTS_DIR/${TEST_ID}_${LOAD_GEN_ID}.log"
exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "========================================"
echo "Socket Firewall Distributed Load Test"
echo "========================================"
echo "Test ID: $TEST_ID"
echo "Load Generator: $LOAD_GEN_ID"
echo "Target RPS: $TARGET_RPS"
echo "Duration: $DURATION"
echo "NPM URL: $NPM_URL"
echo "PyPI URL: $PYPI_URL"
echo "Maven URL: $MAVEN_URL"
echo "SFW Monitor: $SFW_MONITOR_URL"
echo "Cache Hit %: $CACHE_HIT_PCT"
echo "Results Dir: $RESULTS_DIR"
echo "========================================"
echo ""

# Check dependencies
check_dependencies() {
  echo "Checking dependencies..."
  
  if ! command -v k6 &> /dev/null; then
    echo -e "${RED}Error: k6 is not installed${NC}"
    exit 1
  fi
  
  if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
  fi
  
  echo -e "${GREEN}✓ All dependencies found${NC}"
}

# Test connectivity
test_connectivity() {
  echo ""
  echo "Testing connectivity..."
  
  # Test npm
  if curl -s -o /dev/null -w "%{http_code}" "$NPM_URL/react" 2>/dev/null | grep -q "200\|304"; then
    echo -e "${GREEN}✓ npm endpoint reachable${NC}"
  else
    echo -e "${RED}✗ npm endpoint unreachable: $NPM_URL${NC}"
    exit 1
  fi
  
  # Test pypi
  if curl -s -o /dev/null -w "%{http_code}" "$PYPI_URL/simple/requests/" 2>/dev/null | grep -q "200\|304"; then
    echo -e "${GREEN}✓ PyPI endpoint reachable${NC}"
  else
    echo -e "${RED}✗ PyPI endpoint unreachable: $PYPI_URL${NC}"
    exit 1
  fi
  
  # Test maven
  if curl -s -o /dev/null -w "%{http_code}" "$MAVEN_URL/org/springframework/boot/spring-boot-starter-web/maven-metadata.xml" 2>/dev/null | grep -q "200\|304"; then
    echo -e "${GREEN}✓ Maven endpoint reachable${NC}"
  else
    echo -e "${RED}✗ Maven endpoint unreachable: $MAVEN_URL${NC}"
    exit 1
  fi
  
  # Test monitoring endpoint
  if curl -s "$SFW_MONITOR_URL/metrics" | grep -q "node_cpu"; then
    echo -e "${GREEN}✓ SFW monitoring endpoint reachable${NC}"
  else
    echo -e "${YELLOW}⚠ Warning: SFW monitoring endpoint not responding${NC}"
    echo "  Metrics collection may be incomplete"
  fi
}

# Warmup phase
run_warmup() {
  if [ "$SKIP_WARMUP" = true ]; then
    echo ""
    echo "Skipping warmup phase..."
    return
  fi
  
  echo ""
  echo "Running warmup phase (30 seconds at 10% target RPS)..."
  
  WARMUP_RPS=$((TARGET_RPS / 10))
  if [ $WARMUP_RPS -lt 10 ]; then
    WARMUP_RPS=10
  fi
  
  k6 run \
    --quiet \
    -e NPM_URL="$NPM_URL" \
    -e PYPI_URL="$PYPI_URL" \
    -e MAVEN_URL="$MAVEN_URL" \
    -e TARGET_RPS="$WARMUP_RPS" \
    -e DURATION="30s" \
    -e VUS="10" \
    -e MAX_VUS="50" \
    -e CACHE_HIT_PCT="$CACHE_HIT_PCT" \
    -e TEST_ID="${TEST_ID}-warmup" \
    -e LOAD_GEN_ID="$LOAD_GEN_ID" \
    socket-firewall-loadtest-distributed.js
  
  echo -e "${GREEN}✓ Warmup complete${NC}"
  echo "Waiting 10 seconds before main test..."
  sleep 10
}

# Collect system metrics
collect_system_metrics() {
  local metrics_file="$RESULTS_DIR/${TEST_ID}_${LOAD_GEN_ID}_system_metrics.jsonl"
  local interval=5  # Collect every 5 seconds
  
  echo ""
  echo "Starting system metrics collection..."
  echo "Metrics file: $metrics_file"
  
  (
    while true; do
      timestamp=$(date -u +%s)
      
      # Fetch metrics from node_exporter
      metrics=$(curl -s "$SFW_MONITOR_URL/metrics" 2>/dev/null || echo "")
      
      if [ -n "$metrics" ]; then
        # Parse CPU usage
        cpu_idle=$(echo "$metrics" | grep 'node_cpu_seconds_total{.*mode="idle"' | awk '{sum+=$2} END {print sum}')
        cpu_total=$(echo "$metrics" | grep 'node_cpu_seconds_total' | awk '{sum+=$2} END {print sum}')
        
        # Parse memory
        mem_total=$(echo "$metrics" | grep 'node_memory_MemTotal_bytes' | awk '{print $2}')
        mem_available=$(echo "$metrics" | grep 'node_memory_MemAvailable_bytes' | awk '{print $2}')
        
        # Parse load average
        load_1m=$(echo "$metrics" | grep 'node_load1' | awk '{print $2}')
        load_5m=$(echo "$metrics" | grep 'node_load5' | awk '{print $2}')
        load_15m=$(echo "$metrics" | grep 'node_load15' | awk '{print $2}')
        
        # Parse network
        net_rx=$(echo "$metrics" | grep 'node_network_receive_bytes_total' | awk '{sum+=$2} END {print sum}')
        net_tx=$(echo "$metrics" | grep 'node_network_transmit_bytes_total' | awk '{sum+=$2} END {print sum}')
        
        # Write to file
        echo "{\"timestamp\":$timestamp,\"cpu_idle\":$cpu_idle,\"cpu_total\":$cpu_total,\"mem_total\":$mem_total,\"mem_available\":$mem_available,\"load_1m\":$load_1m,\"load_5m\":$load_5m,\"load_15m\":$load_15m,\"net_rx\":$net_rx,\"net_tx\":$net_tx}" >> "$metrics_file"
      fi
      
      sleep $interval
    done
  ) &
  
  METRICS_PID=$!
  echo "System metrics collection started (PID: $METRICS_PID)"
}

# Stop metrics collection
stop_metrics_collection() {
  if [ -n "$METRICS_PID" ]; then
    echo ""
    echo "Stopping metrics collection..."
    kill $METRICS_PID 2>/dev/null || true
    wait $METRICS_PID 2>/dev/null || true
    echo -e "${GREEN}✓ Metrics collection stopped${NC}"
  fi
}

# Run main load test
run_load_test() {
  echo ""
  echo "========================================"
  echo "Starting main load test"
  echo "Target RPS: $TARGET_RPS"
  echo "Duration: $DURATION"
  echo "========================================"
  echo ""
  
  # Calculate VUs
  VUS=$((TARGET_RPS / 10))
  MAX_VUS=$((TARGET_RPS / 3))
  
  if [ $VUS -lt 50 ]; then
    VUS=50
  fi
  
  if [ $MAX_VUS -lt 100 ]; then
    MAX_VUS=100
  fi
  
  RESULT_FILE="$RESULTS_DIR/${TEST_ID}_${LOAD_GEN_ID}_k6_results.json"
  SUMMARY_FILE="$RESULTS_DIR/${TEST_ID}_${LOAD_GEN_ID}_k6_summary.txt"
  
  # Start metrics collection
  collect_system_metrics
  
  # Trap to ensure metrics collection stops
  trap stop_metrics_collection EXIT INT TERM
  
  # Run k6 test
  k6 run \
    --out json="$RESULT_FILE" \
    --summary-export="$SUMMARY_FILE" \
    -e NPM_URL="$NPM_URL" \
    -e PYPI_URL="$PYPI_URL" \
    -e MAVEN_URL="$MAVEN_URL" \
    -e TARGET_RPS="$TARGET_RPS" \
    -e DURATION="$DURATION" \
    -e VUS="$VUS" \
    -e MAX_VUS="$MAX_VUS" \
    -e CACHE_HIT_PCT="$CACHE_HIT_PCT" \
    -e TEST_ID="$TEST_ID" \
    -e LOAD_GEN_ID="$LOAD_GEN_ID" \
    socket-firewall-loadtest-distributed.js
  
  # Stop metrics collection
  stop_metrics_collection
  
  echo ""
  echo "========================================"
  echo -e "${GREEN}Load test complete!${NC}"
  echo "========================================"
  echo ""
  echo "Results:"
  echo "  k6 results:     $RESULT_FILE"
  echo "  k6 summary:     $SUMMARY_FILE"
  echo "  System metrics: $RESULTS_DIR/${TEST_ID}_${LOAD_GEN_ID}_system_metrics.jsonl"
  echo "  Log file:       $LOG_FILE"
  echo ""
}

# Main execution
main() {
  check_dependencies
  test_connectivity
  run_warmup
  run_load_test
  
  echo "Next steps:"
  echo "1. If running on multiple load generators, wait for all to complete"
  echo "2. Aggregate results with: ./aggregate-results.py $TEST_ID"
  echo "3. Generate report with: ./generate-comprehensive-report.py $TEST_ID"
  echo ""
}

main
