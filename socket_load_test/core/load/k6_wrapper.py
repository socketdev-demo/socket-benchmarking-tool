"""K6 load test script wrapper.

This module provides the K6Manager class for generating, validating, and managing
k6 load test scripts with multi-ecosystem support (npm, PyPI, Maven).
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Template, TemplateError

from ...config import TestConfig, RegistriesConfig, TrafficConfig


class K6Manager:
    """Manages k6 load test script generation and execution.
    
    This class handles:
    - Embedding and rendering the k6 script template with Jinja2
    - Generating k6 scripts with parameterized configurations
    - Validating k6 script parameters
    - Preparing environment variables for k6 execution
    """
    
    # Embedded k6 script template
    K6_SCRIPT_TEMPLATE = """import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate, Trend, Counter } from 'k6/metrics';
import encoding from 'k6/encoding';

// Custom metrics
const cacheHitRate = new Rate('cache_hits');
const metadataLatency = new Trend('metadata_latency');
const downloadLatency = new Trend('download_latency');
// Separate request duration metrics for metadata vs downloads
const metadataRequestDuration = new Trend('metadata_request_duration');
const downloadRequestDuration = new Trend('download_request_duration');
const errorRate = new Rate('errors');
const requestCounter = new Counter('total_requests');
const successCounter = new Counter('successful_requests');
const npmRequests = new Counter('npm_requests');
const pypiRequests = new Counter('pypi_requests');
const mavenRequests = new Counter('maven_requests');

// Bandwidth tracking - using Trend to preserve tags (Counter doesn't emit data points to JSON)
const responseSize = new Trend('response_bytes');

// HTTP Status Code tracking
const status2xx = new Counter('status_2xx');  // Success responses
const status404 = new Counter('status_404');  // Not Found (expected, not an error)
const status403 = new Counter('status_403');  // Forbidden (expected, not an error)
const status4xx = new Counter('status_4xx');  // Other client errors (excluding 404/403)
const status5xx = new Counter('status_5xx');  // Server errors
const statusTimeout = new Counter('status_timeout');  // Network timeouts (status 0)

// Configuration
const NPM_BASE_URL = __ENV.NPM_URL || '{{ npm_url }}';
const PYPI_BASE_URL = __ENV.PYPI_URL || '{{ pypi_url }}';
const MAVEN_BASE_URL = __ENV.MAVEN_URL || '{{ maven_url }}';
const CACHE_HIT_PERCENTAGE = parseFloat(__ENV.CACHE_HIT_PCT || '{{ cache_hit_pct }}');
const TEST_ID = __ENV.TEST_ID || '{{ test_id }}';
const LOAD_GENERATOR_ID = __ENV.LOAD_GEN_ID || 'gen-1';
const METADATA_ONLY = (__ENV.METADATA_ONLY || '{{ metadata_only }}') === 'true';

// Authentication configuration
const NPM_TOKEN = __ENV.NPM_TOKEN || '{{ npm_token }}';
const NPM_USERNAME = __ENV.NPM_USERNAME || '{{ npm_username }}';
const NPM_PASSWORD = __ENV.NPM_PASSWORD || '{{ npm_password }}';

const PYPI_TOKEN = __ENV.PYPI_TOKEN || '{{ pypi_token }}';
const PYPI_USERNAME = __ENV.PYPI_USERNAME || '{{ pypi_username }}';
const PYPI_PASSWORD = __ENV.PYPI_PASSWORD || '{{ pypi_password }}';

const MAVEN_USERNAME = __ENV.MAVEN_USERNAME || '{{ maven_username }}';
const MAVEN_PASSWORD = __ENV.MAVEN_PASSWORD || '{{ maven_password }}';

// Enabled ecosystems
const ECOSYSTEMS = {{ ecosystems | tojson }};

// Traffic ratios (percentages)
const NPM_RATIO = parseFloat(__ENV.NPM_RATIO || '{{ npm_ratio }}');
const PYPI_RATIO = parseFloat(__ENV.PYPI_RATIO || '{{ pypi_ratio }}');
const MAVEN_RATIO = parseFloat(__ENV.MAVEN_RATIO || '{{ maven_ratio }}');

// Top 100 packages per ecosystem (known to exist)
const PACKAGE_SEEDS = {{ package_seeds | tojson }};

// Pre-fetched metadata (if available)
const USE_PREFETCHED_METADATA = {{ use_prefetched_metadata | tojson }};
const PREFETCHED_METADATA = {{ pre_fetched_metadata | tojson }};

// Validation results (if available)
const USE_VALIDATION = {{ use_validation | tojson }};
const VALIDATION_RESULTS = {{ validation_results | tojson }};
const ERROR_RATE = parseFloat(__ENV.ERROR_RATE || '{{ error_rate }}');

// Helper functions
function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function parseMavenCoords(coords) {
  const [group, artifact] = coords.split(':');
  return { group, artifact };
}

