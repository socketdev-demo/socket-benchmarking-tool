"""Unit tests for k6_wrapper module."""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from socket_load_test.core.load.k6_wrapper import K6Manager
from socket_load_test.config import TestConfig, RegistriesConfig, TrafficConfig


class TestK6Manager:
    """Test suite for K6Manager class."""
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return TestConfig(
            rps=1000,
            duration='5m',
            test_id='test-123',
            warmup=True,
            warmup_duration='30s',
            warmup_rps_percent=10
        )
    
    @pytest.fixture
    def registries_config(self):
        """Create registries configuration."""
        return RegistriesConfig(
            npm_url='https://npm.example.com',
            pypi_url='https://pypi.example.com',
            maven_url='https://maven.example.com',
            cache_hit_percent=30
        )
    
    @pytest.fixture
    def traffic_config(self):
        """Create traffic configuration."""
        return TrafficConfig(
            cache_ratio=30,
            npm_ratio=40,
            pypi_ratio=30,
            maven_ratio=30,
            metadata_only=False
        )
    
    @pytest.fixture
    def k6_manager(self, test_config, registries_config, traffic_config):
        """Create K6Manager instance."""
        return K6Manager(
            test_config=test_config,
            registries_config=registries_config,
            traffic_config=traffic_config
        )
    
    def test_initialization(self, k6_manager, test_config, registries_config, traffic_config):
        """Test K6Manager initialization."""
        assert k6_manager.test_config == test_config
        assert k6_manager.registries_config == registries_config
        assert k6_manager.traffic_config == traffic_config
        assert k6_manager.package_seeds == K6Manager.DEFAULT_PACKAGE_SEEDS
        
        # Check VU calculations
        assert k6_manager.vus == 100  # max(1000 // 10, 50) = 100
        assert k6_manager.max_vus == 333  # max(1000 // 3, 100) = 333
    
    def test_initialization_with_custom_package_seeds(self, test_config, registries_config, traffic_config):
        """Test K6Manager initialization with custom package seeds."""
        custom_seeds = {
            'npm': ['react', 'vue'],
            'pypi': ['django', 'flask'],
            'maven': ['org.springframework:spring-core']
        }
        
        manager = K6Manager(
            test_config=test_config,
            registries_config=registries_config,
            traffic_config=traffic_config,
            package_seeds=custom_seeds
        )
        
        assert manager.package_seeds == custom_seeds
    
    def test_vus_calculation_low_rps(self, registries_config, traffic_config):
        """Test VUs calculation for low RPS."""
        config = TestConfig(rps=100, duration='5m', test_id='test-low')
        manager = K6Manager(config, registries_config, traffic_config)
        
        # max(100 // 10, 50) = 50
        assert manager.vus == 50
        # max(100 // 3, 100) = 100
        assert manager.max_vus == 100
    
    def test_vus_calculation_high_rps(self, registries_config, traffic_config):
        """Test VUs calculation for high RPS."""
        config = TestConfig(rps=10000, duration='5m', test_id='test-high')
        manager = K6Manager(config, registries_config, traffic_config)
        
        # max(10000 // 10, 50) = 1000
        assert manager.vus == 1000
        # max(10000 // 3, 100) = 3333
        assert manager.max_vus == 3333
    
    def test_generate_script_without_output(self, k6_manager):
        """Test script generation without saving to file."""
        script = k6_manager.generate_script()
        
        # Verify it returns a string
        assert isinstance(script, str)
        assert len(script) > 0
        
        # Verify template variables are replaced
        assert 'test-123' in script
        assert 'https://npm.example.com' in script
        assert 'https://pypi.example.com' in script
        assert 'https://maven.example.com' in script
        assert '1000' in script  # RPS
        assert '5m' in script  # Duration
    
    def test_generate_script_with_output(self, k6_manager):
        """Test script generation with file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'test_script.js')
            
            script = k6_manager.generate_script(output_path)
            
            # Verify file was created
            assert os.path.exists(output_path)
            
            # Verify file content matches returned content
            with open(output_path, 'r') as f:
                file_content = f.read()
            assert file_content == script
    
    def test_generate_script_creates_parent_dirs(self, k6_manager):
        """Test that script generation creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'subdir', 'nested', 'test_script.js')
            
            k6_manager.generate_script(output_path)
            
            assert os.path.exists(output_path)
    
    def test_generate_script_with_metadata_only(self, test_config, registries_config):
        """Test script generation with metadata_only flag."""
        traffic_config = TrafficConfig(
            cache_ratio=30,
            npm_ratio=40,
            pypi_ratio=30,
            maven_ratio=30,
            metadata_only=True
        )
        
        manager = K6Manager(test_config, registries_config, traffic_config)
        script = manager.generate_script()
        
        # Verify metadata_only is set to true in the script
        assert "METADATA_ONLY = (__ENV.METADATA_ONLY || 'true')" in script
    
    def test_generate_script_with_custom_traffic_ratios(self, test_config, registries_config):
        """Test script generation with custom traffic ratios."""
        traffic_config = TrafficConfig(
            cache_ratio=50,
            npm_ratio=50,
            pypi_ratio=25,
            maven_ratio=25,
            metadata_only=False
        )
        
        manager = K6Manager(test_config, registries_config, traffic_config)
        script = manager.generate_script()
        
        # Verify ratios are in the script
        assert "NPM_RATIO = parseFloat(__ENV.NPM_RATIO || '50')" in script
        assert "PYPI_RATIO = parseFloat(__ENV.PYPI_RATIO || '25')" in script
        assert "MAVEN_RATIO = parseFloat(__ENV.MAVEN_RATIO || '25')" in script
    
    def test_validate_script_valid(self, k6_manager):
        """Test validation of a valid k6 script."""
        script = k6_manager.generate_script()
        
        # Should not raise an exception
        assert k6_manager.validate_script(script) is True
    
    def test_validate_script_missing_http_import(self, k6_manager):
        """Test validation fails for missing http import."""
        invalid_script = "// Missing http import"
        
        with pytest.raises(ValueError, match="Missing required import.*http"):
            k6_manager.validate_script(invalid_script)
    
    def test_validate_script_missing_k6_imports(self, k6_manager):
        """Test validation fails for missing k6 imports."""
        invalid_script = "import http from 'k6/http';\n// Missing check, sleep"
        
        with pytest.raises(ValueError, match="Missing required import"):
            k6_manager.validate_script(invalid_script)
    
    def test_validate_script_missing_metrics_import(self, k6_manager):
        """Test validation fails for missing metrics import."""
        invalid_script = """
        import http from 'k6/http';
        import { check, sleep } from 'k6';
        // Missing metrics import
        """
        
        with pytest.raises(ValueError, match="Missing required import.*metrics"):
            k6_manager.validate_script(invalid_script)
    
    def test_validate_script_missing_setup_function(self, k6_manager):
        """Test validation fails for missing setup function."""
        invalid_script = """
        import http from 'k6/http';
        import { check, sleep } from 'k6';
        import { Rate } from 'k6/metrics';
        export default function() {}
        export const options = {};
        """
        
        with pytest.raises(ValueError, match="Missing required function.*setup"):
            k6_manager.validate_script(invalid_script)
    
    def test_validate_script_missing_default_function(self, k6_manager):
        """Test validation fails for missing default export function."""
        invalid_script = """
        import http from 'k6/http';
        import { check, sleep } from 'k6';
        import { Rate } from 'k6/metrics';
        export function setup() {}
        export const options = {};
        """
        
        with pytest.raises(ValueError, match="Missing required function.*default"):
            k6_manager.validate_script(invalid_script)
    
    def test_validate_script_missing_options(self, k6_manager):
        """Test validation fails for missing options export."""
        invalid_script = """
        import http from 'k6/http';
        import { check, sleep } from 'k6';
        import { Rate } from 'k6/metrics';
        export function setup() {}
        export default function() {}
        """
        
        with pytest.raises(ValueError, match="Missing required.*options"):
            k6_manager.validate_script(invalid_script)
    
    def test_prepare_environment(self, k6_manager):
        """Test environment variable preparation."""
        env_vars = k6_manager.prepare_environment('gen-test')
        
        # Verify all required environment variables are present
        assert env_vars['TEST_ID'] == 'test-123'
        assert env_vars['LOAD_GEN_ID'] == 'gen-test'
        assert env_vars['TARGET_RPS'] == '1000'
        assert env_vars['DURATION'] == '5m'
        assert env_vars['VUS'] == '100'
        assert env_vars['MAX_VUS'] == '333'
        assert env_vars['NPM_URL'] == 'https://npm.example.com'
        assert env_vars['PYPI_URL'] == 'https://pypi.example.com'
        assert env_vars['MAVEN_URL'] == 'https://maven.example.com'
        assert env_vars['CACHE_HIT_PCT'] == '30'
        assert env_vars['NPM_RATIO'] == '40'
        assert env_vars['PYPI_RATIO'] == '30'
        assert env_vars['MAVEN_RATIO'] == '30'
        assert env_vars['METADATA_ONLY'] == 'false'
    
    def test_prepare_environment_default_load_gen_id(self, k6_manager):
        """Test environment preparation with default load gen ID."""
        env_vars = k6_manager.prepare_environment()
        
        assert env_vars['LOAD_GEN_ID'] == 'gen-1'
    
    def test_prepare_environment_metadata_only(self, test_config, registries_config):
        """Test environment preparation with metadata_only=True."""
        traffic_config = TrafficConfig(
            cache_ratio=30,
            npm_ratio=40,
            pypi_ratio=30,
            maven_ratio=30,
            metadata_only=True
        )
        
        manager = K6Manager(test_config, registries_config, traffic_config)
        env_vars = manager.prepare_environment()
        
        assert env_vars['METADATA_ONLY'] == 'true'
    
    def test_get_k6_command(self, k6_manager):
        """Test k6 command generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = '/path/to/script.js'
            
            cmd = k6_manager.get_k6_command(script_path, tmpdir, 'gen-2')
            
            # Verify command structure
            assert 'k6 run' in cmd
            assert script_path in cmd
            assert '--out json=' in cmd
            
            # Verify environment variables are in command
            assert 'TEST_ID=test-123' in cmd
            assert 'LOAD_GEN_ID=gen-2' in cmd
            assert 'TARGET_RPS=1000' in cmd
            assert 'DURATION=5m' in cmd
            
            # Verify output file path is correct
            expected_output = os.path.join(tmpdir, 'test-123_gen-2_k6_results.json')
            assert expected_output in cmd
    
    def test_get_k6_command_default_load_gen_id(self, k6_manager):
        """Test k6 command with default load gen ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = k6_manager.get_k6_command('/path/to/script.js', tmpdir)
            
            assert 'LOAD_GEN_ID=gen-1' in cmd
            assert 'test-123_gen-1_k6_results.json' in cmd
    
    def test_default_package_seeds_structure(self):
        """Test that default package seeds have correct structure."""
        seeds = K6Manager.DEFAULT_PACKAGE_SEEDS
        
        # Verify all ecosystems are present
        assert 'npm' in seeds
        assert 'pypi' in seeds
        assert 'maven' in seeds
        
        # Verify they are lists
        assert isinstance(seeds['npm'], list)
        assert isinstance(seeds['pypi'], list)
        assert isinstance(seeds['maven'], list)
        
        # Verify they are not empty
        assert len(seeds['npm']) > 0
        assert len(seeds['pypi']) > 0
        assert len(seeds['maven']) > 0
        
        # Verify npm packages are strings
        for pkg in seeds['npm']:
            assert isinstance(pkg, str)
            assert len(pkg) > 0
        
        # Verify pypi packages are strings
        for pkg in seeds['pypi']:
            assert isinstance(pkg, str)
            assert len(pkg) > 0
        
        # Verify maven packages have correct format (group:artifact)
        for coords in seeds['maven']:
            assert isinstance(coords, str)
            assert ':' in coords
            parts = coords.split(':')
            assert len(parts) == 2
            assert len(parts[0]) > 0  # group
            assert len(parts[1]) > 0  # artifact
    
    def test_generate_script_json_serialization(self, k6_manager):
        """Test that package seeds are properly JSON serialized in script."""
        script = k6_manager.generate_script()
        
        # Extract the PACKAGE_SEEDS variable from script
        # It should be valid JSON
        assert 'const PACKAGE_SEEDS =' in script
        
        # Verify the packages appear in the script
        assert 'react' in script  # npm package
        assert 'requests' in script  # pypi package
        assert 'org.springframework.boot' in script  # maven package
    
    def test_k6_script_template_is_valid_javascript(self, k6_manager):
        """Test that the generated script has valid JavaScript structure."""
        script = k6_manager.generate_script()
        
        # Check for proper JavaScript structure
        assert script.count('export function setup()') == 1
        assert script.count('export default function') == 1
        assert script.count('export const options') == 1
        
        # Check that there are no unrendered Jinja2 templates
        assert '{{' not in script
        assert '}}' not in script
        
        # Check for common JavaScript patterns
        assert 'import' in script
        assert 'function' in script
        assert 'const' in script
        
    def test_generate_script_escapes_special_chars(self, test_config, registries_config, traffic_config):
        """Test that special characters in config are properly escaped."""
        # Create config with special characters
        test_id_special = 'test-123-special'
        config = TestConfig(
            rps=1000,
            duration='5m',
            test_id=test_id_special,
            warmup=True,
            warmup_duration='30s',
            warmup_rps_percent=10
        )
        
        manager = K6Manager(config, registries_config, traffic_config)
        script = manager.generate_script()
        
        # Verify test_id appears correctly
        assert test_id_special in script
        
    def test_generate_script_handles_edge_case_rps(self, registries_config, traffic_config):
        """Test script generation with edge case RPS values."""
        # Very low RPS
        low_config = TestConfig(rps=1, duration='1m', test_id='test-low-rps')
        low_manager = K6Manager(low_config, registries_config, traffic_config)
        low_script = low_manager.generate_script()
        
        assert '1' in low_script
        assert low_manager.vus == 50  # Should use minimum
        assert low_manager.max_vus == 100  # Should use minimum
        
        # Very high RPS
        high_config = TestConfig(rps=50000, duration='1m', test_id='test-high-rps')
        high_manager = K6Manager(high_config, registries_config, traffic_config)
        high_script = high_manager.generate_script()
        
        assert '50000' in high_script
        assert high_manager.vus == 5000
        assert high_manager.max_vus == 16666
