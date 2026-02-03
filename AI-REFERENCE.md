# AI-REF: Socket Firewall Load Test

**IMPORTANT: Before doing anything, scroll to the bottom and check the "Completed Tasks" section to see what's already done and where you left off!**

## PURPOSE
Distributed load test for Socket Registry Firewall (npm/PyPI/Maven proxies). Multi-node RPS testing with metrics + HTML reports.

## ARCH
LoadGen[1..N]->SFW:3128->Registries | Metrics:5s->NodeExporter:9100->JSONL | Results->Aggregate->HTML

## FILES
- run-distributed-test.sh: Orchestrator (deps→connect→warmup→metrics→k6→save)
- socket-firewall-loadtest-distributed.js: k6 multi-ecosystem loader
- setup-sfw-monitoring.sh: Install node_exporter, systemd service, port 9100
- generate-comprehensive-report.py: Parse k6+metrics→HTML graphs
- generate-report-simple.py: Wrapper for comprehensive gen
- aggregate-results.py: Combine multi-node results by test_id

## CONFIGS
socket.yml tiers: 1cpu-1gb(500RPS), 2cpu-2gb(1k-2k), 4cpu-4gb(5k-10k), 8cpu-8gb(15k-20k)
Mem=RAM-256M | CPU_res=50% | Mem_res=64-67%

## FLOW
Input: --rps N --duration D --test-id ID
ENV: NPM_URL,PYPI_URL,MAVEN_URL,SFW_MONITOR_URL,CACHE_HIT_PCT,RESULTS_DIR,LOAD_GEN_ID
Steps: validate_deps→connectivity→warmup(30s@10%)→metrics_start→k6→metrics_stop→save
Output: {id}_{gen}_k6_results.json, {id}_{gen}_system_metrics.jsonl, {id}_{gen}_k6_summary.txt, {id}_{gen}.log
VUS=max(RPS/10,50), MAX_VUS=max(RPS/3,100)

## METRICS
Collect@5s: cpu_idle,cpu_total,mem_total,mem_available,load_1/5/15,net_rx/tx
k6_JSONL: http_req_duration,http_reqs,errors,cache_hits,metadata_latency,download_latency

## THRESHOLDS
Good: err<1%, P95<500ms, P99<1s, CPU<80%
Warn: err 1-5%, P95 500-1000ms, CPU>80%
Poor: err>5%, P95>1s, CPU>90%

## SCALING
|RPS|Gens|RPS/Gen|Config|
|500|1|500|1cpu|
|1k|1|1k|2cpu|
|5k|2-3|1667-2500|4cpu|
|10k|3-4|2500-3333|4cpu|
|20k|5-6|3333-4000|8cpu|

## ECOSYSTEMS
npm(40%): GET /{pkg}, GET /{pkg}/-/{pkg}-{ver}.tgz
pypi(30%): GET /simple/{pkg}/, GET /pypi/{pkg}/json
maven(30%): GET /org/.../maven-metadata.xml, GET /.../artifact-ver.jar
Cache_sim: CACHE_HIT_PCT% reuse recent, rest random

## SETUP
```bash
# Always create and activate .venv first
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## CMDS
```bash
./run-distributed-test.sh --rps 1000 --duration 5m [--test-id ID] [--skip-warmup]
./generate-report-simple.py test-id total-rps
python3 aggregate-results.py test-id
socket-load-test test --rps 1000 --duration 5m
socket-load-test report --test-id ID
socket-load-test validate
```

## TROUBLESHOOT
- No results: ls load-test-results/*_k6_results.json
- Monitor fail: systemctl status node_exporter; curl IP:9100/metrics
- High errors: Check SFW logs, reduce RPS, verify upstream

---

# REFACTOR: Python CLI Module

## TARGET_ARCH
```
socket_load_test/
├── __init__.py, __main__.py, cli.py, config.py
├── core/
│   ├── infrastructure/{base,ssh,minikube,gke}.py
│   ├── load/{generator,orchestrator,aggregator,k6_wrapper}.py
│   ├── reporting/{parser,aggregator,html_generator,templates/}
│   └── monitoring/{collector,exporter}.py
└── utils/{ssh_manager,validation,logging}.py
```

## CONFIG_SCHEMA
```yaml
infrastructure:
  type: ssh|minikube|gke
  ssh: {firewall_server:{host,port:22,user,key_file?,password?}, load_generators:[{host,port,user,key_file?,password?}]}
  minikube: {profile:minikube, context?}
  gke: {project_id, cluster_name, zone, credentials_file?}
