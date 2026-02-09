"""
Comprehensive Load Test Report Generator for Socket Firewall
Generates detailed HTML reports with system metrics, graphs, and per-RPS sections
"""

import json
import os
import glob
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import statistics

def parse_k6_json(filepath):
    """Parse k6 JSON output and extract metrics"""
    metrics = defaultdict(list)
    timeline = defaultdict(lambda: defaultdict(list))
    
    with open(filepath, 'r') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get('type') != 'Point':
                    continue
                
                metric_name = data.get('metric')
                value = data.get('data', {}).get('value')
                tags = data.get('data', {}).get('tags', {})
                timestamp = data.get('data', {}).get('time')
                
                # EXCLUDE setup phase metrics - only include load test metrics
                group = tags.get('group', '')
                if group == '::setup':
                    continue
                
                if metric_name and value is not None:
                    metrics[metric_name].append({
                        'value': value,
                        'tags': tags,
                        'time': timestamp
                    })
                    
                    # Build timeline for charts
                    if timestamp:
                        timeline[metric_name][timestamp].append(value)
            except json.JSONDecodeError:
                continue
    
    return metrics, timeline


def parse_system_metrics(filepath):
    """Parse system metrics JSONL file"""
    metrics = []
    
    if not Path(filepath).exists():
        return metrics
    
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                # Only add if it's a dict with expected structure
                if isinstance(data, dict):
                    metrics.append(data)
            except json.JSONDecodeError as e:
                # Skip malformed lines
                print(f"Warning: Skipping malformed line {line_num} in {filepath}: {e}")
                continue
            except Exception as e:
                print(f"Warning: Error processing line {line_num} in {filepath}: {e}")
                continue
    
    return metrics


def calculate_percentile(values, percentile):
    """Calculate percentile"""
    if not values:
        return 0
    sorted_values = sorted(values)
    index = int(len(sorted_values) * percentile / 100)
    if index >= len(sorted_values):
        index = len(sorted_values) - 1
    return sorted_values[index]


def format_bytes(bytes_value):
    """Format bytes into human-readable format (KB, MB, GB)"""
    if bytes_value < 1024:
        return f"{bytes_value:.0f} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.2f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"


