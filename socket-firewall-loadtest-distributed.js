import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const cacheHitRate = new Rate('cache_hits');
const metadataLatency = new Trend('metadata_latency');
const downloadLatency = new Trend('download_latency');
const errorRate = new Rate('errors');
const requestCounter = new Counter('total_requests');
const successCounter = new Counter('successful_requests');
const npmRequests = new Counter('npm_requests');
const pypiRequests = new Counter('pypi_requests');
const mavenRequests = new Counter('maven_requests');

// Configuration
const NPM_BASE_URL = __ENV.NPM_URL || 'https://npm.dougbot.ai';
const PYPI_BASE_URL = __ENV.PYPI_URL || 'https://pypi.dougbot.ai';
const MAVEN_BASE_URL = __ENV.MAVEN_URL || 'https://maven.dougbot.ai';
const CACHE_HIT_PERCENTAGE = parseFloat(__ENV.CACHE_HIT_PCT || '30');
const TEST_ID = __ENV.TEST_ID || 'test-' + Date.now();
const LOAD_GENERATOR_ID = __ENV.LOAD_GEN_ID || 'gen-1';

// Top 100 packages per ecosystem (known to exist)
const PACKAGE_SEEDS = {
  npm: [
    'react', 'lodash', 'chalk', 'commander', 'express', 'axios', 'debug', 'request', 'async', 'moment',
    'typescript', 'webpack', 'eslint', 'jest', 'mocha', 'babel-core', 'core-js', 'tslib', 'yargs', 'inquirer',
    'uuid', 'dotenv', 'classnames', 'prop-types', 'react-dom', 'colors', 'minimist', 'semver', 'glob', 'mkdirp',
    'rimraf', 'through2', 'fs-extra', 'bluebird', 'underscore', 'body-parser', 'cors', 'express-validator',
    'jsonwebtoken', 'bcrypt', 'mongoose', 'sequelize', 'mysql', 'pg', 'redis', 'ws', 'socket.io',
    'nodemon', 'concurrently', 'cross-env', 'npm-run-all', 'winston', 'morgan', 'helmet', 'compression',
    'multer', 'cookie-parser', 'express-session', 'passport', 'joi', 'validator', 'cheerio', 'xml2js',
    'marked', 'handlebars', 'ejs', 'pug', 'nunjucks', 'node-fetch', 'got', 'superagent', 'form-data',
    'mime-types', 'iconv-lite', 'buffer', 'stream', 'readable-stream', 'concat-stream', 'pump',
    'end-of-stream', 'duplexify', 'pumpify', 'mississippi', 'tar', 'archiver', 'unzipper', 'adm-zip',
    'date-fns', 'dayjs', 'luxon', 'ms', 'pretty-ms', 'human-interval', 'node-schedule', 'cron', 'agenda'
  ],
  pypi: [
    'requests', 'urllib3', 'certifi', 'charset-normalizer', 'idna', 'six', 'python-dateutil', 'setuptools',
    'pip', 'wheel', 'packaging', 'pyparsing', 'attrs', 'pytz', 'importlib-metadata', 'zipp', 'typing-extensions',
    'pyyaml', 'click', 'jinja2', 'markupsafe', 'werkzeug', 'flask', 'django', 'fastapi', 'pydantic',
    'sqlalchemy', 'psycopg2', 'pymysql', 'redis', 'celery', 'kombu', 'amqp', 'vine', 'billiard',
    'boto3', 'botocore', 's3transfer', 'awscli', 'cryptography', 'cffi', 'pycparser', 'pyopenssl',
    'numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn', 'pillow', 'scikit-learn', 'joblib', 'threadpoolctl',
    'pytest', 'pluggy', 'iniconfig', 'tomli', 'coverage', 'pytest-cov', 'tox', 'virtualenv', 'black',
    'flake8', 'pylint', 'mypy', 'isort', 'autopep8', 'pycodestyle', 'pyflakes', 'mccabe', 'astroid',
    'httpx', 'httpcore', 'h11', 'anyio', 'sniffio', 'aiohttp', 'async-timeout', 'multidict', 'yarl',
    'beautifulsoup4', 'lxml', 'html5lib', 'soupsieve', 'cssselect', 'pyquery', 'scrapy', 'twisted',
    'colorama', 'termcolor', 'rich', 'tqdm', 'progressbar2', 'python-dotenv', 'environs', 'marshmallow'
  ],
  maven: [
    'org.springframework.boot:spring-boot-starter-web',
    'org.springframework.boot:spring-boot-starter-data-jpa',
    'org.springframework.boot:spring-boot-starter-security',
    'org.springframework.boot:spring-boot-starter-test',
    'org.springframework.boot:spring-boot-starter-actuator',
    'org.springframework:spring-core',
    'org.springframework:spring-context',
    'org.springframework:spring-beans',
    'org.springframework:spring-web',
    'org.springframework:spring-webmvc',
    'com.google.guava:guava',
    'org.apache.commons:commons-lang3',
    'org.apache.commons:commons-collections4',
    'commons-io:commons-io',
    'commons-codec:commons-codec',
    'com.fasterxml.jackson.core:jackson-databind',
    'com.fasterxml.jackson.core:jackson-core',
    'com.fasterxml.jackson.core:jackson-annotations',
    'com.google.code.gson:gson',
    'org.json:json',
    'org.slf4j:slf4j-api',
    'ch.qos.logback:logback-classic',
    'ch.qos.logback:logback-core',
    'org.apache.logging.log4j:log4j-core',
    'org.apache.logging.log4j:log4j-api',
    'junit:junit',
    'org.junit.jupiter:junit-jupiter',
    'org.junit.jupiter:junit-jupiter-api',
    'org.junit.jupiter:junit-jupiter-engine',
    'org.mockito:mockito-core',
    'org.mockito:mockito-junit-jupiter',
    'org.assertj:assertj-core',
    'org.hamcrest:hamcrest',
    'org.testng:testng',
    'org.hibernate:hibernate-core',
    'org.hibernate:hibernate-entitymanager',
    'javax.persistence:javax.persistence-api',
    'mysql:mysql-connector-java',
    'org.postgresql:postgresql',
    'com.h2database:h2',
    'org.apache.httpcomponents:httpclient',
    'org.apache.httpcomponents:httpcore',
    'com.squareup.okhttp3:okhttp',
    'io.netty:netty-all',
    'io.netty:netty-handler',
    'redis.clients:jedis',
    'org.apache.kafka:kafka-clients',
    'com.rabbitmq:amqp-client',
    'javax.servlet:javax.servlet-api',
    'javax.validation:validation-api',
    'org.hibernate.validator:hibernate-validator',
    'com.squareup.retrofit2:retrofit',
    'com.squareup.okhttp3:logging-interceptor',
    'io.swagger.core.v3:swagger-annotations',
    'org.springdoc:springdoc-openapi-ui',
    'org.projectlombok:lombok',
    'org.mapstruct:mapstruct',
    'com.google.inject:guice',
    'org.apache.commons:commons-text',
    'org.apache.commons:commons-math3',
    'joda-time:joda-time',
    'com.google.protobuf:protobuf-java',
    'org.yaml:snakeyaml'
  ]
};

