# Socket Firewall Docker Compose Resource Configurations

Reference configurations for deploying Socket Firewall with different resource tiers.

## Configuration Tiers

### 1 CPU / 1GB RAM
**File:** `socket.yml.1cpu-1gb`

- **Use case:** Small development/testing environments, low traffic
- **Limits:** 1.0 CPU, 768M RAM
- **Reservations:** 0.5 CPU, 512M RAM
- **Expected throughput:** ~500 RPS

### 2 CPU / 2GB RAM
**File:** `socket.yml.2cpu-2gb`

- **Use case:** Standard development/staging environments, moderate traffic
- **Limits:** 2.0 CPU, 1792M RAM
- **Reservations:** 1.0 CPU, 1280M RAM
- **Expected throughput:** ~1,000-2,000 RPS

### 4 CPU / 4GB RAM
**File:** `socket.yml.4cpu-4gb`

- **Use case:** Production environments, high traffic
- **Limits:** 4.0 CPU, 3840M RAM
- **Reservations:** 2.0 CPU, 2560M RAM
- **Expected throughput:** ~5,000-10,000 RPS

### 8 CPU / 8GB RAM
**File:** `socket.yml.8cpu-8gb`

- **Use case:** High-volume production environments, very high traffic
- **Limits:** 8.0 CPU, 7936M RAM
- **Reservations:** 4.0 CPU, 5120M RAM
- **Expected throughput:** ~15,000-20,000 RPS

## Key Design Principles

### Memory Allocation
- **OS Overhead:** Always leave ~256MB for OS overhead
- **Calculation:** `memory_limit = total_ram - 256M`
- **Reservations:** ~64-67% of limit provides buffer for burst traffic

### CPU Allocation
- **Reservations:** 50% of limit ensures minimum guaranteed performance
- **Limits:** Full CPU count allows burst capacity
- **Match to socket.yml:** Use `socket.yml.1cpu-1gb` with 1 CPU config, `socket.yml.2cpu-2gb` with 2 CPU config, etc.

### Resource Matching
When deploying Socket Firewall:
1. Choose appropriate tier based on expected traffic
2. Copy corresponding `socket.yml.*` content into your docker-compose.yml
3. Place under your socket service definition

## Usage Example

```yaml
version: '3.8'

services:
  socket-firewall:
    image: socket/firewall:latest
    ports:
      - "3128:3128"
    environment:
      - SOCKET_API_KEY=${SOCKET_API_KEY}
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 3840M
        reservations:
          cpus: '2.0'
          memory: 2560M
```

## Load Testing Recommendations

### Starting Configuration
- Begin with **1 CPU / 1GB** tier for initial testing
- Run baseline test at 500 RPS
- Monitor CPU and memory utilization

### Scaling Tests
1. **Test progression:** 500 → 1,000 → 2,000 → 5,000 → 10,000 RPS
2. **Upgrade tier** when CPU consistently exceeds 80%
3. **Retest** at same RPS level with new configuration
4. **Document** performance at each tier

### Monitoring Thresholds
- **CPU Usage:** Should stay below 80% at sustained load
- **Memory Usage:** Should stay below 90% of limit
- **Error Rate:** Should remain below 0.1%
- **P95 Latency:** Should stay under 200ms

## Testing Matrix

| Tier | RPS Range | Duration | Expected CPU | Expected Memory |
|------|-----------|----------|--------------|-----------------|
| 1 CPU / 1GB | 100-500 | 5m-1h | 60-80% | 400-600M |
| 2 CPU / 2GB | 500-2,000 | 5m-1h | 60-80% | 800-1,400M |
| 4 CPU / 4GB | 2,000-10,000 | 5m-1h | 60-80% | 2,000-3,200M |
| 8 CPU / 8GB | 10,000-20,000 | 5m-1h | 60-80% | 4,000-6,400M |

## Notes

- These configurations are based on Socket Firewall performance testing
- Actual throughput depends on cache hit rate, network latency, and package sizes
- Monitor metrics during tests and adjust reservations as needed
- For production, consider adding 20-30% headroom beyond expected peak load