def analyze_k6_metrics(metrics):
    """Analyze k6 metrics and return statistics"""
    stats = {}
    
    # HTTP request duration
    if 'http_req_duration' in metrics:
        durations = [m['value'] for m in metrics['http_req_duration']]
        stats['http_req_duration'] = {
            'min': min(durations),
            'max': max(durations),
            'avg': statistics.mean(durations),
            'median': statistics.median(durations),
            'p10': calculate_percentile(durations, 10),
            'p50': calculate_percentile(durations, 50),
            'p75': calculate_percentile(durations, 75),
            'p90': calculate_percentile(durations, 90),
            'p95': calculate_percentile(durations, 95),
            'p99': calculate_percentile(durations, 99),
            'stddev': statistics.stdev(durations) if len(durations) > 1 else 0,
        }
    
    # Metadata latency
    if 'metadata_latency' in metrics:
        latencies = [m['value'] for m in metrics['metadata_latency']]
        stats['metadata_latency'] = {
            'avg': statistics.mean(latencies),
            'p10': calculate_percentile(latencies, 10),
            'p50': calculate_percentile(latencies, 50),
            'p75': calculate_percentile(latencies, 75),
            'p95': calculate_percentile(latencies, 95),
            'p99': calculate_percentile(latencies, 99),
        }
    
    # Download latency
    if 'download_latency' in metrics:
        latencies = [m['value'] for m in metrics['download_latency']]
        stats['download_latency'] = {
            'avg': statistics.mean(latencies),
            'p10': calculate_percentile(latencies, 10),
            'p50': calculate_percentile(latencies, 50),
            'p75': calculate_percentile(latencies, 75),
            'p95': calculate_percentile(latencies, 95),
            'p99': calculate_percentile(latencies, 99),
        }
    
    # Metadata request duration (separate from http_req_duration to exclude downloads)
    if 'metadata_request_duration' in metrics:
        durations = [m['value'] for m in metrics['metadata_request_duration']]
        # Count timeouts (requests at or near timeout threshold)
        # Note: setup uses 30s, metadata uses 60s, downloads use 120s
        timeout_threshold = 59900  # 59.9s to catch 60s timeouts
        timeout_count = sum(1 for d in durations if d >= timeout_threshold)
        timeout_percentage = (timeout_count / len(durations) * 100) if durations else 0
        
        stats['metadata_request_duration'] = {
            'min': min(durations),
            'max': max(durations),
            'avg': statistics.mean(durations),
            'median': statistics.median(durations),
            'p10': calculate_percentile(durations, 10),
            'p50': calculate_percentile(durations, 50),
            'p75': calculate_percentile(durations, 75),
            'p90': calculate_percentile(durations, 90),
            'p95': calculate_percentile(durations, 95),
            'p99': calculate_percentile(durations, 99),
            'stddev': statistics.stdev(durations) if len(durations) > 1 else 0,
            'timeout_count': timeout_count,
            'timeout_percentage': timeout_percentage,
        }
    
    # Download request duration (separate from http_req_duration)
    if 'download_request_duration' in metrics:
        durations = [m['value'] for m in metrics['download_request_duration']]
        stats['download_request_duration'] = {
            'min': min(durations),
            'max': max(durations),
            'avg': statistics.mean(durations),
            'median': statistics.median(durations),
            'p10': calculate_percentile(durations, 10),
            'p50': calculate_percentile(durations, 50),
            'p75': calculate_percentile(durations, 75),
            'p90': calculate_percentile(durations, 90),
            'p95': calculate_percentile(durations, 95),
            'p99': calculate_percentile(durations, 99),
            'stddev': statistics.stdev(durations) if len(durations) > 1 else 0,
        }
        
        # Calculate download speeds from duration and bandwidth
        # Speed = bytes / seconds
        # Both metrics are emitted together in the same order, so match by index
        if 'response_bytes' in metrics:
            # Get download bytes in order
            download_bytes_list = [m for m in metrics['response_bytes'] 
                                  if m.get('tags', {}).get('type') == 'download']
            
            download_durations_list = list(metrics['download_request_duration'])
            
            # Match by index since they're emitted in the same order
            if download_bytes_list and download_durations_list and len(download_bytes_list) == len(download_durations_list):
                speeds = []
                # Size buckets: <100KB, 100KB-1MB, 1-10MB, >10MB
                size_buckets = {
                    '<100KB': {'sizes': [], 'durations': [], 'speeds': []},
                    '100KB-1MB': {'sizes': [], 'durations': [], 'speeds': []},
                    '1-10MB': {'sizes': [], 'durations': [], 'speeds': []},
                    '>10MB': {'sizes': [], 'durations': [], 'speeds': []},
                }
                
                for i in range(len(download_bytes_list)):
                    bytes_transferred = download_bytes_list[i]['value']
                    duration_ms = download_durations_list[i]['value']
                    
                    if duration_ms > 0:
                        duration_s = duration_ms / 1000  # convert ms to seconds
                        speed_bps = bytes_transferred / duration_s  # bytes per second
                        speeds.append(speed_bps)
                        
                        # Categorize by size bucket
                        if bytes_transferred < 100 * 1024:  # <100KB
                            bucket = '<100KB'
                        elif bytes_transferred < 1024 * 1024:  # 100KB-1MB
                            bucket = '100KB-1MB'
                        elif bytes_transferred < 10 * 1024 * 1024:  # 1-10MB
                            bucket = '1-10MB'
                        else:  # >10MB
                            bucket = '>10MB'
                        
                        size_buckets[bucket]['sizes'].append(bytes_transferred)
                        size_buckets[bucket]['durations'].append(duration_ms)
                        size_buckets[bucket]['speeds'].append(speed_bps)
                
                if speeds:
                    stats['download_speed'] = {
                        'avg': statistics.mean(speeds),
                        'min': min(speeds),
                        'max': max(speeds),
                        'p10': calculate_percentile(speeds, 10),
                        'p50': calculate_percentile(speeds, 50),
                        'p75': calculate_percentile(speeds, 75),
                        'p95': calculate_percentile(speeds, 95),
                        'p99': calculate_percentile(speeds, 99),
                    }
                
                # Calculate statistics per bucket
                stats['download_size_buckets'] = {}
                for bucket_name, bucket_data in size_buckets.items():
                    if bucket_data['sizes']:
                        stats['download_size_buckets'][bucket_name] = {
                            'count': len(bucket_data['sizes']),
                            'avg_size': statistics.mean(bucket_data['sizes']),
                            'avg_duration': statistics.mean(bucket_data['durations']),
                            'avg_speed': statistics.mean(bucket_data['speeds']),
                            'p95_duration': calculate_percentile(bucket_data['durations'], 95),
                        }
    
    # Request counts
    stats['total_requests'] = len(metrics.get('http_reqs', []))
    stats['npm_requests'] = sum(1 for m in metrics.get('http_reqs', []) if m['tags'].get('ecosystem') == 'npm')
    stats['pypi_requests'] = sum(1 for m in metrics.get('http_reqs', []) if m['tags'].get('ecosystem') == 'pypi')
    stats['maven_requests'] = sum(1 for m in metrics.get('http_reqs', []) if m['tags'].get('ecosystem') == 'maven')
    
    # Error rate
    if 'errors' in metrics:
        error_values = [m['value'] for m in metrics['errors']]
        stats['error_rate'] = statistics.mean(error_values) if error_values else 0
        stats['total_errors'] = sum(error_values)
    else:
        stats['error_rate'] = 0
        stats['total_errors'] = 0
    
    # HTTP Status Code breakdown
    from collections import Counter
    status_codes = Counter()
    timeout_count = 0
    total_requests = 0
    for m in metrics.get('http_reqs', []):
        status = m.get('tags', {}).get('status')
        if status:
            status_codes[status] += 1
            total_requests += 1
            if status == '0':
                timeout_count += 1
    stats['status_codes'] = dict(status_codes)
    stats['timeout_rate'] = (timeout_count / total_requests * 100) if total_requests > 0 else 0
    stats['timeout_count'] = timeout_count
    
    # Parse new status code counters
    # These are Counter metrics that track specific status code categories
    stats['status_2xx_count'] = sum(m['value'] for m in metrics.get('status_2xx', []))
    stats['status_404_count'] = sum(m['value'] for m in metrics.get('status_404', []))
    stats['status_403_count'] = sum(m['value'] for m in metrics.get('status_403', []))
    stats['status_4xx_count'] = sum(m['value'] for m in metrics.get('status_4xx', []))  # Other 4xx errors
    stats['status_5xx_count'] = sum(m['value'] for m in metrics.get('status_5xx', []))
    stats['status_timeout_count'] = sum(m['value'] for m in metrics.get('status_timeout', []))
    
    # Calculate totals for reporting
    total_counted = (stats['status_2xx_count'] + stats['status_404_count'] + 
                     stats['status_403_count'] + stats['status_4xx_count'] + 
                     stats['status_5xx_count'] + stats['status_timeout_count'])
    if total_counted > 0:
        stats['status_404_pct'] = (stats['status_404_count'] / total_counted) * 100
        stats['status_403_pct'] = (stats['status_403_count'] / total_counted) * 100
    else:
        stats['status_404_pct'] = 0
        stats['status_403_pct'] = 0
    
    # Bandwidth tracking using custom response_bytes Trend metric
    # Trend metrics preserve request tags (type: 'metadata' or 'download')
    if 'response_bytes' in metrics:
        # Separate metadata vs download bandwidth using request type tags
        metadata_bytes = sum(m['value'] for m in metrics['response_bytes'] 
                           if m.get('tags', {}).get('type') == 'metadata')
        download_bytes = sum(m['value'] for m in metrics['response_bytes'] 
                          if m.get('tags', {}).get('type') == 'download')
        total_bytes = sum(m['value'] for m in metrics['response_bytes'])
        
        stats['metadata_bytes'] = metadata_bytes
        stats['download_bytes'] = download_bytes
        stats['total_bytes'] = total_bytes
    # Fallback to data_received if response_bytes not available (old tests)
    elif 'data_received' in metrics:
        total_bytes = sum(m['value'] for m in metrics['data_received'])
        stats['metadata_bytes'] = 0
        stats['download_bytes'] = 0
        stats['total_bytes'] = total_bytes
    else:
        stats['metadata_bytes'] = 0
        stats['download_bytes'] = 0
        stats['total_bytes'] = 0
    
    return stats


