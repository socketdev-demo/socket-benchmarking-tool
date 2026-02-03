#!/usr/bin/env python3
"""
Simple wrapper to generate report from test ID
"""

import sys
import json
import os
import subprocess
import re
import tempfile

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate-report-simple.py <test-id> [rps]")
        print("")
        print("Examples:")
        print("  python3 generate-report-simple.py test-20260109-173015")
        print("  python3 generate-report-simple.py test-20260109-173015 500")
        print("")
        print("The script will:")
        print("  1. Create a temporary config file")
        print("  2. Generate the HTML report")
        print("  3. Clean up the config file")
        sys.exit(1)
    
    test_id = sys.argv[1]
    
    results_dir = './load-test-results'
    
    # Try to extract RPS from actual test results
    rps = None
    duration_seconds = None
    
    if len(sys.argv) > 2:
        rps = int(sys.argv[2])
    else:
        # Try to read actual RPS from k6 summary file
        import glob
        summary_files = glob.glob(f"{results_dir}/{test_id}_*_k6_summary.txt")
        if summary_files:
            try:
                with open(summary_files[0], 'r') as f:
                    summary_data = json.load(f)
                    # Get actual RPS from metrics
                    if 'metrics' in summary_data and 'total_requests' in summary_data['metrics']:
                        actual_rps = summary_data['metrics']['total_requests'].get('rate', 0)
                        rps = int(round(actual_rps))
                        print(f"Detected actual RPS from test results: {rps}")
                    
                    # Get duration from iterations metric
                    if 'metrics' in summary_data and 'iterations' in summary_data['metrics']:
                        duration_seconds = int(summary_data['metrics']['iterations'].get('count', 0) / actual_rps) if rps else None
            except Exception as e:
                print(f"Warning: Could not read RPS from summary file: {e}")
        
        if not rps:
            # Try to guess from filename or default to 500
            match = re.search(r'(\d+)rps', test_id.lower())
            if match:
                rps = int(match.group(1))
            else:
                print("Could not determine RPS from test results. Defaulting to 500.")
                print("Specify RPS manually: ./generate-report-simple.py test-id 1000")
                rps = 500
    
    print(f"Generating report for test: {test_id}")
    print(f"RPS: {rps}")
    print(f"Results directory: {results_dir}")
    print("")
    
    # Check if test results exist
    import glob
    pattern = f"{results_dir}/{test_id}_*_k6_results.json"
    result_files = glob.glob(pattern)
    
    if not result_files:
        print(f"ERROR: No result files found matching: {pattern}")
        print("")
        print("Available test IDs:")
        all_results = glob.glob(f"{results_dir}/*_k6_results.json")
        test_ids = set()
        for f in all_results:
            basename = os.path.basename(f)
            # Extract test ID (everything before first underscore after 'test-')
            parts = basename.split('_')
            if len(parts) >= 2:
                test_ids.add(parts[0])
        
        for tid in sorted(test_ids):
            print(f"  {tid}")
        sys.exit(1)
    
    print(f"Found {len(result_files)} result file(s)")
    # using cross-platform temp directory
    temp_dir = tempfile.gettempdir()
    config_file = os.path.join(temp_dir, f'report-config-{test_id}.json')
    config = [
        {"test_id": test_id, "rps": rps}
    ]
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created config: {config_file}")
    print("")
    
    # Run report generator
    try:
        python_cmd = 'python' if sys.platform == 'win32' else 'python3'
        script_dir = os.path.dirname(os.path.abspath(__file__))
        report_script = os.path.join(script_dir, 'generate-comprehensive-report.py')
        subprocess.run([
            python_cmd, 
            report_script, 
            config_file, 
            results_dir
        ], check=True)
        
        print("")
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        
        # Determine duration for filename
        duration_label = "5-minute"  # default
        if duration_seconds:
            if duration_seconds < 90:
                duration_label = f"{duration_seconds}-second"
            else:
                duration_minutes = int(round(duration_seconds / 60))
                duration_label = f"{duration_minutes}-minute"
        
        report_filename = f"load-test-report-{duration_label}.html"
        print(f"Report generated: {report_filename}")
        print(f"Test: {test_id} | RPS: {rps} | Duration: ~{duration_label.replace('-', ' ')}")
        print("")
        print("Open it in your browser:")
        print(f"  firefox {report_filename}")
        print("  # or")
        print("  python3 -m http.server 8000")
        print(f"  # then visit http://localhost:8000/{report_filename}")
        print("")
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Report generation failed: {e}")
        sys.exit(1)
    finally:
        # Clean up config file
        if os.path.exists(config_file):
            os.remove(config_file)

if __name__ == '__main__':
    main()
