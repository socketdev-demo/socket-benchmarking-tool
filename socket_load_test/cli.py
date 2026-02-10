"""Command-line interface for socket-load-test."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .config import TestConfig, RegistriesConfig, TrafficConfig
from .core.load.k6_wrapper import K6Manager
from .core.metadata_fetcher import MetadataFetcher


def test_command(args):
    """Run a load test."""
    
    # Parse and validate ecosystems
    selected_ecosystems = [e.strip().lower() for e in args.ecosystems.split(',')]
    valid_ecosystems = ['npm', 'pypi', 'maven']
    
    for ecosystem in selected_ecosystems:
        if ecosystem not in valid_ecosystems:
            print(f"Error: Invalid ecosystem '{ecosystem}'. Must be one of: {', '.join(valid_ecosystems)}", file=sys.stderr)
            sys.exit(1)
    
    if not selected_ecosystems:
        print("Error: At least one ecosystem must be specified", file=sys.stderr)
        sys.exit(1)
    
    # Handle base-url + path combinations
    base_url = args.base_url
    npm_url = args.npm_url
    pypi_url = args.pypi_url
    maven_url = args.maven_url
    npm_path = args.npm_path
    pypi_path = args.pypi_path
    maven_path = args.maven_path
    
    if base_url and not base_url.startswith(('http://', 'https://')):
        base_url = f"https://{base_url}"
    
    if base_url:
        base_url = base_url.rstrip('/')
        # Only build URLs from base_url + path if full URL not provided
        if 'npm' in selected_ecosystems and not npm_url and npm_path:
            npm_url = f"{base_url}{npm_path if npm_path.startswith('/') else '/' + npm_path}"
        if 'pypi' in selected_ecosystems and not pypi_url and pypi_path:
            pypi_url = f"{base_url}{pypi_path if pypi_path.startswith('/') else '/' + pypi_path}"
        if 'maven' in selected_ecosystems and not maven_url and maven_path:
            maven_url = f"{base_url}{maven_path if maven_path.startswith('/') else '/' + maven_path}"
    
    # Validate required URLs for selected ecosystems only
    missing_urls = []
    if 'npm' in selected_ecosystems and not npm_url:
        missing_urls.append('npm')
    if 'pypi' in selected_ecosystems and not pypi_url:
        missing_urls.append('pypi')
    if 'maven' in selected_ecosystems and not maven_url:
        missing_urls.append('maven')
    
    if missing_urls:
        print(f"Error: Missing URLs for selected ecosystems: {', '.join(missing_urls)}", file=sys.stderr)
        print("Must provide either:", file=sys.stderr)
        for eco in missing_urls:
            print(f"  - --{eco}-url, OR", file=sys.stderr)
        print(f"  - --base-url with appropriate paths (--{'-path, --'.join(missing_urls)}-path)", file=sys.stderr)
        sys.exit(1)
    
    # Load custom packages if provided
    custom_packages = None
    packages = args.packages
    if packages:
        try:
            with open(packages, 'r', encoding='utf-8') as f:
                custom_packages = json.load(f)
            print(f"Loaded custom packages from: {packages}")
            if args.verbose:
                for eco in selected_ecosystems:
                    if eco in custom_packages:
                        print(f"  {eco}: {len(custom_packages[eco])} packages")
        except Exception as e:
            print(f"Error loading packages file: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Generate test ID if not provided
    test_id = args.test_id
    if not test_id:
        test_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Display configuration
    if args.no_docker:
        print("Running k6 locally (no Docker)")
    else:
        print("Running k6 with Docker)")
    
    print(f"\nTest Configuration:")
    print(f"  Test ID:      {test_id}")
    print(f"  Duration:     {args.duration}")
    print(f"  Target RPS:   {args.rps}")
    print(f"  Ecosystems:   {', '.join(selected_ecosystems)}")
    if 'npm' in selected_ecosystems:
        print(f"  NPM URL:      {npm_url}")
    if 'pypi' in selected_ecosystems:
        print(f"  PyPI URL:     {pypi_url}")
    if 'maven' in selected_ecosystems:
        print(f"  Maven URL:    {maven_url}")
    print(f"  Output Dir:   {args.output_dir}")
    print(f"  Load Gen ID:  {args.load_gen_id}")
    print(f"  Repeat Mode:  {args.repeat}")
    
    # Display package information if verbose
    if args.verbose:
        print(f"\nPackage Configuration:")
        if custom_packages:
            print(f"  Source:       Custom packages file ({packages})")
        else:
            print(f"  Source:       Default package seeds")
        
        # Get package seeds (custom or default)
        package_seeds = custom_packages or K6Manager.DEFAULT_PACKAGE_SEEDS
        
        for eco in selected_ecosystems:
            if eco in package_seeds:
                pkg_list = package_seeds[eco]
                print(f"\n  {eco.upper()} Packages ({len(pkg_list)} total):")
                # Show first 10 packages and indicate if there are more
                for i, pkg in enumerate(pkg_list[:10]):
                    print(f"    - {pkg}")
                if len(pkg_list) > 10:
                    print(f"    ... and {len(pkg_list) - 10} more")
    
    print()
    
    # Initialize metadata fetcher
    metadata_fetcher = MetadataFetcher(output_dir=args.metadata_cache_dir)
    pre_fetched_metadata = {}
    
    # Get package seeds (custom or default)
    package_seeds = custom_packages or K6Manager.DEFAULT_PACKAGE_SEEDS
    
    # Prepare authentication config for metadata fetcher
    auth_config = {
        'npm_token': args.npm_token,
        'npm_username': args.npm_username,
        'npm_password': args.npm_password,
        'pypi_token': args.pypi_token,
        'pypi_username': args.pypi_username,
        'pypi_password': args.pypi_password,
        'maven_username': args.maven_username,
        'maven_password': args.maven_password,
    }
    
    # Prepare registry URLs
    registry_urls = {}
    if 'npm' in selected_ecosystems:
        registry_urls['npm'] = npm_url
    if 'pypi' in selected_ecosystems:
        registry_urls['pypi'] = pypi_url
    if 'maven' in selected_ecosystems:
        registry_urls['maven'] = maven_url
    
    # Handle --repeat mode or fetch fresh metadata
    if args.repeat:
        print("\n" + "=" * 60)
        print("REPEAT MODE: Loading cached metadata")
        print("=" * 60)
        
        # Try to load cached metadata for each ecosystem
        all_cached = True
        for ecosystem in selected_ecosystems:
            cached = metadata_fetcher.load_metadata(ecosystem)
            if cached and 'metadata' in cached:
                pre_fetched_metadata[ecosystem] = cached['metadata']
                print(f"  ✓ Loaded {ecosystem} metadata from cache ({len(cached['metadata'])} packages)")
            else:
                all_cached = False
                print(f"  ✗ No cache found for {ecosystem}")
        
        if not all_cached:
            print("\n  Warning: Some metadata caches not found. Fetching fresh metadata...")
            # Fetch missing metadata
            missing_ecosystems = [eco for eco in selected_ecosystems if eco not in pre_fetched_metadata]
            if missing_ecosystems:
                fetched = metadata_fetcher.fetch_and_cache_all(
                    ecosystems=missing_ecosystems,
                    packages={eco: package_seeds.get(eco, []) for eco in missing_ecosystems},
                    registry_urls=registry_urls,
                    auth_config=auth_config,
                    verbose=args.verbose
                )
                pre_fetched_metadata.update(fetched)
        
        print("=" * 60)
    else:
        # Always fetch fresh metadata (not in repeat mode)
        print("\nFetching fresh metadata from registries...")
        print("(This may take 5-10 minutes for 260+ packages)")
        
        pre_fetched_metadata = metadata_fetcher.fetch_and_cache_all(
            ecosystems=selected_ecosystems,
            packages={eco: package_seeds.get(eco, []) for eco in selected_ecosystems},
            registry_urls=registry_urls,
            auth_config=auth_config,
            verbose=args.verbose
        )
    
    try:
        # Create configuration objects
        test_config = TestConfig(
            rps=args.rps,
            duration=args.duration,
            test_id=test_id,
            no_docker=args.no_docker
        )
        
        registries_config = RegistriesConfig(
            npm_url=npm_url,
            pypi_url=pypi_url,
            maven_url=maven_url,
            ecosystems=selected_ecosystems,
            # NPM authentication
            npm_token=args.npm_token,
            npm_username=args.npm_username,
            npm_password=args.npm_password,
            # PyPI authentication
            pypi_token=args.pypi_token,
            pypi_username=args.pypi_username,
            pypi_password=args.pypi_password,
            # Maven authentication
            maven_username=args.maven_username,
            maven_password=args.maven_password
        )
        
        traffic_config = TrafficConfig(ecosystems=selected_ecosystems)
        
        # Create K6Manager
        k6_manager = K6Manager(
            test_config=test_config,
            registries_config=registries_config,
            traffic_config=traffic_config,
            package_seeds=custom_packages,
            pre_fetched_metadata=pre_fetched_metadata
        )
        
        # Generate k6 script
        print("Generating k6 test script...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            script_path = f.name
            script_content = k6_manager.generate_script()
            f.write(script_content)
        
        print(f"k6 script generated: {script_path}")
        
        # Execute k6 test
        print(f"\nStarting k6 load test...")
        print("=" * 60)
        
        exit_code = k6_manager.execute_k6(
            script_path=script_path,
            output_dir=args.output_dir,
            load_gen_id=args.load_gen_id,
            no_docker=args.no_docker
        )
        
        print("=" * 60)
        
        if exit_code == 0:
            print(f"\n✓ Test completed successfully!")
            print(f"  Results saved to: {args.output_dir}")
            print(f"  Test ID: {test_id}")
            
            # Generate HTML report if requested
            if args.generate_html_report:
                print(f"\nGenerating HTML report...")
                try:
                    from .core.reporting.comprehensive_report import generate_html_report as gen_report
                    import glob
                    import re
                    
                    # Create config for report generation
                    test_configs = [{"test_id": test_id, "rps": args.rps}]
                    
                    # Parse duration from args.duration (e.g., "120s", "5m", "1h")
                    duration_str = args.duration.lower()
                    duration_seconds = None
                    
                    if duration_str.endswith('s'):
                        duration_seconds = int(duration_str[:-1])
                    elif duration_str.endswith('m'):
                        duration_seconds = int(duration_str[:-1]) * 60
                    elif duration_str.endswith('h'):
                        duration_seconds = int(duration_str[:-1]) * 3600
                    else:
                        # Try to parse as plain number (assume seconds)
                        try:
                            duration_seconds = int(duration_str)
                        except:
                            duration_seconds = 300  # Default to 5 minutes
                    
                    # Use custom title if provided, otherwise generate from duration
                    if args.title:
                        test_type = args.title
                    else:
                        # Format test type based on duration
                        if duration_seconds < 90:
                            test_type = f"{duration_seconds}-Second"
                        elif duration_seconds < 3600:
                            minutes = int(round(duration_seconds / 60))
                            test_type = f"{minutes}-Minute"
                        else:
                            hours = int(round(duration_seconds / 3600))
                            test_type = f"{hours}-Hour"
                    
                    # Collect registry URLs from config
                    registry_urls = {}
                    if 'npm' in selected_ecosystems:
                        registry_urls['npm'] = npm_url
                    if 'pypi' in selected_ecosystems:
                        registry_urls['pypi'] = pypi_url
                    if 'maven' in selected_ecosystems:
                        registry_urls['maven'] = maven_url
                    
                    # Ensure output directory exists
                    os.makedirs(args.html_report_path, exist_ok=True)
                    
                    # Generate output file path - append timestamp and sanitize title for filename
                    timestamp = datetime.now().strftime('%Y%m%d_%H-%M-%S')
                    report_name = f"{test_type} - {timestamp}"
                    safe_title = re.sub(r'[^a-zA-Z0-9-]', '-', report_name.lower())
                    output_file = os.path.join(args.html_report_path, f"load-test-report-{safe_title}.html")
                    
                    # Generate the report
                    gen_report(test_configs, args.output_dir, output_file, test_type, duration_seconds, registry_urls)
                    
                    print(f"  ✓ HTML report generated: {output_file}")
                    
                except Exception as e:
                    print(f"  ✗ Failed to generate HTML report: {e}", file=sys.stderr)
                    if args.verbose:
                        import traceback
                        traceback.print_exc()
        else:
            print(f"\n✗ Test failed with exit code: {exit_code}", file=sys.stderr)
            sys.exit(exit_code)
            
        # Clean up temp script
        try:
            os.unlink(script_path)
        except:
            pass
            
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def report_command(args):
    """Generate a report from existing test results."""
    print("Report command - to be implemented")


def setup_command(args):
    """Setup monitoring or SSH keys."""
    print("Setup command - to be implemented")


def validate_command(args):
    """Validate configuration and connectivity."""
    print("Validate command - to be implemented")


def aggregate_command(args):
    """Aggregate results from multiple load generators."""
    print("Aggregate command - to be implemented")


def cli():
    """Socket Load Test - Distributed load testing for Socket Registry Firewall."""
    # Fix Windows encoding issues - ensure UTF-8 for console output
    # This prevents 'charmap' codec errors with Unicode characters like ✓
    import io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Parent parser for common arguments shared across all commands
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parent_parser.add_argument('--log-file', type=str, help='Path to log file')
    parent_parser.add_argument('--config', type=str, help='Path to config file')
    
    parser = argparse.ArgumentParser(
        description='Socket Load Test - Distributed load testing for Socket Registry Firewall',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument('--version', action='version', version='socket-load-test 0.1.0')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Run a load test', parents=[parent_parser])
    test_parser.add_argument('--no-docker', action='store_true', help='Run k6 locally without Docker')
    test_parser.add_argument('--host', type=str, help='Target firewall host')
    test_parser.add_argument('--port', type=int, default=8080, help='Target firewall port')
    test_parser.add_argument('--duration', type=str, default='60s', help='Test duration (e.g., 60s, 5m)')
    test_parser.add_argument('--vus', type=int, help='Number of virtual users')
    test_parser.add_argument('--rps', type=int, required=True, help='Target requests per second')
    test_parser.add_argument('--ecosystems', type=str, required=True, help='Comma-separated list of ecosystems to test (npm,pypi,maven)')
    test_parser.add_argument('--base-url', type=str, help='Base firewall URL (use with --npm-path, --pypi-path, --maven-path)')
    test_parser.add_argument('--npm-path', type=str, help='Path for npm registry (e.g., /npm or /custom/npm)')
    test_parser.add_argument('--pypi-path', type=str, help='Path for pypi registry (e.g., /pypi or /simple)')
    test_parser.add_argument('--maven-path', type=str, help='Path for maven registry (e.g., /maven or /maven2)')
    test_parser.add_argument('--npm-url', type=str, help='Full NPM registry URL (overrides --base-url)')
    test_parser.add_argument('--pypi-url', type=str, help='Full PyPI registry URL (overrides --base-url)')
    test_parser.add_argument('--maven-url', type=str, help='Full Maven registry URL (overrides --base-url)')
    # Authentication options for npm
    test_parser.add_argument('--npm-token', type=str, help='Bearer token for NPM registry authentication')
    test_parser.add_argument('--npm-username', type=str, help='Username for NPM registry basic authentication')
    test_parser.add_argument('--npm-password', type=str, help='Password for NPM registry basic authentication')
    # Authentication options for PyPI
    test_parser.add_argument('--pypi-token', type=str, help='Bearer token for PyPI registry authentication')
    test_parser.add_argument('--pypi-username', type=str, help='Username for PyPI registry basic authentication')
    test_parser.add_argument('--pypi-password', type=str, help='Password for PyPI registry basic authentication')
    # Authentication options for Maven
    test_parser.add_argument('--maven-username', type=str, help='Username for Maven registry basic authentication')
    test_parser.add_argument('--maven-password', type=str, help='Password for Maven registry basic authentication')
    test_parser.add_argument('--test-id', type=str, help='Custom test ID (default: auto-generated)')
    test_parser.add_argument('--output-dir', type=str, default='./load-test-results', help='Results output directory')
    test_parser.add_argument('--load-gen-id', type=str, default='gen-1', help='Load generator ID')
    test_parser.add_argument('--generate-html-report', action='store_true', help='Generate comprehensive HTML report after test completion')
    test_parser.add_argument('--html-report-path', type=str, default='./reports', help='Output directory for HTML report (default: ./reports)')
    test_parser.add_argument('--title', type=str, help='Custom title for the HTML report (e.g., "Production Load Test")')
    test_parser.add_argument('--packages', type=str, help='JSON file with custom package lists (format: {"npm": [], "pypi": [], "maven": []})')
    test_parser.add_argument('--repeat', action='store_true', help='Use cached metadata from previous run (saves time on repeated tests)')
    test_parser.add_argument('--metadata-cache-dir', type=str, default='./metadata-cache', help='Directory for metadata cache files (default: ./metadata-cache)')
    test_parser.set_defaults(func=test_command)
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate a report from existing test results', parents=[parent_parser])
    report_parser.set_defaults(func=report_command)
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup monitoring or SSH keys', parents=[parent_parser])
    setup_parser.set_defaults(func=setup_command)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration and connectivity', parents=[parent_parser])
    validate_parser.set_defaults(func=validate_command)
    
    # Aggregate command
    aggregate_parser = subparsers.add_parser('aggregate', help='Aggregate results from multiple load generators', parents=[parent_parser])
    aggregate_parser.set_defaults(func=aggregate_command)
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command provided, show help
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    args.func(args)


if __name__ == '__main__':
    cli()