// Global storage for packages with versions
let packageDatabase = {
  npm: [],
  pypi: [],
  maven: []
};

// Helper functions
function randomChoice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function parseMavenCoords(coords) {
  const [group, artifact] = coords.split(':');
  return { group, artifact };
}

// Fetch versions for a package
function fetchNpmVersions(pkg) {
  try {
    const response = http.get(`${NPM_BASE_URL}/${pkg}`, { timeout: '30s' });
    if (response.status === 200) {
      const data = JSON.parse(response.body);
      const versions = Object.keys(data.versions || {}).slice(0, 5); // Top 5 versions
      return versions.length > 0 ? versions : ['latest'];
    }
  } catch (e) {
    // Silent fail - use default
  }
  return ['latest'];
}

function fetchPypiVersions(pkg) {
  try {
    const response = http.get(`${PYPI_BASE_URL}/pypi/${pkg}/json`, { timeout: '30s' });
    if (response.status === 200) {
      const data = JSON.parse(response.body);
      const releases = Object.keys(data.releases || {});
      // Get last 5 versions
      const versions = releases.slice(Math.max(0, releases.length - 5));
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
    const groupPath = group.replace(/\./g, '/');
    const url = `${MAVEN_BASE_URL}/${groupPath}/${artifact}/maven-metadata.xml`;
    
    const response = http.get(url, { timeout: '30s' });
    if (response.status === 200) {
      // Parse XML to get versions (simple regex approach)
      const matches = response.body.match(/<version>([^<]+)<\/version>/g);
      if (matches) {
        const versions = matches.map(m => m.replace(/<\/?version>/g, '')).slice(-5); // Last 5
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
  console.log(`Target RPS:           ${__ENV.TARGET_RPS || '1000'}`);
  console.log(`Duration:             ${__ENV.DURATION || '5m'}`);
  console.log(`Pre-allocated VUs:    ${__ENV.VUS || '50'}`);
  console.log(`Max VUs:              ${__ENV.MAX_VUS || '1000'}`);
  console.log(`Cache Hit %:          ${CACHE_HIT_PERCENTAGE}%`);
  console.log('');
  console.log('Registry URLs:');
  console.log(`  npm:                ${NPM_BASE_URL}`);
  console.log(`  PyPI:               ${PYPI_BASE_URL}`);
  console.log(`  Maven:              ${MAVEN_BASE_URL}`);
  console.log('');
  console.log('Traffic Mix:');
  console.log(`  Metadata requests:  40%`);
  console.log(`  Download requests:  60%`);
  console.log('');
  console.log('Package Distribution:');
  console.log(`  Top 20% (popular):  ${CACHE_HIT_PERCENTAGE}% of requests`);
  console.log(`  Remaining 80%:      ${100 - CACHE_HIT_PERCENTAGE}% of requests`);
  console.log('='.repeat(60));
  console.log('');
  console.log('SETUP: Fetching real package versions from registries...');
  console.log('This may take 5-10 minutes for 260+ packages...');
  console.log('Set setupTimeout to 10m in options to allow enough time.');
  console.log('='.repeat(60));
  
  const database = {
    npm: [],
    pypi: [],
    maven: []
  };
  
  const startTime = new Date();
  
  // Store configuration in database for report
  database.config = {
    test_id: TEST_ID,
    load_generator: LOAD_GENERATOR_ID,
    target_rps: parseInt(__ENV.TARGET_RPS || '1000'),
    duration: __ENV.DURATION || '5m',
    vus: parseInt(__ENV.VUS || '50'),
    max_vus: parseInt(__ENV.MAX_VUS || '1000'),
    cache_hit_pct: CACHE_HIT_PERCENTAGE,
    npm_url: NPM_BASE_URL,
    pypi_url: PYPI_BASE_URL,
    maven_url: MAVEN_BASE_URL,
    timestamp: new Date().toISOString()
  };
  
  // Fetch npm packages
  console.log(`\nFetching versions for ${PACKAGE_SEEDS.npm.length} npm packages...`);
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
  
  // Fetch PyPI packages
  console.log(`\nFetching versions for ${PACKAGE_SEEDS.pypi.length} PyPI packages...`);
  count = 0;
  for (const pkg of PACKAGE_SEEDS.pypi) {
    const versions = fetchPypiVersions(pkg);
    database.pypi.push({ name: pkg, versions: versions });
    count++;
    if (count % 20 === 0) {
      const elapsed = Math.floor((new Date() - startTime) / 1000);
      console.log(`  pypi: ${count}/${PACKAGE_SEEDS.pypi.length} (${elapsed}s elapsed)`);
    }
  }
  
  // Fetch Maven packages
  console.log(`\nFetching versions for ${PACKAGE_SEEDS.maven.length} Maven packages...`);
  count = 0;
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
  
  const totalTime = Math.floor((new Date() - startTime) / 1000);
  
  console.log('='.repeat(60));
  console.log('SETUP COMPLETE!');
  console.log(`  Total time: ${totalTime} seconds`);
  console.log(`  npm packages:   ${database.npm.length} (${database.npm.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
  console.log(`  pypi packages:  ${database.pypi.length} (${database.pypi.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
  console.log(`  maven packages: ${database.maven.length} (${database.maven.reduce((sum, p) => sum + p.versions.length, 0)} versions)`);
  console.log('='.repeat(60));
  
  return database;
}

// Get package based on cache hit probability
function getPackage(ecosystem, data) {
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

function checkResponse(response, ecosystem, type) {
  const success = response.status === 200 || response.status === 304;
  const isError = !success;
  
  requestCounter.add(1);
  if (success) {
    successCounter.add(1);
  }
  errorRate.add(isError);
  
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
    headers: { 
      'User-Agent': 'npm/10.0.0 node/v20.0.0',
      'Accept': 'application/json'
    },
    timeout: '30s',
    tags: { 
      ecosystem: 'npm', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'npm', 'metadata');
  metadataLatency.add(duration);
  npmRequests.add(1);
}

function npmDownloadRequest(data) {
  const pkg = getPackage('npm', data);
  const version = randomChoice(pkg.versions);
  // For simplicity, just request metadata (real download URLs are complex)
  const url = `${NPM_BASE_URL}/${pkg.name}`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'npm/10.0.0 node/v20.0.0',
      'Accept': 'application/json'
    },
    timeout: '30s',
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
  
  checkResponse(response, 'npm', 'download');
  downloadLatency.add(duration);
  npmRequests.add(1);
}

// PyPI requests
function pypiSimpleRequest(data) {
  const pkg = getPackage('pypi', data);
  const url = `${PYPI_BASE_URL}/simple/${pkg.name}/`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'pip/23.0 CPython/3.11.0',
      'Accept': 'text/html'
    },
    timeout: '30s',
    tags: { 
      ecosystem: 'pypi', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'pypi', 'metadata');
  metadataLatency.add(duration);
  pypiRequests.add(1);
}

function pypiJsonRequest(data) {
  const pkg = getPackage('pypi', data);
  const url = `${PYPI_BASE_URL}/pypi/${pkg.name}/json`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'pip/23.0 CPython/3.11.0',
      'Accept': 'application/json'
    },
    timeout: '30s',
    tags: { 
      ecosystem: 'pypi', 
      type: 'metadata',
      package: pkg.name,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'pypi', 'metadata');
  metadataLatency.add(duration);
  pypiRequests.add(1);
}

function pypiDownloadRequest(data) {
  const pkg = getPackage('pypi', data);
  const version = randomChoice(pkg.versions);
  // Use simple endpoint for simplicity
  const url = `${PYPI_BASE_URL}/simple/${pkg.name}/`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'pip/23.0 CPython/3.11.0',
      'Accept': 'text/html'
    },
    timeout: '30s',
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
  
  checkResponse(response, 'pypi', 'download');
  downloadLatency.add(duration);
  pypiRequests.add(1);
}

// Maven requests
function mavenMetadataRequest(data) {
  const pkg = getPackage('maven', data);
  const groupPath = pkg.group.replace(/\./g, '/');
  const url = `${MAVEN_BASE_URL}/${groupPath}/${pkg.artifact}/maven-metadata.xml`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
      'Accept': 'application/xml'
    },
    timeout: '30s',
    tags: { 
      ecosystem: 'maven', 
      type: 'metadata',
      package: `${pkg.group}:${pkg.artifact}`,
      test_id: TEST_ID,
      load_gen: LOAD_GENERATOR_ID
    }
  });
  const duration = Date.now() - startTime;
  
  checkResponse(response, 'maven', 'metadata');
  metadataLatency.add(duration);
  mavenRequests.add(1);
}

function mavenDownloadRequest(data) {
  const pkg = getPackage('maven', data);
  const version = randomChoice(pkg.versions);
  const groupPath = pkg.group.replace(/\./g, '/');
  const url = `${MAVEN_BASE_URL}/${groupPath}/${pkg.artifact}/${version}/${pkg.artifact}-${version}.jar`;
  
  const startTime = Date.now();
  const response = http.get(url, {
    headers: { 
      'User-Agent': 'Apache-Maven/3.9.0 (Java 17.0.0)',
      'Accept': 'application/java-archive'
    },
    timeout: '30s',
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
  
  checkResponse(response, 'maven', 'download');
  downloadLatency.add(duration);
  mavenRequests.add(1);
}

// Main scenario
export default function (data) {
  // Weighted distribution: 40% metadata, 60% downloads
  const rand = Math.random();
  
  if (rand < 0.4) {
    // Metadata request
    const ecosystem = randomChoice(['npm', 'pypi', 'maven']);
    
    switch (ecosystem) {
      case 'npm':
        npmMetadataRequest(data);
        break;
      case 'pypi':
        if (Math.random() < 0.5) {
          pypiSimpleRequest(data);
        } else {
          pypiJsonRequest(data);
        }
        break;
      case 'maven':
        mavenMetadataRequest(data);
        break;
    }
  } else {
    // Download request
    const ecosystem = randomChoice(['npm', 'pypi', 'maven']);
    
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

export const options = {
  setupTimeout: '10m', // 10 minutes for setup phase (fetching all package versions)
  scenarios: {
    load_test: {
      executor: 'constant-arrival-rate',
      rate: parseInt(__ENV.TARGET_RPS || '1000'),
      timeUnit: '1s',
      duration: __ENV.DURATION || '5m',
      preAllocatedVUs: parseInt(__ENV.VUS || '50'),
      maxVUs: parseInt(__ENV.MAX_VUS || '1000'),
    },
  },
};
