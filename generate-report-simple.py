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
    
    # Try to extract RPS from test_id if not provided
    rps = None
    if len(sys.argv) > 2:
        rps = int(sys.argv[2])
    else:
        # Try to guess from filename or default to 500
        match = re.search(r'(\d+)rps', test_id.lower())
        if match:
            rps = int(match.group(1))
        else:
            print("Could not determine RPS from test ID. Defaulting to 500.")
            print("Specify RPS manually: ./generate-report-simple.py test-id 1000")
            rps = 500
    
    results_dir = './load-test-results'
    
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
        print("Report generated: load-test-report-5-minute.html")
        print("")
        print("Open it in your browser:")
        print("  firefox load-test-report-5-minute.html")
        print("  # or")
        print("  python3 -m http.server 8000")
        print("  # then visit http://localhost:8000/load-test-report-5-minute.html")
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
