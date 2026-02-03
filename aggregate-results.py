#!/usr/bin/env python3
"""
Aggregate results from multiple load generators for a single test
"""

import sys
import json
import glob
from pathlib import Path
from collections import defaultdict

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 aggregate-results.py <test-id> [results-dir]")
        print("")
        print("Example:")
        print("  python3 aggregate-results.py test-20260109-163426")
        print("  python3 aggregate-results.py test-20260109-163426 ./load-test-results")
        sys.exit(1)
    
    test_id = sys.argv[1]
    results_dir = sys.argv[2] if len(sys.argv) > 2 else './load-test-results'
    
    print(f"Aggregating results for test: {test_id}")
    print(f"Results directory: {results_dir}")
    print("")
    
    # Find all result files for this test
    pattern = f"{results_dir}/{test_id}_*_k6_results.json"
    result_files = glob.glob(pattern)
    
    if not result_files:
        print(f"No result files found matching: {pattern}")
        sys.exit(1)
    
    print(f"Found {len(result_files)} result file(s):")
    for f in result_files:
        print(f"  - {Path(f).name}")
    
    print("")
    print("Results are already aggregated by the report generator.")
    print("To generate a report, create a config file:")
    print("")
    print("  cat > config.json <<EOF")
    print("  [")
    print(f'    {{"test_id": "{test_id}", "rps": 500}}')
    print("  ]")
    print("  EOF")
    print("")
    print("Then run:")
    print(f"  python3 generate-comprehensive-report.py config.json {results_dir}")
    print("")

if __name__ == '__main__':
    main()