// Build authentication headers for each ecosystem
function getNpmAuthHeaders() {
  const headers = {
    'User-Agent': 'npm/10.0.0 node/v20.0.0',
    'Accept': 'application/json'
  };
  
  // NPM registry authentication:
  // - Tokens use Bearer auth: Authorization: Bearer <token>
  // - Username/password use Basic auth: Authorization: Basic base64(username:password)
  if (NPM_TOKEN && NPM_TOKEN !== '') {
    headers['Authorization'] = `Bearer ${NPM_TOKEN}`;
  } else if (NPM_USERNAME && NPM_USERNAME !== '' && NPM_PASSWORD && NPM_PASSWORD !== '') {
    const credentials = encoding.b64encode(`${NPM_USERNAME}:${NPM_PASSWORD}`);
    headers['Authorization'] = `Basic ${credentials}`;
  }
  
  return headers;
}

function getPypiAuthHeaders() {
  const headers = {
    'User-Agent': 'pip/23.0 CPython/3.11.0',
    'Accept': '*/*'  // Changed from 'application/json' to match curl behavior for Artifactory compatibility
  };
  
  // PyPI authentication:
  // - Tokens use Basic auth with format: base64encode(__token__:token_value)
  // - Username/password use Basic auth with format: base64encode(username:password)
  if (PYPI_TOKEN && PYPI_TOKEN !== '') {
    const credentials = encoding.b64encode(`__token__:${PYPI_TOKEN}`);
    headers['Authorization'] = `Basic ${credentials}`;
  } else if (PYPI_USERNAME && PYPI_USERNAME !== '' && PYPI_PASSWORD && PYPI_PASSWORD !== '') {
    const credentials = encoding.b64encode(`${PYPI_USERNAME}:${PYPI_PASSWORD}`);
    headers['Authorization'] = `Basic ${credentials}`;
  }
  
  return headers;
}

function getMavenAuthHeaders() {
  const headers = {
    'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
    'Accept': 'application/xml'
  };
  
  if (MAVEN_USERNAME && MAVEN_USERNAME !== '' && MAVEN_PASSWORD && MAVEN_PASSWORD !== '') {
    const credentials = encoding.b64encode(`${MAVEN_USERNAME}:${MAVEN_PASSWORD}`);
    headers['Authorization'] = `Basic ${credentials}`;
  }
  
  return headers;
}

// Weighted random ecosystem selection based on ratios
function selectEcosystem() {
  const rand = Math.random() * 100;
  let cumulative = 0;
  
  if (ECOSYSTEMS.includes('npm')) {
    cumulative += NPM_RATIO;
    if (rand < cumulative) return 'npm';
  }
  
  if (ECOSYSTEMS.includes('pypi')) {
    cumulative += PYPI_RATIO;
    if (rand < cumulative) return 'pypi';
  }
  
  if (ECOSYSTEMS.includes('maven')) {
    cumulative += MAVEN_RATIO;
    if (rand < cumulative) return 'maven';
  }
  
  // Fallback to first available ecosystem
  return ECOSYSTEMS[0];
}

// Fetch versions for a package
function fetchNpmVersions(pkg) {
  try {
    const response = http.get(`${NPM_BASE_URL}/${pkg}`, { 
      headers: getNpmAuthHeaders(),
      timeout: '30s'
    });
    if (response.status === 200) {
      const data = JSON.parse(response.body);
      const versions = Object.keys(data.versions || {}).slice(0, 5);
      return versions.length > 0 ? versions : ['latest'];
    }
  } catch (e) {
    // Silent fail - use default
  }
  return ['latest'];
}

function fetchPypiVersions(pkg) {
  try {
    // Use Simple API (PEP 503) by default instead of JSON API
    const response = http.get(`${PYPI_BASE_URL}/simple/${pkg}/`, { 
      headers: getPypiAuthHeaders(),
      timeout: '30s'
    });
    if (response.status === 200) {
      // Parse HTML to extract versions from links
      // Simple regex to extract version numbers from package filenames
      const html = response.body;
      const pattern = new RegExp(pkg + '-([0-9]+\\.[0-9]+(?:\\.[0-9]+)?[^"]*?)(?:-py|\\.tar\\.gz|\\.whl)', 'gi');
      const matches = [];
      let match;
      while ((match = pattern.exec(html)) !== null) {
        if (match[1] && !matches.includes(match[1])) {
          matches.push(match[1]);
        }
      }
      // Return last 5 versions
      const versions = matches.slice(Math.max(0, matches.length - 5));
      return versions.length > 0 ? versions : ['1.0.0'];
    }
  } catch (e) {
    // Silent fail - use default
  }
  return ['1.0.0'];
}

function fetchMavenVersions(coords) {
  try {
    const { group, artifact } = parseMavenCoords(coords);
    const groupPath = group.replace(/\\./g, '/');
    const url = `${MAVEN_BASE_URL}/${groupPath}/${artifact}/maven-metadata.xml`;
    
    const response = http.get(url, { 
      headers: getMavenAuthHeaders(),
      timeout: '30s'
    });
    if (response.status === 200) {
      const matches = response.body.match(/<version>([^<]+)<\\/version>/g);
      if (matches) {
        const versions = matches.map(m => m.replace(/<\\/?version>/g, '')).slice(-5);
        return versions.length > 0 ? versions : ['1.0.0'];
      }
    }
  } catch (e) {
    // Silent fail - use default
  }
  return ['1.0.0'];
}