def analyze_system_metrics(metrics):
    """Analyze system metrics"""
    if not metrics:
        return {}
    
    stats = {
        'cpu_usage': [],
        'memory_usage': [],
        'load_avg': [],
        'timestamps': []
    }
    
    prev_cpu_idle = None
    prev_cpu_total = None
    
    for m in metrics:
        timestamp = m.get('timestamp', 0)
        stats['timestamps'].append(timestamp)
        
        # CPU usage
        cpu_idle = m.get('cpu_idle', 0)
        cpu_total = m.get('cpu_total', 0)
        
        if prev_cpu_idle is not None and prev_cpu_total is not None:
            cpu_idle_delta = cpu_idle - prev_cpu_idle
            cpu_total_delta = cpu_total - prev_cpu_total
            
            if cpu_total_delta > 0:
                cpu_usage = 100 * (1 - cpu_idle_delta / cpu_total_delta)
                stats['cpu_usage'].append(max(0, min(100, cpu_usage)))
            else:
                stats['cpu_usage'].append(0)
        
        prev_cpu_idle = cpu_idle
        prev_cpu_total = cpu_total
        
        # Memory usage
        mem_total = m.get('mem_total', 0)
        mem_available = m.get('mem_available', 0)
        
        if mem_total > 0:
            mem_used = mem_total - mem_available
            mem_usage_pct = 100 * (mem_used / mem_total)
            stats['memory_usage'].append(mem_usage_pct)
        else:
            stats['memory_usage'].append(0)
        
        # Load average
        load_1m = m.get('load_1m', 0)
        stats['load_avg'].append(load_1m)
    
    # Remove first CPU measurement (no delta available)
    if stats['timestamps']:
        stats['timestamps'] = stats['timestamps'][1:]
    
    # Calculate summary statistics
    if stats['cpu_usage']:
        stats['cpu_avg'] = statistics.mean(stats['cpu_usage'])
        stats['cpu_max'] = max(stats['cpu_usage'])
        stats['cpu_p95'] = calculate_percentile(stats['cpu_usage'], 95)
    
    if stats['memory_usage']:
        stats['mem_avg'] = statistics.mean(stats['memory_usage'])
        stats['mem_max'] = max(stats['memory_usage'])
        stats['mem_p95'] = calculate_percentile(stats['memory_usage'], 95)
    
    if stats['load_avg']:
        stats['load_avg_mean'] = statistics.mean(stats['load_avg'])
        stats['load_avg_max'] = max(stats['load_avg'])
    
    return stats


def aggregate_test_results(test_id, results_dir):
    """Aggregate results from all load generators for a test"""
    pattern = f"{results_dir}/{test_id}_*_k6_results.json"
    result_files = glob.glob(pattern)
    
    if not result_files:
        print(f"No result files found for test ID: {test_id}")
        return None
    
    print(f"Found {len(result_files)} result file(s) for test {test_id}")
    
    # Aggregate k6 metrics
    all_metrics = defaultdict(list)
    
    for filepath in result_files:
        print(f"  Processing {filepath}...")
        metrics, _ = parse_k6_json(filepath)
        
        for metric_name, values in metrics.items():
            all_metrics[metric_name].extend(values)
    
    # Aggregate system metrics
    pattern = f"{results_dir}/{test_id}_*_system_metrics.jsonl"
    system_files = glob.glob(pattern)
    
    all_system_metrics = []
    for filepath in system_files:
        metrics = parse_system_metrics(filepath)
        # Filter out any non-dict items (in case of malformed data)
        valid_metrics = [m for m in metrics if isinstance(m, dict)]
        all_system_metrics.extend(valid_metrics)
    
    # Sort by timestamp (only if we have valid metrics)
    if all_system_metrics:
        all_system_metrics.sort(key=lambda x: x.get('timestamp', 0))
    
    return {
        'metrics': all_metrics,
        'system_metrics': all_system_metrics,
        'num_generators': len(result_files)
    }


def format_duration(ms):
    """Format milliseconds"""
    if ms < 1:
        return f"{ms * 1000:.2f}µs"
    elif ms < 1000:
        return f"{ms:.2f}ms"
    else:
        return f"{ms / 1000:.2f}s"


