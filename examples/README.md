# Configuration Examples

This directory contains example configuration files for socket-load-test.

## SSH Authentication

The SSH infrastructure supports both **key-based** and **password-based** authentication.

### Key-Based Authentication (Recommended)

```yaml
infrastructure:
  type: ssh
  ssh:
    firewall_server:
      host: 192.168.1.100
      port: 22
      user: admin
      key_file: ~/.ssh/id_rsa  # Path to private key
    load_generators:
      - host: 192.168.1.101
        user: loadgen
        key_file: ~/.ssh/id_rsa
```

**Benefits:**
- More secure than password authentication
- No password stored in config files
- Supports key passphrases
- Standard practice for automated systems

### Password-Based Authentication

```yaml
infrastructure:
  type: ssh
  ssh:
    firewall_server:
      host: 192.168.1.100
      port: 22
      user: admin
      password: ${SFW_PASSWORD}  # Use environment variable
```

**Security Notes:**
- Use environment variables instead of hardcoding passwords
- Consider using key-based auth for production
- Ensure config files have restrictive permissions (600)

### Mixed Authentication

You can use different authentication methods for different servers:

```yaml
infrastructure:
  type: ssh
  ssh:
    firewall_server:
      host: 192.168.1.100
      user: admin
      key_file: ~/.ssh/firewall_key  # Key for firewall
    load_generators:
      - host: 192.168.1.101
        user: loadgen
        key_file: ~/.ssh/id_rsa      # Key for gen1
      - host: 192.168.1.102
        user: loadgen
        password: ${GEN2_PASS}        # Password for gen2
```

## Using Environment Variables

Set environment variables before running:

```bash
export SFW_PASSWORD="your-secure-password"
export LOADGEN_PASSWORD="another-password"
socket-load-test test --config config.yaml
```

## File Locations

- `config-examples.yaml` - Complete configuration examples
- See main README for full configuration reference

## Quick Start

1. Copy an example: `cp examples/config-examples.yaml my-config.yaml`
2. Edit with your settings
3. Set SSH keys or passwords
4. Run: `socket-load-test test --config my-config.yaml --rps 1000 --duration 5m`