// Setup function - runs once before test starts
export function setup() {
  console.log('='.repeat(60));
  console.log('LOAD TEST CONFIGURATION');
  console.log('='.repeat(60));
  console.log(`Test ID:              ${TEST_ID}`);
  console.log(`Load Generator:       ${LOAD_GENERATOR_ID}`);
  console.log(`Target RPS:           ${__ENV.TARGET_RPS || '{{ target_rps }}'}`);
  console.log(`Duration:             ${__ENV.DURATION || '{{ duration }}'}`);
  console.log(`Pre-allocated VUs:    ${__ENV.VUS || '{{ vus }}'}`);
  console.log(`Max VUs:              ${__ENV.MAX_VUS || '{{ max_vus }}'}`);
  console.log(`Cache Hit %:          ${CACHE_HIT_PERCENTAGE}%`);
  console.log(`Metadata Only:        ${METADATA_ONLY}`);
  console.log(`Enabled Ecosystems:   ${ECOSYSTEMS.join(', ')}`);
  console.log(`Using Prefetched:     ${USE_PREFETCHED_METADATA}`);
  console.log(`Using Validation:     ${USE_VALIDATION}`);
  if (USE_VALIDATION) {
    console.log(`Error Rate:           ${ERROR_RATE}%`);
  }
  console.log('');
  console.log('Registry URLs:');
  if (ECOSYSTEMS.includes('npm')) {
    console.log(`  npm:                ${NPM_BASE_URL}`);
  }
  if (ECOSYSTEMS.includes('pypi')) {
    console.log(`  PyPI:               ${PYPI_BASE_URL}`);
  }
  if (ECOSYSTEMS.includes('maven')) {
    console.log(`  Maven:              ${MAVEN_BASE_URL}`);
  }
  console.log('');
  console.log('Traffic Distribution:');
  if (ECOSYSTEMS.includes('npm')) {
    console.log(`  npm:                ${NPM_RATIO}%`);
  }
  if (ECOSYSTEMS.includes('pypi')) {
    console.log(`  PyPI:               ${PYPI_RATIO}%`);
  }
  if (ECOSYSTEMS.includes('maven')) {
    console.log(`  Maven:              ${MAVEN_RATIO}%`);
  }
  console.log('');
  console.log('Request Types:');
  console.log(`  Metadata requests:  ${METADATA_ONLY ? '100%' : '40%'}`);
  console.log(`  Download requests:  ${METADATA_ONLY ? '0%' : '60%'}`);
  console.log('='.repeat(60));
  
  const database = {
    npm: [],
    pypi: [],
    maven: []
  };
  
  // Store configuration in database for report
  database.config = {
    test_id: TEST_ID,
    load_generator: LOAD_GENERATOR_ID,
    target_rps: parseInt(__ENV.TARGET_RPS || '{{ target_rps }}'),
    duration: __ENV.DURATION || '{{ duration }}',
    vus: parseInt(__ENV.VUS || '{{ vus }}'),
    max_vus: parseInt(__ENV.MAX_VUS || '{{ max_vus }}'),
    cache_hit_pct: CACHE_HIT_PERCENTAGE,
    metadata_only: METADATA_ONLY,
    ecosystems: ECOSYSTEMS,
    npm_ratio: NPM_RATIO,
    pypi_ratio: PYPI_RATIO,
    maven_ratio: MAVEN_RATIO,
    npm_url: NPM_BASE_URL,
    pypi_url: PYPI_BASE_URL,
    maven_url: MAVEN_BASE_URL,
    timestamp: new Date().toISOString()
  };
  
  // Use validation results if available (preferred), otherwise use pre-fetched metadata, or fetch from registries
  if (USE_VALIDATION) {
    console.log('');
    console.log('Using validated packages from Python script...');
    console.log('='.repeat(60));
    
    // Load validated packages and combine valid + invalid
    if (VALIDATION_RESULTS.npm) {
      const valid = VALIDATION_RESULTS.npm.valid || [];
      const invalid = VALIDATION_RESULTS.npm.invalid || [];
      database.npm = valid.concat(invalid);
      console.log(`  ✓ Loaded ${database.npm.length} npm packages (${valid.length} valid, ${invalid.length} invalid)`);
    }
    if (VALIDATION_RESULTS.pypi) {
      const valid = VALIDATION_RESULTS.pypi.valid || [];
      const invalid = VALIDATION_RESULTS.pypi.invalid || [];
      database.pypi = valid.concat(invalid);
      console.log(`  ✓ Loaded ${database.pypi.length} PyPI packages (${valid.length} valid, ${invalid.length} invalid)`);
    }
    if (VALIDATION_RESULTS.maven) {
      const valid = VALIDATION_RESULTS.maven.valid || [];
      const invalid = VALIDATION_RESULTS.maven.invalid || [];
      database.maven = valid.concat(invalid);
      console.log(`  ✓ Loaded ${database.maven.length} Maven packages (${valid.length} valid, ${invalid.length} invalid)`);
    }
    
    console.log('='.repeat(60));
    console.log('SETUP COMPLETE! (using validated packages)');
    console.log(`  npm packages:   ${database.npm.length}`);
    console.log(`  pypi packages:  ${database.pypi.length}`);
    console.log(`  maven packages: ${database.maven.length}`);
    console.log('='.repeat(60));
  } else if (USE_PREFETCHED_METADATA) {
    console.log('');
    console.log('Using pre-fetched metadata from Python script...');
    console.log('='.repeat(60));
    
    // Load pre-fetched metadata directly
    if (PREFETCHED_METADATA.npm) {
      database.npm = PREFETCHED_METADATA.npm;
      console.log(`  ✓ Loaded ${database.npm.length} npm packages from cache`);
    }
    if (PREFETCHED_METADATA.pypi) {
      database.pypi = PREFETCHED_METADATA.pypi;
      console.log(`  ✓ Loaded ${database.pypi.length} PyPI packages from cache`);
    }
    if (PREFETCHED_METADATA.maven) {
      database.maven = PREFETCHED_METADATA.maven;
      console.log(`  ✓ Loaded ${database.maven.length} Maven packages from cache`);
    }
    
    console.log('='.repeat(60));
    console.log('SETUP COMPLETE! (using cached metadata)');
    console.log(`  npm packages:   ${database.npm.length} (${database.npm.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log(`  pypi packages:  ${database.pypi.length} (${database.pypi.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log(`  maven packages: ${database.maven.length} (${database.maven.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log('='.repeat(60));
  } else {
    console.log('');
    console.log('SETUP: Fetching real package versions from registries...');
    console.log('This may take 5-10 minutes for 260+ packages...');
    console.log('='.repeat(60));
    
    const startTime = new Date();
    
    // Fetch packages for enabled ecosystems only
    if (ECOSYSTEMS.includes('npm') && PACKAGE_SEEDS.npm) {
      console.log(`\\nFetching versions for ${PACKAGE_SEEDS.npm.length} npm packages...`);
      let count = 0;
      for (const pkg of PACKAGE_SEEDS.npm) {
        const versions = fetchNpmVersions(pkg);
        database.npm.push({ name: pkg, versions: versions });
        count++;
        if (count % 20 === 0) {
          const elapsed = Math.floor((new Date() - startTime) / 1000);
          console.log(`  npm: ${count}/${PACKAGE_SEEDS.npm.length} (${elapsed}s elapsed)`);
        }
      }
    }
    
    if (ECOSYSTEMS.includes('pypi') && PACKAGE_SEEDS.pypi) {
      console.log(`\\nFetching versions for ${PACKAGE_SEEDS.pypi.length} PyPI packages...`);
      let count = 0;
      for (const pkg of PACKAGE_SEEDS.pypi) {
        const versions = fetchPypiVersions(pkg);
        database.pypi.push({ name: pkg, versions: versions });
        count++;
        if (count % 20 === 0) {
          const elapsed = Math.floor((new Date() - startTime) / 1000);
          console.log(`  pypi: ${count}/${PACKAGE_SEEDS.pypi.length} (${elapsed}s elapsed)`);
        }
      }
    }
    
    if (ECOSYSTEMS.includes('maven') && PACKAGE_SEEDS.maven) {
      console.log(`\\nFetching versions for ${PACKAGE_SEEDS.maven.length} Maven packages...`);
      let count = 0;
      for (const coords of PACKAGE_SEEDS.maven) {
        const versions = fetchMavenVersions(coords);
        const { group, artifact } = parseMavenCoords(coords);
        database.maven.push({ group: group, artifact: artifact, versions: versions });
        count++;
        if (count % 20 === 0) {
          const elapsed = Math.floor((new Date() - startTime) / 1000);
          console.log(`  maven: ${count}/${PACKAGE_SEEDS.maven.length} (${elapsed}s elapsed)`);
        }
      }
    }
    
    const totalTime = Math.floor((new Date() - startTime) / 1000);
    
    console.log('='.repeat(60));
    console.log('SETUP COMPLETE!');
    console.log(`  Total time: ${totalTime} seconds`);
    console.log(`  npm packages:   ${database.npm.length} (${database.npm.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log(`  pypi packages:  ${database.pypi.length} (${database.pypi.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log(`  maven packages: ${database.maven.length} (${database.maven.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
    console.log('='.repeat(60));
  }
  
  return database;
}

// Get package based on cache hit probability and validation results
function getPackage(ecosystem, data) {
  // If validation results are available, use them to control valid/invalid packages
  if (USE_VALIDATION && VALIDATION_RESULTS[ecosystem]) {
    const validPackages = VALIDATION_RESULTS[ecosystem].valid || [];
    const invalidPackages = VALIDATION_RESULTS[ecosystem].invalid || [];
    
    // Decide if this request should intentionally 404 based on error rate
    const shouldError = Math.random() * 100 < ERROR_RATE;
    
    if (shouldError && invalidPackages.length > 0) {
      // Select from invalid packages (will likely 404)
      return randomChoice(invalidPackages);
    } else if (validPackages.length > 0) {
      // Select from valid packages
      const rand = Math.random() * 100;
      
      if (rand < CACHE_HIT_PERCENTAGE) {
        // Cache hit - pick from top 20% (most popular)
        const topTierSize = Math.ceil(validPackages.length * 0.2);
        const topTier = validPackages.slice(0, topTierSize);
        return randomChoice(topTier);
      } else {
        // Cache miss - pick from all valid packages
        return randomChoice(validPackages);
      }
    }
    // Fall through to default logic if no valid packages
  }
  
  // Default logic when validation is not available
  const packages = data[ecosystem];
  const rand = Math.random() * 100;
  
  if (rand < CACHE_HIT_PERCENTAGE) {
    // Cache hit - pick from top 20% (most popular)
    const topTierSize = Math.ceil(packages.length * 0.2);
    const topTier = packages.slice(0, topTierSize);
    return randomChoice(topTier);
  } else {
    // Cache miss - pick from all packages
    return randomChoice(packages);
  }
}

function checkResponse(response, ecosystem, type, tags) {
  const success = response.status === 200 || response.status === 304;
  
  // Track HTTP status codes
  if (response.status === 0) {
    // Client-side timeout (k6 timeout, not server response)
    statusTimeout.add(1);
  } else if (response.status >= 200 && response.status < 300) {
    // 2xx Success
    status2xx.add(1);
  } else if (response.status === 404) {
    // 404 Not Found - expected behavior, not counted as error
    status404.add(1);
  } else if (response.status === 403) {
    // 403 Forbidden - expected behavior, not counted as error
    status403.add(1);
  } else if (response.status >= 400 && response.status < 500) {
    // Other 4xx errors (excluding 404/403)
    status4xx.add(1);
  } else if (response.status >= 500 && response.status < 600) {
    // 5xx Server errors
    status5xx.add(1);
  }
  
  // Error tracking: only count server errors (5xx) and other 4xx (excluding 404/403)
  // Don't count client-side timeouts (status 0) or expected 404/403
  const isServerError = (response.status >= 500 && response.status < 600) || 
                        (response.status >= 400 && response.status < 500 && 
                         response.status !== 404 && response.status !== 403);
  
  requestCounter.add(1);
  if (success) {
    successCounter.add(1);
  }
  errorRate.add(isServerError);
  
  // Track response size using Trend metric with explicit tags
  // Prefer Content-Length (works even when responseType is 'none'), fall back to body length
  let bytesTransferred = 0;
  const contentLengthHeader = response.headers && (response.headers['Content-Length'] || response.headers['content-length']);
  if (contentLengthHeader) {
    const parsedLength = parseInt(contentLengthHeader, 10);
    if (!isNaN(parsedLength)) {
      bytesTransferred = parsedLength;
    }
  }
  if (bytesTransferred === 0 && response.body) {
    bytesTransferred = response.body.length || 0;
  }
  responseSize.add(bytesTransferred, tags || { ecosystem, type });
  
  // Check cache status
  const cacheHeader = response.headers['X-Cache-Status'] || 
                      response.headers['x-cache-status'] ||
                      response.headers['X-Cache'] ||
                      response.headers['x-cache'];
  
  if (cacheHeader) {
    const headerValue = String(cacheHeader).toLowerCase();
    const isHit = headerValue.includes('hit');
    cacheHitRate.add(isHit);
  }
  
  return success;
}

// NPM requests
function npmMetadataRequest(data) {
  const pkg = getPackage('npm', data);
  const url = `${NPM_BASE_URL}/${pkg.name}`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getNpmAuthHeaders(),
    timeout: '60s',
    tags: { 
      ecosystem: 'npm', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'npm', 'metadata', { ecosystem: 'npm', type: 'metadata' });
  metadataLatency.add(duration);
  metadataRequestDuration.add(duration, { ecosystem: 'npm', type: 'metadata' });
  npmRequests.add(1);
}

function npmDownloadRequest(data) {
  const pkg = getPackage('npm', data);
  const version = randomChoice(pkg.versions);
  const url = `${NPM_BASE_URL}/${pkg.name}`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getNpmAuthHeaders(),
    timeout: '120s',  // Downloads can be large, allow more time
    tags: { 
      ecosystem: 'npm', 
      type: 'download',
      package: pkg.name,
      version: version,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'npm', 'download', { ecosystem: 'npm', type: 'download' });
  downloadLatency.add(duration);
  downloadRequestDuration.add(duration, { ecosystem: 'npm', type: 'download' });
  npmRequests.add(1);
}

// PyPI requests
function pypiSimpleRequest(data) {
  const pkg = getPackage('pypi', data);
  const url = `${PYPI_BASE_URL}/simple/${pkg.name}/`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getPypiAuthHeaders(),
    timeout: '60s',
    tags: { 
      ecosystem: 'pypi', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'pypi', 'metadata', { ecosystem: 'pypi', type: 'metadata' });
  metadataLatency.add(duration);
  metadataRequestDuration.add(duration, { ecosystem: 'pypi', type: 'metadata' });
  pypiRequests.add(1);
}

function pypiJsonRequest(data) {
  const pkg = getPackage('pypi', data);
  const url = `${PYPI_BASE_URL}/pypi/${pkg.name}/json`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getPypiAuthHeaders(),  // Removed Accept override to use the default from getPypiAuthHeaders()
    timeout: '60s',
    tags: { 
      ecosystem: 'pypi', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'pypi', 'metadata', { ecosystem: 'pypi', type: 'metadata' });
  metadataLatency.add(duration);
  metadataRequestDuration.add(duration, { ecosystem: 'pypi', type: 'metadata' });
  pypiRequests.add(1);
}

function pypiDownloadRequest(data) {
  const pkg = getPackage('pypi', data);
  const version = randomChoice(pkg.versions);
  const url = `${PYPI_BASE_URL}/simple/${pkg.name}/`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getPypiAuthHeaders(),
    timeout: '120s',  // Downloads can be large, allow more time
    tags: { 
      ecosystem: 'pypi', 
      type: 'download',
      package: pkg.name,
      version: version,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'pypi', 'download', { ecosystem: 'pypi', type: 'download' });
  downloadLatency.add(duration);
  downloadRequestDuration.add(duration, { ecosystem: 'pypi', type: 'download' });
  pypiRequests.add(1);
}

// Maven requests
function mavenMetadataRequest(data) {
  const pkg = getPackage('maven', data);
  const groupPath = pkg.group.replace(/\\./g, '/');
  const url = `${MAVEN_BASE_URL}/${groupPath}/${pkg.artifact}/maven-metadata.xml`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getMavenAuthHeaders(),
    timeout: '60s',
    tags: { 
      ecosystem: 'maven', 
      type: 'metadata',
      package: `${pkg.group}:${pkg.artifact}`,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'maven', 'metadata', { ecosystem: 'maven', type: 'metadata' });
  metadataLatency.add(duration);
  metadataRequestDuration.add(duration, { ecosystem: 'maven', type: 'metadata' });
  mavenRequests.add(1);
}

function mavenDownloadRequest(data) {
  const pkg = getPackage('maven', data);
  const version = randomChoice(pkg.versions);
  const groupPath = pkg.group.replace(/\\./g, '/');
  const url = `${MAVEN_BASE_URL}/${groupPath}/${pkg.artifact}/${version}/${pkg.artifact}-${version}.jar`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: getMavenAuthHeaders(),
    timeout: '120s',  // Downloads can be large, allow more time
    tags: { 
      ecosystem: 'maven', 
      type: 'download',
      package: `${pkg.group}:${pkg.artifact}`,
      version: version,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'maven', 'download', { ecosystem: 'maven', type: 'download' });
  downloadLatency.add(duration);
  downloadRequestDuration.add(duration, { ecosystem: 'maven', type: 'download' });
  mavenRequests.add(1);
}

// Main scenario
export default function (data) {
  const ecosystem = selectEcosystem();
  
  if (METADATA_ONLY) {
    // Metadata-only mode
    switch (ecosystem) {
      case 'npm':
        npmMetadataRequest(data);
        break;
      case 'pypi':
        // Default to Simple API (PEP 503)
        pypiSimpleRequest(data);
        break;
      case 'maven':
        mavenMetadataRequest(data);
        break;
    }
  } else {
    // Mixed mode: 40% metadata, 60% downloads
    const isMetadata = Math.random() < 0.4;
    
    if (isMetadata) {
      switch (ecosystem) {
        case 'npm':
          npmMetadataRequest(data);
          break;
        case 'pypi':
          // Default to Simple API (PEP 503)
          pypiSimpleRequest(data);
          break;
        case 'maven':
          mavenMetadataRequest(data);
          break;
      }
    } else {
      switch (ecosystem) {
        case 'npm':
          npmDownloadRequest(data);
          break;
        case 'pypi':
          pypiDownloadRequest(data);
          break;
        case 'maven':
          mavenDownloadRequest(data);
          break;
      }
    }
  }
}

export const options = {
  setupTimeout: '10m',
  scenarios: {
    load_test: {
      executor: 'constant-arrival-rate',
      rate: parseInt(__ENV.TARGET_RPS || '{{ target_rps }}'),
      timeUnit: '1s',
      duration: __ENV.DURATION || '{{ duration }}',
      preAllocatedVUs: parseInt(__ENV.VUS || '{{ vus }}'),
      maxVUs: parseInt(__ENV.MAX_VUS || '{{ max_vus }}'),
    },
  },
};
"""
    
    # Default package seeds
    DEFAULT_PACKAGE_SEEDS = {
        'npm': [
            'react', 'lodash', 'chalk', 'commander', 'express', 'axios', 'debug', 
            'request', 'async', 'moment', 'typescript', 'webpack', 'eslint', 'jest', 
            'mocha', 'babel-core', 'core-js', 'tslib', 'yargs', 'inquirer', 'uuid', 
            'dotenv', 'classnames', 'prop-types', 'react-dom', 'colors', 'minimist', 
            'semver', 'glob', 'mkdirp', 'rimraf', 'through2', 'fs-extra', 'bluebird', 
            'underscore', 'body-parser', 'cors', 'express-validator', 'jsonwebtoken', 
            'bcrypt', 'mongoose', 'sequelize', 'mysql', 'pg', 'redis', 'ws', 
            'socket.io', 'nodemon', 'concurrently', 'cross-env'
        ],
        'pypi': [
            'requests', 'urllib3', 'certifi', 'charset-normalizer', 'idna', 'six', 
            'python-dateutil', 'setuptools', 'pip', 'wheel', 'packaging', 'pyparsing', 
            'attrs', 'pytz', 'importlib-metadata', 'zipp', 'typing-extensions', 
            'pyyaml', 'click', 'jinja2', 'markupsafe', 'werkzeug', 'flask', 'django', 
            'fastapi', 'pydantic', 'sqlalchemy', 'psycopg2', 'pymysql', 'redis', 
            'celery', 'kombu', 'amqp', 'vine', 'billiard', 'boto3', 'botocore', 
            's3transfer', 'awscli', 'cryptography', 'cffi', 'pycparser', 'pyopenssl', 
            'numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn', 'pillow'
        ],
        'maven': [
            'org.springframework.boot:spring-boot-starter-web',
            'org.springframework.boot:spring-boot-starter-data-jpa',
            'org.springframework.boot:spring-boot-starter-security',
            'org.springframework.boot:spring-boot-starter-test',
            'org.springframework:spring-core',
            'org.springframework:spring-context',
            'org.springframework:spring-beans',
            'com.google.guava:guava',
            'org.apache.commons:commons-lang3',
            'commons-io:commons-io',
            'com.fasterxml.jackson.core:jackson-databind',
            'com.google.code.gson:gson',
            'org.slf4j:slf4j-api',
            'ch.qos.logback:logback-classic',
            'junit:junit',
            'org.junit.jupiter:junit-jupiter',
            'org.mockito:mockito-core',
            'org.hibernate:hibernate-core',
            'mysql:mysql-connector-java',
            'org.postgresql:postgresql'
        ]
    }
    
    def __init__(
        self,
        test_config: TestConfig,
        registries_config: RegistriesConfig,
        traffic_config: TrafficConfig,
        package_seeds: Optional[Dict[str, list]] = None,
        pre_fetched_metadata: Optional[Dict[str, list]] = None,
        validation_results: Optional[Dict[str, Dict[str, list]]] = None,
        error_rate: float = 10.0
    ):
        """Initialize K6Manager.
        
        Args:
            test_config: Test configuration (RPS, duration, etc.)
            registries_config: Registry URLs configuration
            traffic_config: Traffic distribution configuration
            package_seeds: Optional custom package seeds for each ecosystem
            pre_fetched_metadata: Optional pre-fetched package metadata (versions, URLs)
            validation_results: Optional validation results with valid/invalid packages
            error_rate: Percentage of requests that should intentionally 404 (default: 10.0)
        """
        self.test_config = test_config
        self.registries_config = registries_config
        self.traffic_config = traffic_config
        
        # Filter package seeds to only selected ecosystems
        all_seeds = package_seeds or self.DEFAULT_PACKAGE_SEEDS
        self.package_seeds = {
            eco: all_seeds[eco] 
            for eco in registries_config.ecosystems 
            if eco in all_seeds
        }
        
        # Store pre-fetched metadata
        self.pre_fetched_metadata = pre_fetched_metadata or {}
        
        # Store validation results and error rate
        self.validation_results = validation_results or {}
        self.error_rate = error_rate
        
        # Calculate VUs based on RPS and timeout duration
        # With 30s timeout, we need: RPS * timeout_seconds to handle blocked VUs
        # We assume average response time of 5s for normal cases, 30s for timeouts
        # Conservative calculation: allocate VUs for 15s average (handles mix of fast + timeout)
        timeout_seconds = 30
        avg_response_time = 15  # Conservative average accounting for timeouts
        
        self.vus = max(test_config.rps * avg_response_time // 2, 50)
        self.max_vus = max(test_config.rps * timeout_seconds, 100)
        
    def generate_script(self, output_path: Optional[str] = None) -> str:
        """Generate k6 load test script from template.
        
        Args:
            output_path: Optional path to save the generated script.
                        If not provided, returns script as string only.
                        
        Returns:
            Generated k6 script content as string.
            
        Raises:
            ValueError: If template rendering fails or validation fails.
        """
        try:
            template = Template(self.K6_SCRIPT_TEMPLATE)
            
            # Prepare template context
            context = {
                'test_id': self.test_config.test_id,
                'target_rps': self.test_config.rps,
                'duration': self.test_config.duration,
                'vus': self.vus,
                'max_vus': self.max_vus,
                'npm_url': self.registries_config.npm_url or '',
                'pypi_url': self.registries_config.pypi_url or '',
                'maven_url': self.registries_config.maven_url or '',
                'cache_hit_pct': self.registries_config.cache_hit_percent,
                'npm_ratio': self.traffic_config.npm_ratio,
                'pypi_ratio': self.traffic_config.pypi_ratio,
                'maven_ratio': self.traffic_config.maven_ratio,
                'metadata_only': 'true' if self.traffic_config.metadata_only else 'false',
                'package_seeds': self.package_seeds,
                'ecosystems': self.registries_config.ecosystems,
                'use_prefetched_metadata': len(self.pre_fetched_metadata) > 0,
                'pre_fetched_metadata': self.pre_fetched_metadata,
                'error_rate': self.error_rate,
                'use_validation': len(self.validation_results) > 0,
                'validation_results': self.validation_results,
                # Authentication credentials
                'npm_token': self.registries_config.npm_token or '',
                'npm_username': self.registries_config.npm_username or '',
                'npm_password': self.registries_config.npm_password or '',
                'pypi_token': self.registries_config.pypi_token or '',
                'pypi_username': self.registries_config.pypi_username or '',
                'pypi_password': self.registries_config.pypi_password or '',
                'maven_username': self.registries_config.maven_username or '',
                'maven_password': self.registries_config.maven_password or '',
            }
            
            # Render template
            script_content = template.render(**context)
            
            # Validate generated script
            self.validate_script(script_content)
            
            # Save to file if path provided
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(script_content, encoding='utf-8')
                
            return script_content
            
        except TemplateError as e:
            raise ValueError(f"Failed to render k6 script template: {e}") from e
            
    def validate_script(self, script_content: str) -> bool:
        """Validate k6 script content.
        
        Args:
            script_content: k6 script content to validate
            
        Returns:
            True if script is valid
            
        Raises:
            ValueError: If script validation fails
        """
        # Basic validation checks
        required_imports = [
            "import http from 'k6/http'",
            "import { check, sleep } from 'k6'",
            "from 'k6/metrics'"
        ]
        
        for required_import in required_imports:
            if required_import not in script_content:
                raise ValueError(f"Missing required import: {required_import}")
                
        # Check for required functions
        required_functions = ['export function setup()', 'export default function']
        for func in required_functions:
            if func not in script_content:
                raise ValueError(f"Missing required function: {func}")
                
        # Check for options export
        if 'export const options' not in script_content:
            raise ValueError("Missing required 'export const options'")
            
        return True
        
    def prepare_environment(self, load_gen_id: str = "gen-1") -> Dict[str, str]:
        """Prepare environment variables for k6 execution.
        
        Args:
            load_gen_id: Load generator identifier
            
        Returns:
            Dictionary of environment variables for k6
        """
        env_vars = {
            'TEST_ID': self.test_config.test_id,
            'LOAD_GEN_ID': load_gen_id,
            'TARGET_RPS': str(self.test_config.rps),
            'DURATION': self.test_config.duration,
            'VUS': str(self.vus),
            'MAX_VUS': str(self.max_vus),
            'CACHE_HIT_PCT': str(self.registries_config.cache_hit_percent),
            'NPM_RATIO': str(self.traffic_config.npm_ratio),
            'PYPI_RATIO': str(self.traffic_config.pypi_ratio),
            'MAVEN_RATIO': str(self.traffic_config.maven_ratio),
            'METADATA_ONLY': 'true' if self.traffic_config.metadata_only else 'false',
        }
        
        # Add only selected ecosystem URLs
        if self.registries_config.npm_url:
            env_vars['NPM_URL'] = self.registries_config.npm_url
        if self.registries_config.pypi_url:
            env_vars['PYPI_URL'] = self.registries_config.pypi_url
        if self.registries_config.maven_url:
            env_vars['MAVEN_URL'] = self.registries_config.maven_url
        
        # Add authentication credentials if provided
        if self.registries_config.npm_token:
            env_vars['NPM_TOKEN'] = self.registries_config.npm_token
        if self.registries_config.npm_username:
            env_vars['NPM_USERNAME'] = self.registries_config.npm_username
        if self.registries_config.npm_password:
            env_vars['NPM_PASSWORD'] = self.registries_config.npm_password
            
        if self.registries_config.pypi_token:
            env_vars['PYPI_TOKEN'] = self.registries_config.pypi_token
        if self.registries_config.pypi_username:
            env_vars['PYPI_USERNAME'] = self.registries_config.pypi_username
        if self.registries_config.pypi_password:
            env_vars['PYPI_PASSWORD'] = self.registries_config.pypi_password
            
        if self.registries_config.maven_username:
            env_vars['MAVEN_USERNAME'] = self.registries_config.maven_username
        if self.registries_config.maven_password:
            env_vars['MAVEN_PASSWORD'] = self.registries_config.maven_password
        
        return env_vars
        
    def get_k6_command(
        self, 
        script_path: str, 
        output_dir: str,
        load_gen_id: str = "gen-1",
        no_docker: bool = False
    ) -> str:
        """Generate k6 command line for execution.
        
        Args:
            script_path: Path to k6 script file
            output_dir: Directory to save results
            load_gen_id: Load generator identifier
            no_docker: If True, run k6 directly on local system without Docker
            
        Returns:
            Complete k6 command as string
        """
        env_vars = self.prepare_environment(load_gen_id)
        
        # Build environment variable exports
        env_exports = ' '.join([f'{k}={v}' for k, v in env_vars.items()])
        
        # Build k6 command with JSON output
        results_file = os.path.join(
            output_dir, 
            f"{self.test_config.test_id}_{load_gen_id}_k6_results.json"
        )
        
        k6_cmd = (
            f"{env_exports} k6 run "
            f"--out json={results_file} "
            f"{script_path}"
        )
        
        return k6_cmd
    
    def execute_k6(
        self,
        script_path: str,
        output_dir: str,
        load_gen_id: str = "gen-1",
        no_docker: bool = False
    ) -> int:
        """Execute k6 load test.
        
        Args:
            script_path: Path to k6 script file
            output_dir: Directory to save results
            load_gen_id: Load generator identifier
            no_docker: If True, run k6 directly on local system without Docker
            
        Returns:
            Exit code from k6 execution
            
        Raises:
            FileNotFoundError: If k6 binary not found when no_docker=True
        """
        import subprocess
        import shutil
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        if no_docker:
            # Check if k6 is available locally
            if not shutil.which('k6'):
                raise FileNotFoundError(
                    "k6 not found in PATH. Install k6 or remove --no-docker flag. "
                    "See https://k6.io/docs/getting-started/installation/"
                )
            
            # Run k6 locally
            env_vars = self.prepare_environment(load_gen_id)
            env = os.environ.copy()
            env.update(env_vars)
            
            results_file = os.path.join(
                output_dir,
                f"{self.test_config.test_id}_{load_gen_id}_k6_results.json"
            )
            
            cmd = [
                'k6', 'run',
                '--out', f'json={results_file}',
                script_path
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            # Print output for visibility
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
                
            return result.returncode
        else:
            # Docker-based execution (existing behavior)
            # This would be implemented by the infrastructure layer
            raise NotImplementedError(
                "Docker-based execution should be handled by infrastructure layer"
            )