def generate_html_report(test_configs, results_dir, output_file, test_type="5-Minute", duration_seconds=300, registry_urls=None):
    """Generate comprehensive HTML report"""
    
    # Set default registry URLs if not provided
    if registry_urls is None:
        registry_urls = {}
    
    print(f"Generating {test_type} Test Report...")
    
    # Collect all test data
    all_test_data = []
    
    for config in test_configs:
        test_id = config['test_id']
        target_rps = config['rps']
        
        print(f"  Aggregating results for {target_rps} RPS (test ID: {test_id})...")
        
        aggregated = aggregate_test_results(test_id, results_dir)
        if not aggregated:
            print(f"    Warning: No results found for {target_rps} RPS")
            continue
        
        k6_stats = analyze_k6_metrics(aggregated['metrics'])
        system_stats = analyze_system_metrics(aggregated['system_metrics'])
        
        all_test_data.append({
            'rps': target_rps,
            'test_id': test_id,
            'k6_stats': k6_stats,
            'system_stats': system_stats,
            'num_generators': aggregated['num_generators'],
            'system_metrics_raw': aggregated['system_metrics']
        })
    
    if not all_test_data:
        print("No test data to generate report")
        return
    
    # Sort by RPS
    all_test_data.sort(key=lambda x: x['rps'])
    
    # Generate HTML
    html = generate_html_content(all_test_data, test_type, duration_seconds)
    
    # Write file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Report generated: {output_file}")