test: {rps, duration, test_id?, warmup:true, warmup_duration:30s, warmup_rps_percent:10}
registries: {npm_url, pypi_url, maven_url, cache_hit_percent:30}
traffic: {cache_ratio:30, npm_ratio:40, pypi_ratio:30, maven_ratio:30, metadata_only:false}
monitoring: {enabled:true, interval_seconds:5, node_exporter_port:9100}
results: {output_dir:./load-test-results, auto_generate_html:true, auto_aggregate:true}
```

## TASKS

### P1: Foundation (4-6h)
T1.1: Package struct (socket_load_test/core/{infrastructure,load,reporting,monitoring}/, utils/, tests/), setup.py, pyproject.toml, requirements.txt(click,paramiko,kubernetes,google-cloud-container,pyyaml,jinja2) | Deps:None
T1.2: Config system (config.py:Config class, YAML/JSON load, schema validation, env override) | Deps:T1.1
T1.3: Logging+utils (utils/logging.py, utils/validation.py) | Deps:T1.1

### P2: Infrastructure (8-12h)
T2.1: BaseInfrastructure ABC (core/infrastructure/base.py: connect,validate_connectivity,setup_monitoring,execute_command,transfer_file,get_firewall_endpoint,get_monitoring_endpoint,get_load_generators,cleanup) | Deps:T1.1,T1.2
T2.2: SSHInfrastructure (core/infrastructure/ssh.py, utils/ssh_manager.py: paramiko, key+password auth, multi-gen support, connection pooling, SFTP) | Deps:T2.1
T2.3: MinikubeInfra (core/infrastructure/minikube.py: kubectl commands, deployments/services/jobs, ConfigMaps, PVC) | Deps:T2.1
T2.4: GKEInfra (core/infrastructure/gke.py: google-cloud-container, service account auth, similar to minikube) | Deps:T2.1

### P3: Load Testing (10-14h)
T3.1: K6Manager (core/load/k6_wrapper.py: embed k6 script template, Jinja2 params, transfer, validate) | Deps:T1.1
T3.2: LoadGenerator (core/load/generator.py: single-node exec, warmup, metrics collection, save results) | Deps:T3.1,T2.1
T3.3: Orchestrator (core/load/orchestrator.py: multi-node parallel exec, RPS distribution, sync start, result collection) | Deps:T3.2,T2.1
T3.4: Aggregator (core/load/aggregator.py: find {test_id}_*, merge JSONL, combine stats, output aggregated JSON) | Deps:T3.2
T3.5: Advanced traffic options (extend T3.1+T5.2: --cache-ratio, --npm-ratio, --pypi-ratio, --maven-ratio, --metadata-only, pass to k6 template) | Deps:T3.1,T5.2

### P4: Monitoring+Reporting (8-10h)
T4.1: MetricsCollector (core/monitoring/collector.py: query node_exporter@5s, parse Prometheus, save JSONL, background thread) | Deps:T1.1
T4.2: ExporterSetup (core/monitoring/exporter.py: install node_exporter, systemd service, firewall port 9100) | Deps:T2.1
T4.3: ResultParser (core/reporting/parser.py: parse k6 JSONL+metrics JSONL, calc P50/90/95/99, ecosystem breakdown, timeline) | Deps:T4.1
T4.4: HTMLGenerator (core/reporting/html_generator.py: Jinja2 templates, Chart.js graphs, single-file HTML) | Deps:T4.3
T4.5: AutoReport (integrate into orchestrator, auto-aggregate+parse+generate HTML) | Deps:T4.4,T3.4

### P5: CLI (6-8h)
T5.1: CLI framework (cli.py:Click, __main__.py, commands:{test,report,setup,validate,aggregate}, global:{--config,--verbose,--log-file}) | Deps:T1.1,T1.2
T5.2: TestCmd (socket-load-test test: load config, init infra, validate, setup monitoring, orchestrate, aggregate, report, summary) | Deps:T5.1,T3.3,T4.5
T5.3: ReportCmd (socket-load-test report --test-id ID [--config-file F] [--output O]: gen from existing) | Deps:T5.1,T4.4
T5.4: SetupCmd (socket-load-test setup {monitoring,ssh-keys}: install node_exporter, setup SSH keys) | Deps:T5.1,T4.2,T2.2
T5.5: ValidateCmd (socket-load-test validate: check config, connectivity, deps, monitoring, registries) | Deps:T5.1,T2.1

### P6: Testing+Docs (8-10h)
T6.1: Unit tests (tests/test_*.py: pytest, pytest-mock, 70%+ coverage, mock infra/SSH) | Deps:All_impl
T6.2: Integration tests (tests/integration/: SSH workflow, report gen with fixtures) | Deps:T6.1
T6.3: Docs (README+SETUP update, examples/, API docs, MIGRATION.md) | Deps:All
T6.4: Backward compat (keep old scripts, deprecation warnings, migration guide) | Deps:All_impl

### P7: Future (TBD)
T7.1: Web UI dashboard
T7.2: Real-time monitoring
T7.3: DB backend
T7.4: CI/CD integration

## DEPS_TREE
```
P1: T1.1→T1.2,T1.3
P2: T2.1(T1.1,T1.2)→T2.2,T2.3,T2.4
P3: T3.1(T1.1), T3.2(T3.1,T2.1)→T3.3,T3.4, T3.5(T3.1,T5.2)
P4: T4.1(T1.1), T4.2(T2.1), T4.3(T4.1)→T4.4→T4.5(T4.4,T3.4)
P5: T5.1(T1.1,T1.2)→T5.2(T3.3,T4.5),T5.3(T4.4),T5.4(T4.2,T2.2),T5.5(T2.1)
P6: T6.1(All)→T6.2,T6.3,T6.4
```

## IMPL_ORDER
D1-2:T1.1,T1.2,T1.3 | D3-4:T2.1,T2.2 | D5-7:T3.1,T3.2,T3.3,T3.4 | D8-9:T4.1,T4.2 | D10-11:T4.3,T4.4,T4.5 | D12-14:T5.1-T5.5,T3.5 | D15-17:T2.3,T2.4 | D18-20:T6.1-T6.4

## INTERFACES

BaseInfrastructure ABC:
```python
connect()->None
validate_connectivity()->bool
setup_monitoring(target:str)->None
execute_command(target:str,cmd:str,bg:bool=False)->dict{stdout,stderr,exit_code}
transfer_file(local:str,remote:str,target:str)->None
get_firewall_endpoint()->str
get_monitoring_endpoint()->str
get_load_generators()->List[str]
cleanup()->None
```

ResultParser output:
```python
{
  summary:{total_requests,total_duration,rps,error_rate,success_rate},
  latencies:{p50,p90,p95,p99,avg,min,max},
  ecosystem_breakdown:{npm:{requests,errors,avg_latency},pypi:{},maven:{}},
  timeline:[{timestamp,rps,latency_p95,errors}],
  system_metrics:[{timestamp,cpu_pct,mem_pct,net_rx_mbps,net_tx_mbps}]
}
```

## CLI_USAGE
```bash
socket-load-test [--config F] [--verbose] test [--rps N] [--duration D] [--test-id ID] [--no-warmup] [--no-auto-report] [--cache-ratio PCT] [--npm-ratio PCT] [--pypi-ratio PCT] [--maven-ratio PCT] [--metadata-only]
socket-load-test report --test-id ID [--output F] [--config-file F]
socket-load-test setup {monitoring|ssh-keys}
socket-load-test validate
socket-load-test aggregate --test-id ID
```

## GUIDELINES
Style: PEP8, type hints, Google docstrings, Black, pylint, max_line:100
Errors: Custom exceptions, helpful messages, fail fast, validate early
Security: No log passwords, validate paths, parameterized cmds, SSH key perms 600
Performance: Connection pooling, parallel exec, streaming, lazy loading

## SUCCESS_CRITERIA
- Zero to test in <10min
- 99% success rate
- <5% overhead
- New infra type in <4h
- 70%+ test coverage
- Works on macOS/Linux/Windows(WSL)

## MIGRATION
Old: ./run-distributed-test.sh + env vars + manual aggregate + manual report
New: socket-load-test --config config.yaml test (auto everything)

## PROGRESS_TRACKING
**IMPORTANT: Always update this section after completing any task!**

### Completed Tasks
- ✅ T1.1: Package struct (socket_load_test/ with core/{infrastructure,load,reporting,monitoring}/, utils/, tests/) - DONE
- ✅ setup.py, pyproject.toml, requirements.txt with all dependencies - DONE
- ✅ T1.2: Config system (Config class, YAML/JSON load, schema validation, env override) - DONE
  - Implemented comprehensive dataclass-based config system
  - YAML/JSON loading with auto-detect
  - Schema validation for all config sections (SSH, Minikube, GKE, Test, Registries, Traffic, Monitoring, Results)
  - Environment variable override support (SOCKET_LOADTEST_*)
  - 37 unit tests with 100% test coverage
  - Example config files for SSH, Minikube, and GKE
- ✅ T1.3: Logging+utils (utils/logging.py, utils/validation.py) - DONE
  - Implemented comprehensive logging utilities:
    - SensitiveDataFilter: Filters passwords, keys, tokens from logs
    - ContextLogger: Adds contextual information to log messages
    - setup_logging(): Configurable console/file logging with filtering
    - Log level management functions
  - Implemented comprehensive validation utilities:
    - Numeric validators (positive int/float, percentage, RPS, port)
    - Duration parsing/formatting (30s, 5m, 2h, 1d)
    - URL validation with scheme checking
    - Path validation (existence, type, creation)
    - Hostname, test ID, ratio sum validators
  - 81 unit tests with 97% test coverage
  - All tests passing
- ✅ T2.1: BaseInfrastructure ABC - DONE
  - Implemented abstract base class with all required methods
  - Methods: connect, validate_connectivity, setup_monitoring, execute_command, transfer_file
  - Methods: get_firewall_endpoint, get_monitoring_endpoint, get_load_generators, cleanup
  - Full type hints and Google-style docstrings
  - 6 comprehensive unit tests with ConcreteInfrastructure implementation
  - All tests passing with 70% coverage of base.py
- ✅ T2.2: SSHInfrastructure - DONE
  - Implemented SSHManager with connection pooling (utils/ssh_manager.py):
    - Connection pool for managing multiple SSH connections
    - Supports both password and key-based authentication
    - Connection reuse and lifecycle management
    - Command execution with timeout support
    - SFTP file transfers with automatic remote directory creation
    - Thread-safe operations with lock protection
    - Context manager support for automatic cleanup
    - 82% test coverage with 18 unit tests
  - Implemented SSHInfrastructure (core/infrastructure/ssh.py):
    - Manages firewall server and multiple load generator connections
    - Full BaseInfrastructure ABC implementation
    - Connectivity validation across all nodes
    - Command execution on firewall or specific load generators
    - File transfer to any node in the infrastructure
    - Background process support via nohup
    - Monitoring setup capabilities
    - 96% test coverage with 24 unit tests (including integration tests)
  - All 42 tests passing

### Current Task
- 🔄 T3.1: K6Manager

### Next Tasks
- T2.2: SSHInfrastructure (core/infrastructure/ssh.py, utils/ssh_manager.py: paramiko, key+password auth, multi-gen support, connection pooling, SFTP)
- T3.1: K6Manager (core/load/k6_wrapper.py: embed k6 script template, Jinja2 params, transfer, validate)

## NEXT
Start: "next task" or "implement T1.2"
