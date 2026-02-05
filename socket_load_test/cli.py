"""Command-line interface for socket-load-test."""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
import click

from .config import TestConfig, RegistriesConfig, TrafficConfig
from .core.load.k6_wrapper import K6Manager


@click.group()
@click.version_option()
@click.option("--config", type=click.Path(exists=True), help="Path to config file")
@click.option("--verbose", is_flag=True, help="Enable verbose output")
@click.option("--log-file", type=click.Path(), help="Path to log file")
@click.pass_context
def cli(ctx, config, verbose, log_file):
    """Socket Load Test - Distributed load testing for Socket Registry Firewall."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["log_file"] = log_file


@cli.command()
@click.option("--no-docker", is_flag=True, help="Run k6 locally without Docker")
@click.option("--host", help="Target firewall host")
@click.option("--port", type=int, default=8080, help="Target firewall port")
@click.option("--duration", default="60s", help="Test duration (e.g., 60s, 5m)")
@click.option("--vus", type=int, help="Number of virtual users")
@click.option("--rps", type=int, required=True, help="Target requests per second")
@click.option("--ecosystems", required=True, help="Comma-separated list of ecosystems to test (npm,pypi,maven)")
@click.option("--base-url", help="Base firewall URL (use with --npm-path, --pypi-path, --maven-path)")
@click.option("--npm-path", help="Path for npm registry (e.g., /npm or /custom/npm)")
@click.option("--pypi-path", help="Path for pypi registry (e.g., /pypi or /simple)")
@click.option("--maven-path", help="Path for maven registry (e.g., /maven or /maven2)")
@click.option("--npm-url", help="Full NPM registry URL (overrides --base-url)")
@click.option("--pypi-url", help="Full PyPI registry URL (overrides --base-url)")
@click.option("--maven-url", help="Full Maven registry URL (overrides --base-url)")
# Authentication options for npm
@click.option("--npm-token", help="Bearer token for NPM registry authentication")
@click.option("--npm-username", help="Username for NPM registry basic authentication")
@click.option("--npm-password", help="Password for NPM registry basic authentication")
# Authentication options for PyPI
@click.option("--pypi-token", help="Bearer token for PyPI registry authentication")
@click.option("--pypi-username", help="Username for PyPI registry basic authentication")
@click.option("--pypi-password", help="Password for PyPI registry basic authentication")
# Authentication options for Maven
@click.option("--maven-username", help="Username for Maven registry basic authentication")
@click.option("--maven-password", help="Password for Maven registry basic authentication")
@click.option("--test-id", help="Custom test ID (default: auto-generated)")
@click.option("--output-dir", default="./load-test-results", help="Results output directory")
@click.option("--load-gen-id", default="gen-1", help="Load generator ID")
@click.option("--generate-html-report", is_flag=True, help="Generate comprehensive HTML report after test completion")
@click.option("--html-report-path", type=click.Path(), default="./reports", help="Output directory for HTML report (default: ./reports)")
@click.option("--packages", type=click.Path(exists=True), help="JSON file with custom package lists (format: {\"npm\": [], \"pypi\": [], \"maven\": []})")
@click.option("--verbose", is_flag=True, help="Show detailed package information and test configuration")
@click.pass_context
def test(ctx, no_docker, host, port, duration, vus, rps, ecosystems, base_url, npm_path, pypi_path, maven_path, 
         npm_url, pypi_url, maven_url, npm_token, npm_username, npm_password, pypi_token, pypi_username, 
         pypi_password, maven_username, maven_password, test_id, output_dir, load_gen_id, generate_html_report, html_report_path, packages, verbose):
    """Run a load test."""
    
    # Parse and validate ecosystems
    selected_ecosystems = [e.strip().lower() for e in ecosystems.split(',')]
    valid_ecosystems = ['npm', 'pypi', 'maven']
    
    for ecosystem in selected_ecosystems:
        if ecosystem not in valid_ecosystems:
            click.echo(f"Error: Invalid ecosystem '{ecosystem}'. Must be one of: {', '.join(valid_ecosystems)}", err=True)
            sys.exit(1)
    
    if not selected_ecosystems:
        click.echo("Error: At least one ecosystem must be specified", err=True)
        sys.exit(1)
    
    # Handle base-url + path combinations
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
        click.echo(f"Error: Missing URLs for selected ecosystems: {', '.join(missing_urls)}", err=True)
        click.echo("Must provide either:", err=True)
        for eco in missing_urls:
            click.echo(f"  - --{eco}-url, OR", err=True)
        click.echo(f"  - --base-url with appropriate paths (--{'-path, --'.join(missing_urls)}-path)", err=True)
        sys.exit(1)
    
    # Load custom packages if provided
    custom_packages = None
    if packages:
        try:
            with open(packages, 'r') as f:
                custom_packages = json.load(f)
            click.echo(f"Loaded custom packages from: {packages}")
            if verbose:
                for eco in selected_ecosystems:
                    if eco in custom_packages:
                        click.echo(f"  {eco}: {len(custom_packages[eco])} packages")
        except Exception as e:
            click.echo(f"Error loading packages file: {e}", err=True)
            sys.exit(1)
    
    # Generate test ID if not provided
    if not test_id:
        test_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Display configuration
    if no_docker:
        click.echo("Running k6 locally (no Docker)")
    else:
        click.echo("Running k6 with Docker)")
    
    click.echo(f"\nTest Configuration:")
    click.echo(f"  Test ID:      {test_id}")
    click.echo(f"  Duration:     {duration}")
    click.echo(f"  Target RPS:   {rps}")
    click.echo(f"  Ecosystems:   {', '.join(selected_ecosystems)}")
    if 'npm' in selected_ecosystems:
        click.echo(f"  NPM URL:      {npm_url}")
    if 'pypi' in selected_ecosystems:
        click.echo(f"  PyPI URL:     {pypi_url}")
    if 'maven' in selected_ecosystems:
        click.echo(f"  Maven URL:    {maven_url}")
    click.echo(f"  Output Dir:   {output_dir}")
    click.echo(f"  Load Gen ID:  {load_gen_id}")
    
    # Display package information if verbose
    if verbose:
        click.echo(f"\nPackage Configuration:")
        if custom_packages:
            click.echo(f"  Source:       Custom packages file ({packages})")
        else:
            click.echo(f"  Source:       Default package seeds")
        
        # Get package seeds (custom or default)
        from .core.load.k6_wrapper import K6Manager
        package_seeds = custom_packages or K6Manager.DEFAULT_PACKAGE_SEEDS
        
        for eco in selected_ecosystems:
            if eco in package_seeds:
                pkg_list = package_seeds[eco]
                click.echo(f"\n  {eco.upper()} Packages ({len(pkg_list)} total):")
                # Show first 10 packages and indicate if there are more
                for i, pkg in enumerate(pkg_list[:10]):
                    click.echo(f"    - {pkg}")
                if len(pkg_list) > 10:
                    click.echo(f"    ... and {len(pkg_list) - 10} more")
    
    click.echo()
    
    try:
        # Create configuration objects
        test_config = TestConfig(
            rps=rps,
            duration=duration,
            test_id=test_id,
            no_docker=no_docker
        )
        
        registries_config = RegistriesConfig(
            npm_url=npm_url,
            pypi_url=pypi_url,
            maven_url=maven_url,
            ecosystems=selected_ecosystems,
            # NPM authentication
            npm_token=npm_token,
            npm_username=npm_username,
            npm_password=npm_password,
            # PyPI authentication
            pypi_token=pypi_token,
            pypi_username=pypi_username,
            pypi_password=pypi_password,
            # Maven authentication
            maven_username=maven_username,
            maven_password=maven_password
        )
        
        traffic_config = TrafficConfig(ecosystems=selected_ecosystems)
        
        # Create K6Manager
        k6_manager = K6Manager(
            test_config=test_config,
            registries_config=registries_config,
            traffic_config=traffic_config,
            package_seeds=custom_packages
        )
        
        # Generate k6 script
        click.echo("Generating k6 test script...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            script_path = f.name
            script_content = k6_manager.generate_script()
            f.write(script_content)
        
        click.echo(f"k6 script generated: {script_path}")
        
        # Execute k6 test
        click.echo(f"\nStarting k6 load test...")
        click.echo("=" * 60)
        
        exit_code = k6_manager.execute_k6(
            script_path=script_path,
            output_dir=output_dir,
            load_gen_id=load_gen_id,
            no_docker=no_docker
        )
        
        click.echo("=" * 60)
        
        if exit_code == 0:
            click.echo(f"\n✓ Test completed successfully!")
            click.echo(f"  Results saved to: {output_dir}")
            click.echo(f"  Test ID: {test_id}")
            
            # Generate HTML report if requested
            if generate_html_report:
                click.echo(f"\nGenerating HTML report...")
                try:
                    from .core.reporting.comprehensive_report import generate_html_report as gen_report
                    import glob
                    
                    # Create config for report generation
                    test_configs = [{"test_id": test_id, "rps": rps}]
                    
                    # Determine test duration
                    result_files = glob.glob(f"{output_dir}/{test_id}_*_k6_results.json")
                    test_type = "Test"
                    duration_seconds = None
                    
                    if result_files:
                        try:
                            first_ts = None
                            last_ts = None
                            with open(result_files[0], 'r') as f:
                                for line in f:
                                    try:
                                        data = json.loads(line)
                                        if data.get('type') == 'Point' and 'time' in data.get('data', {}):
                                            ts = data['data']['time']
                                            if first_ts is None:
                                                first_ts = ts
                                            last_ts = ts
                                    except:
                                        continue
                            
                            if first_ts and last_ts:
                                start = datetime.fromisoformat(first_ts.replace('Z', '+00:00'))
                                end = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
                                duration_seconds = int((end - start).total_seconds())
                                
                                # Format test type based on duration
                                if duration_seconds < 90:
                                    test_type = f"{duration_seconds}-Second"
                                elif duration_seconds < 3600:
                                    minutes = int(round(duration_seconds / 60))
                                    test_type = f"{minutes}-Minute"
                                else:
                                    hours = int(round(duration_seconds / 3600))
                                    test_type = f"{hours}-Hour"
                        except Exception as e:
                            click.echo(f"  Warning: Could not determine test duration: {e}")
                    
                    # Set defaults if not detected
                    duration_seconds = duration_seconds or 300
                    
                    # Ensure output directory exists
                    os.makedirs(html_report_path, exist_ok=True)
                    
                    # Generate output file path
                    output_file = os.path.join(html_report_path, f"load-test-report-{test_type.lower()}.html")
                    
                    # Generate the report
                    gen_report(test_configs, output_dir, output_file, test_type, duration_seconds)
                    
                    click.echo(f"  ✓ HTML report generated: {output_file}")
                    
                except Exception as e:
                    click.echo(f"  ✗ Failed to generate HTML report: {e}", err=True)
                    if ctx.obj.get("verbose"):
                        import traceback
                        traceback.print_exc()
        else:
            click.echo(f"\n✗ Test failed with exit code: {exit_code}", err=True)
            sys.exit(exit_code)
            
        # Clean up temp script
        try:
            os.unlink(script_path)
        except:
            pass
            
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        if ctx.obj["verbose"]:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
def report():
    """Generate a report from existing test results."""
    click.echo("Report command - to be implemented")


@cli.command()
def setup():
    """Setup monitoring or SSH keys."""
    click.echo("Setup command - to be implemented")


@cli.command()
def validate():
    """Validate configuration and connectivity."""
    click.echo("Validate command - to be implemented")


@cli.command()
def aggregate():
    """Aggregate results from multiple load generators."""
    click.echo("Aggregate command - to be implemented")