def generate_html_content(all_test_data, test_type, duration_seconds=300):
    """Generate HTML content for report"""
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Prepare summary data
    rps_list = [str(d['rps']) for d in all_test_data]
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Socket Registry Firewall - {test_type} Load Test Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 32px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
            font-size: 24px;
        }}
        h3 {{
            color: #2c3e50;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 20px;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        .overview {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 30px;
        }}
        .overview h2 {{
            margin-top: 0;
            border-bottom: none;
        }}
        .overview p {{
            margin: 10px 0;
            color: #2c3e50;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            color: white;
            font-size: 14px;
            margin: 0 0 10px 0;
            text-transform: uppercase;
            opacity: 0.9;
        }}
        .metric-card .value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .metric-card .unit {{
            font-size: 16px;
            opacity: 0.8;
            margin-left: 5px;
        }}
        .rps-section {{
            background: #fff;
            margin: 40px 0;
            padding: 30px;
            border: 2px solid #3498db;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .rps-section h2 {{
            margin-top: 0;
            color: #3498db;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 30px;
            margin: 30px 0;
        }}
        .chart-container {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .chart-container h3 {{
            color: #2c3e50;
            margin: 0 0 15px 0;
            font-size: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background: #34495e;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .good {{ color: #27ae60; font-weight: bold; }}
        .warning {{ color: #f39c12; font-weight: bold; }}
        .bad {{ color: #e74c3c; font-weight: bold; }}
        .info-box {{
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            color: #7f8c8d;
            font-size: 14px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Socket Registry Firewall</h1>
        <h1>{test_type} Load Test Report</h1>
        <p class="subtitle">Generated on {timestamp}</p>
'''
    
    # Overview section
    html += '''
        <div class="overview">
            <h2>Test Overview</h2>
            <p><strong>Test Type:</strong> ''' + test_type + ''' Load Test</p>
            <p><strong>Purpose:</strong> Evaluate Socket Firewall performance under sustained load across multiple RPS levels</p>'''
    
    # Add ecosystem information if registry URLs are provided
    if registry_urls:
        ecosystems_info = []
        if 'npm' in registry_urls:
            ecosystems_info.append(f"npm ({registry_urls['npm']})")
        if 'pypi' in registry_urls:
            ecosystems_info.append(f"PyPI ({registry_urls['pypi']})")
        if 'maven' in registry_urls:
            ecosystems_info.append(f"Maven ({registry_urls['maven']})")
        
        if ecosystems_info:
            html += f'''
            <p><strong>Ecosystems Tested:</strong> {', '.join(ecosystems_info)}</p>'''
    
    html += '''
            <p><strong>Traffic Mix:</strong> 40% metadata requests, 60% package downloads</p>
            <p><strong>RPS Levels:</strong> ''' + ', '.join(rps_list) + ''' requests/second</p>
            <p><strong>Duration per Level:</strong> ''' + test_type + '''</p>
        </div>
        
        <div class="overview">
            <h2>Test Configuration</h2>
'''
    
    # Add configuration details from first test
    if all_test_data and len(all_test_data) > 0:
        first_test = all_test_data[0]
        test_id = first_test.get('test_id', 'N/A')
        num_gens = first_test.get('num_generators', 1)
        
        html += f'''
            <p><strong>Test ID:</strong> {test_id}</p>
            <p><strong>Load Generators:</strong> {num_gens}</p>
            <p><strong>Test Date:</strong> {timestamp}</p>
'''
    
    html += '''
            <p><strong>Registry URLs:</strong></p>
            <ul style="margin-left: 20px;">'''
    
    # Add registry URLs if provided
    if registry_urls:
        if 'npm' in registry_urls:
            html += f'''
                <li>npm: {registry_urls['npm']}</li>'''
        if 'pypi' in registry_urls:
            html += f'''
                <li>PyPI: {registry_urls['pypi']}</li>'''
        if 'maven' in registry_urls:
            html += f'''
                <li>Maven: {registry_urls['maven']}</li>'''
    
    html += '''
            </ul>
            <p><strong>Traffic Distribution:</strong></p>
            <ul style="margin-left: 20px;">
                <li>Metadata requests: 40%</li>
                <li>Download requests: 60%</li>
            </ul>
            <p><strong>Package Selection:</strong></p>
            <ul style="margin-left: 20px;">
                <li>Top 20% packages (most popular): Selected for 30% of requests</li>
                <li>Remaining 80% packages: Selected for 70% of requests</li>
                <li>All packages use real versions from registries</li>
            </ul>
        </div>
'''
    
    # Summary metrics
    total_requests = sum(d['k6_stats'].get('total_requests', 0) for d in all_test_data)
    total_errors = sum(d['k6_stats'].get('total_errors', 0) for d in all_test_data)
    avg_error_rate = statistics.mean([d['k6_stats'].get('error_rate', 0) * 100 for d in all_test_data])
    max_rps = max(d['rps'] for d in all_test_data)
    total_bandwidth = sum(d['k6_stats'].get('total_bytes', 0) for d in all_test_data)
    metadata_bandwidth = sum(d['k6_stats'].get('metadata_bytes', 0) for d in all_test_data)
    download_bandwidth = sum(d['k6_stats'].get('download_bytes', 0) for d in all_test_data)
    
    html += f'''
        <div class="summary-grid">
            <div class="metric-card">
                <h3>Total Requests</h3>
                <div class="value">{total_requests:,}</div>
            </div>
            <div class="metric-card">
                <h3>Max RPS Tested</h3>
                <div class="value">{max_rps:,}</div>
            </div>
            <div class="metric-card">
                <h3>Total Errors</h3>
                <div class="value">{total_errors:,}</div>
            </div>
            <div class="metric-card">
                <h3>Avg Error Rate</h3>
                <div class="value">{avg_error_rate:.2f}<span class="unit">%</span></div>
            </div>
            <div class="metric-card">
                <h3>Total Bandwidth</h3>
                <div class="value">{format_bytes(total_bandwidth)}</div>
            </div>
            <div class="metric-card">
                <h3>Metadata Traffic</h3>
                <div class="value">{format_bytes(metadata_bandwidth)}</div>
            </div>
            <div class="metric-card">
                <h3>Download Traffic</h3>
                <div class="value">{format_bytes(download_bandwidth)}</div>
            </div>
        </div>
'''
    
    # Per-RPS sections
    for test_data in all_test_data:
        html += generate_rps_section(test_data, duration_seconds)
    
    # Footer
    html += '''
        <div class="footer">
            <p>Socket Registry Firewall Load Test Report</p>
            <p>Distributed load testing with system resource monitoring</p>
        </div>
    </div>
</body>
</html>
'''
    
    return html


def generate_rps_section(test_data, duration_seconds=300):
    """Generate HTML for a single RPS test section"""
    
    rps = test_data['rps']
    k6 = test_data['k6_stats']
    sys = test_data['system_stats']
    test_id = test_data['test_id']
    num_gens = test_data['num_generators']
    
    # Determine status colors
    error_rate = k6.get('error_rate', 0) * 100
    error_class = 'good' if error_rate < 1 else ('warning' if error_rate < 5 else 'bad')
    
    timeout_rate = k6.get('timeout_rate', 0)
    timeout_class = 'good' if timeout_rate < 1 else ('warning' if timeout_rate < 10 else 'bad')
    
    # Use metadata_request_duration for API performance if available (fallback to http_req_duration)
    metadata_duration = k6.get('metadata_request_duration', k6.get('http_req_duration', {}))
    p75_latency = metadata_duration.get('p75', 0)
    p75_class = 'good' if p75_latency < 500 else ('warning' if p75_latency < 1000 else 'bad')
    
    # P95/P99 status - check if hitting timeout threshold
    # Note: setup uses 30s, metadata uses 60s, downloads use 120s
    p95_latency = metadata_duration.get('p95', 0)
    p99_latency = metadata_duration.get('p99', 0)
    timeout_threshold_ms = 59900  # 59.9s in milliseconds for 60s metadata timeout
    
    # P95 status
    if p95_latency >= timeout_threshold_ms:
        p95_class = 'bad'
        p95_status = '✗ Timeout'
        p95_is_timeout = True
    elif p95_latency >= 20000:  # 20s+
        p95_class = 'bad'
        p95_status = '✗ Poor'
        p95_is_timeout = False
    elif p95_latency >= 15000:  # 15-20s
        p95_class = 'warning'
        p95_status = '⚠ Warning'
        p95_is_timeout = False
    else:
        p95_class = 'good'
        p95_status = '✓ Good'
        p95_is_timeout = False
    
    # P99 status
    if p99_latency >= timeout_threshold_ms:
        p99_class = 'bad'
        p99_status = '✗ Timeout'
        p99_is_timeout = True
    elif p99_latency >= 20000:  # 20s+
        p99_class = 'bad'
        p99_status = '✗ Poor'
        p99_is_timeout = False
    elif p99_latency >= 15000:  # 15-20s
        p99_class = 'warning'
        p99_status = '⚠ Warning'
        p99_is_timeout = False
    else:
        p99_class = 'good'
        p99_status = '✓ Good'
        p99_is_timeout = False
    
    # Get timeout percentage if available
    timeout_pct = metadata_duration.get('timeout_percentage', 0)
    
    # Calculate achieved RPS from actual duration
    total_requests = k6.get('total_requests', 0)
    achieved_rps = total_requests // duration_seconds if duration_seconds > 0 else 0
    
    html = f'''
        <div class="rps-section">
            <h2>{rps:,} Requests Per Second</h2>
            <div class="info-box">
                <p><strong>Test ID:</strong> {test_id}</p>
                <p><strong>Load Generators:</strong> {num_gens}</p>
                <p><strong>Total Requests:</strong> {total_requests:,}</p>
                <p><strong>Target RPS:</strong> {rps:,} req/s</p>
                <p><strong>Achieved RPS:</strong> ~{achieved_rps:,} req/s (approx, based on {duration_seconds}s test)</p>
            </div>
            
            <h3>Performance Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Server Error Rate</td>
                        <td class="{error_class}">{error_rate:.2f}%</td>
                        <td class="{error_class}">{'✓ Good' if error_rate < 1 else ('⚠ Warning' if error_rate < 5 else '✗ Poor')}</td>
                    </tr>
                    <tr>
                        <td>Timeout Rate</td>
                        <td class="{timeout_class}">{timeout_rate:.2f}%</td>
                        <td class="{timeout_class}">{'✓ Good' if timeout_rate < 1 else ('⚠ Warning' if timeout_rate < 10 else '✗ Poor')}</td>
                    </tr>
                    <tr>
                        <td>Total Bandwidth</td>
                        <td>{format_bytes(k6.get('total_bytes', 0))}</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
            
            <h3>Metadata API Performance</h3>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <em>Metadata requests include package info, search, and JSON API calls (excludes tarball/wheel/JAR downloads)</em>
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Avg Response Time</td>
                        <td>{format_duration(metadata_duration.get('avg', 0))}</td>
                        <td class="good">✓ Good</td>
                    </tr>
                    <tr>
                        <td>P50 Response Time</td>
                        <td>{format_duration(metadata_duration.get('p50', 0))}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>P75 Response Time</td>
                        <td class="{p75_class}">{format_duration(p75_latency)}</td>
                        <td class="{p75_class}">{'✓ Good' if p75_latency < 500 else ('⚠ Warning' if p75_latency < 1000 else '✗ Poor')}</td>
                    </tr>
                    <tr>
                        <td>P95 Response Time</td>
                        <td class="{p95_class}">{format_duration(p95_latency)}</td>
                        <td class="{p95_class}">{p95_status}</td>
                    </tr>'''
    
    # Only show P99 if P95 is not at timeout threshold
    if not p95_is_timeout:
        html += f'''
                    <tr>
                        <td>P99 Response Time</td>
                        <td class="{p99_class}">{format_duration(p99_latency)}</td>
                        <td class="{p99_class}">{p99_status}</td>
                    </tr>'''
    
    html += f'''
                    <tr>
                        <td>Metadata Traffic</td>
                        <td>{format_bytes(k6.get('metadata_bytes', 0))}</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>'''
    
    # Add timeout warning if applicable
    if timeout_pct > 0:
        html += f'''
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0;">
                <strong>⚠ Timeout Warning:</strong> {timeout_pct:.1f}% of metadata requests are timing out at 60 seconds. 
                This indicates severe performance issues that need immediate investigation.
            </div>'''
    
    html += '''
'''
    
    # Download performance section (only if downloads occurred)
    download_duration = k6.get('download_request_duration', {})
    if download_duration:
        download_speed = k6.get('download_speed', {})
        download_buckets = k6.get('download_size_buckets', {})
        
        html += f'''
            <h3>Download Performance</h3>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <em>Download requests include tarballs, wheels, and JAR files</em>
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Avg Download Time</td>
                        <td>{format_duration(download_duration.get('avg', 0))}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>P50 Download Time</td>
                        <td>{format_duration(download_duration.get('p50', 0))}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>P75 Download Time</td>
                        <td>{format_duration(download_duration.get('p75', 0))}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>P99 Download Time</td>
                        <td>{format_duration(download_duration.get('p99', 0))}</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>Download Traffic</td>
                        <td>{format_bytes(k6.get('download_bytes', 0))}</td>
                        <td>-</td>
                    </tr>'''
        
        if download_speed:
            html += f'''
                    <tr>
                        <td>Avg Download Speed</td>
                        <td>{format_bytes(download_speed.get('avg', 0))}/s</td>
                        <td>-</td>
                    </tr>
                    <tr>
                        <td>P75 Download Speed</td>
                        <td>{format_bytes(download_speed.get('p75', 0))}/s</td>
                        <td>-</td>
                    </tr>'''
        
        html += '''
                </tbody>
            </table>
'''
        
        # Add size bucket breakdown if available
        if download_buckets:
            html += '''
            <h4>Download Performance by File Size</h4>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <em>Performance metrics grouped by download size ranges</em>
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Size Range</th>
                        <th>Count</th>
                        <th>Avg Size</th>
                        <th>Avg Time</th>
                        <th>P95 Time</th>
                        <th>Avg Speed</th>
                    </tr>
                </thead>
                <tbody>
'''
            # Display buckets in order: <100KB, 100KB-1MB, 1-10MB, >10MB
            bucket_order = ['<100KB', '100KB-1MB', '1-10MB', '>10MB']
            for bucket_name in bucket_order:
                if bucket_name in download_buckets:
                    bucket = download_buckets[bucket_name]
                    html += f'''
                    <tr>
                        <td><strong>{bucket_name}</strong></td>
                        <td>{bucket['count']:,}</td>
                        <td>{format_bytes(bucket['avg_size'])}</td>
                        <td>{format_duration(bucket['avg_duration'])}</td>
                        <td>{format_duration(bucket['p95_duration'])}</td>
                        <td>{format_bytes(bucket['avg_speed'])}/s</td>
                    </tr>'''
            
            html += '''
                </tbody>
            </table>
'''
    
    # HTTP Status Code breakdown - NEW categorized metrics
    # Show the new categorized counters if available
    status_2xx = k6.get('status_2xx_count', 0)
    status_404 = k6.get('status_404_count', 0)
    status_403 = k6.get('status_403_count', 0)
    status_4xx = k6.get('status_4xx_count', 0)
    status_5xx = k6.get('status_5xx_count', 0)
    status_timeout = k6.get('status_timeout_count', 0)
    
    if status_2xx + status_404 + status_403 + status_4xx + status_5xx + status_timeout > 0:
        total_status_counts = status_2xx + status_404 + status_403 + status_4xx + status_5xx + status_timeout
        html += '''
            <h3>HTTP Status Code Summary</h3>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <strong>Note:</strong> 404 (Not Found) and 403 (Forbidden) are expected responses and are <strong>not counted as errors</strong>.<br>
                Only 5xx (Server Errors) and other 4xx errors are counted in the Server Error Rate above.<br>
                Timeouts (status 0) indicate the request exceeded k6's timeout limit.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Count</th>
                        <th>Percentage</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
'''
        if status_2xx > 0:
            pct = (status_2xx / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="good">2xx Success</td>
                        <td>{status_2xx:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="good">✓ Success</td>
                    </tr>
'''
        if status_404 > 0:
            pct = (status_404 / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="good">404 Not Found</td>
                        <td>{status_404:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="good">✓ Expected</td>
                    </tr>
'''
        if status_403 > 0:
            pct = (status_403 / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="good">403 Forbidden</td>
                        <td>{status_403:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="good">✓ Expected</td>
                    </tr>
'''
        if status_4xx > 0:
            pct = (status_4xx / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="bad">4xx Other Client Errors</td>
                        <td>{status_4xx:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="bad">✗ Error</td>
                    </tr>
'''
        if status_5xx > 0:
            pct = (status_5xx / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="bad">5xx Server Errors</td>
                        <td>{status_5xx:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="bad">✗ Error</td>
                    </tr>
'''
        if status_timeout > 0:
            pct = (status_timeout / total_status_counts * 100)
            html += f'''
                    <tr>
                        <td class="warning">Timeouts (status 0)</td>
                        <td>{status_timeout:,}</td>
                        <td>{pct:.1f}%</td>
                        <td class="warning">⚠ Timeout</td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
'''
    
    # HTTP Status Code breakdown - old detailed view (fallback for older test results)
    status_codes = k6.get('status_codes', {})
    if status_codes:
        html += '''
            <h3>HTTP Status Codes (Detailed)</h3>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <strong>Note:</strong> Status code 0 indicates client-side timeout (request exceeded k6's timeout limit).
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Status Code</th>
                        <th>Count</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
'''
        total = sum(status_codes.values())
        for status in sorted(status_codes.keys()):
            count = status_codes[status]
            pct = (count / total * 100) if total > 0 else 0
            # Display friendly label for status 0 (timeouts)
            status_label = '0 (Timeout)' if status == '0' else status
            # 200 is good, 3xx redirects are warning, 403/404 are expected (good), other errors are bad
            if status in ['200', '201', '204']:
                status_class = 'good'
            elif status in ['403', '404']:
                status_class = 'good'  # Expected responses from firewall
            elif status.startswith('3'):
                status_class = 'warning'
            else:
                status_class = 'bad'
            html += f'''
                    <tr>
                        <td class="{status_class}">{status_label}</td>
                        <td>{count:,}</td>
                        <td>{pct:.1f}%</td>
                    </tr>
'''
        html += '''
                </tbody>
            </table>
'''
    
    # System metrics table
    if sys:
        html += f'''
            <h3>System Resource Utilization</h3>
            <table>
                <thead>
                    <tr>
                        <th>Resource</th>
                        <th>Average</th>
                        <th>Peak (Max)</th>
                        <th>P95</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>CPU Usage</td>
                        <td>{sys.get('cpu_avg', 0):.1f}%</td>
                        <td>{sys.get('cpu_max', 0):.1f}%</td>
                        <td>{sys.get('cpu_p95', 0):.1f}%</td>
                    </tr>
                    <tr>
                        <td>Memory Usage</td>
                        <td>{sys.get('mem_avg', 0):.1f}%</td>
                        <td>{sys.get('mem_max', 0):.1f}%</td>
                        <td>{sys.get('mem_p95', 0):.1f}%</td>
                    </tr>
                    <tr>
                        <td>Load Average (1m)</td>
                        <td>{sys.get('load_avg_mean', 0):.2f}</td>
                        <td>{sys.get('load_avg_max', 0):.2f}</td>
                        <td>-</td>
                    </tr>
                </tbody>
            </table>
'''
    
    # Ecosystem breakdown
    npm_reqs = k6.get('npm_requests', 0)
    pypi_reqs = k6.get('pypi_requests', 0)
    maven_reqs = k6.get('maven_requests', 0)
    total_reqs = k6.get('total_requests', 1)
    
    html += f'''
            <h3>Request Distribution by Ecosystem</h3>
            <table>
                <thead>
                    <tr>
                        <th>Ecosystem</th>
                        <th>Requests</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>npm</td>
                        <td>{npm_reqs:,}</td>
                        <td>{npm_reqs / total_reqs * 100:.1f}%</td>
                    </tr>
                    <tr>
                        <td>PyPI</td>
                        <td>{pypi_reqs:,}</td>
                        <td>{pypi_reqs / total_reqs * 100:.1f}%</td>
                    </tr>
                    <tr>
                        <td>Maven</td>
                        <td>{maven_reqs:,}</td>
                        <td>{maven_reqs / total_reqs * 100:.1f}%</td>
                    </tr>
                </tbody>
            </table>
'''
    
    # Response time details
    metadata_duration = k6.get('metadata_request_duration', k6.get('http_req_duration', {}))
    download_duration = k6.get('download_request_duration', {})
    
    html += f'''
            <h3>Response Time Details</h3>
            <p style="font-size: 0.9em; color: #666; margin-bottom: 10px;">
                <em>Percentile values show the maximum time for the specified percentage of requests:</em><br>
                <em>• P10 = 10% of requests completed in ≤ this time</em><br>
                <em>• P50 (Median) = 50% of requests completed in ≤ this time</em><br>
                <em>• P75 = 75% of requests completed in ≤ this time</em><br>
                <em>• P95 = 95% of requests completed in ≤ this time</em><br>
                <em>• P99 = 99% of requests completed in ≤ this time</em>
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Request Type</th>
                        <th>Min</th>
                        <th>P10</th>
                        <th>P50 (Median)</th>
                        <th>Avg</th>
                        <th>P75</th>
                        <th>P95</th>
                        <th>P99</th>
                        <th>Max</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Metadata (API)</strong></td>
                        <td>{format_duration(metadata_duration.get('min', 0))}</td>
                        <td>{format_duration(metadata_duration.get('p10', 0))}</td>
                        <td>{format_duration(metadata_duration.get('p50', metadata_duration.get('median', 0)))}</td>
                        <td>{format_duration(metadata_duration.get('avg', 0))}</td>
                        <td>{format_duration(metadata_duration.get('p75', 0))}</td>
                        <td>{format_duration(metadata_duration.get('p95', 0))}</td>
                        <td>{format_duration(metadata_duration.get('p99', 0))}</td>
                        <td>{format_duration(metadata_duration.get('max', 0))}</td>
                    </tr>'''
    
    if download_duration:
        html += f'''
                    <tr>
                        <td><strong>Downloads</strong></td>
                        <td>{format_duration(download_duration.get('min', 0))}</td>
                        <td>{format_duration(download_duration.get('p10', 0))}</td>
                        <td>{format_duration(download_duration.get('p50', download_duration.get('median', 0)))}</td>
                        <td>{format_duration(download_duration.get('avg', 0))}</td>
                        <td>{format_duration(download_duration.get('p75', 0))}</td>
                        <td>{format_duration(download_duration.get('p95', 0))}</td>
                        <td>{format_duration(download_duration.get('p99', 0))}</td>
                        <td>{format_duration(download_duration.get('max', 0))}</td>
                    </tr>'''
    
    html += '''
                </tbody>
            </table>
'''
    
    # Charts
    html += '''
            <h3>Performance Graphs</h3>
            <div class="charts-grid">
'''
    
    # Response time chart data
    chart_id_base = f"chart_{rps}"
    
    html += f'''
                <div class="chart-container">
                    <h3>Response Time Distribution</h3>
                    <canvas id="{chart_id_base}_latency"></canvas>
                </div>
'''
    
    # System metrics charts
    if sys and sys.get('cpu_usage'):
        html += f'''
                <div class="chart-container">
                    <h3>CPU Usage Over Time</h3>
                    <canvas id="{chart_id_base}_cpu"></canvas>
                </div>
                <div class="chart-container">
                    <h3>Memory Usage Over Time</h3>
                    <canvas id="{chart_id_base}_memory"></canvas>
                </div>
'''
    
    html += '''
            </div>
        </div>
'''
    
    # Add Chart.js scripts
    html += f'''
    <script>
        // Response time distribution (using metadata_duration for API performance)
        new Chart(document.getElementById('{chart_id_base}_latency'), {{
            type: 'bar',
            data: {{
                labels: ['Min', 'Avg', 'Median', 'P95', 'P99', 'Max'],
                datasets: [{{
                    label: 'Metadata Response Time (ms)',
                    data: [{metadata_duration.get('min', 0):.2f}, {metadata_duration.get('avg', 0):.2f}, {metadata_duration.get('median', 0):.2f}, {metadata_duration.get('p95', 0):.2f}, {metadata_duration.get('p99', 0):.2f}, {metadata_duration.get('max', 0):.2f}],
                    backgroundColor: ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6', '#34495e']
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{ display: true, text: 'Milliseconds' }}
                    }}
                }}
            }}
        }});
'''
    
    # System metrics charts
    if sys and sys.get('cpu_usage'):
        cpu_data = sys['cpu_usage']
        mem_data = sys['memory_usage']
        timestamps = sys['timestamps']
        
        # Convert timestamps to relative seconds
        if timestamps:
            start_time = timestamps[0]
            relative_times = [(t - start_time) for t in timestamps[:len(cpu_data)]]
            time_labels = [f"{t//60}:{t%60:02d}" for t in relative_times]
        else:
            time_labels = list(range(len(cpu_data)))
        
        html += f'''
        // CPU usage
        new Chart(document.getElementById('{chart_id_base}_cpu'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(time_labels)},
                datasets: [{{
                    label: 'CPU Usage %',
                    data: {json.dumps(cpu_data)},
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{ display: true, text: 'CPU %' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Time (mm:ss)' }}
                    }}
                }}
            }}
        }});
        
        // Memory usage
        new Chart(document.getElementById('{chart_id_base}_memory'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(time_labels)},
                datasets: [{{
                    label: 'Memory Usage %',
                    data: {json.dumps(mem_data)},
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{ display: true, text: 'Memory %' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Time (mm:ss)' }}
                    }}
                }}
            }}
        }});
'''
    
    html += '''
    </script>
'''
    
    return html


# Public API functions
__all__ = [
    'parse_k6_json',
    'parse_system_metrics',
    'analyze_k6_metrics',
    'analyze_system_metrics',
    'aggregate_test_results',
    'generate_html_report',
    'format_bytes',
    'format_duration',
    'calculate_percentile',
]
