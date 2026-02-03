#!/bin/bash

# Socket Firewall System Monitoring Setup
# Install this on your Socket Firewall server to enable CPU/Memory monitoring during load tests

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "Socket Firewall Monitoring Setup"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}Error: This script must be run as root${NC}"
  echo "Run: sudo $0"
  exit 1
fi

# Install Prometheus Node Exporter
install_node_exporter() {
  echo "Installing Prometheus Node Exporter..."
  
  # Download latest node_exporter
  NODE_EXPORTER_VERSION="1.7.0"
  cd /tmp
  wget -q https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
  tar xzf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
  
  # Install binary
  cp node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/
  chmod +x /usr/local/bin/node_exporter
  
  # Clean up
  rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64*
  
  echo -e "${GREEN}✓ Node Exporter installed${NC}"
}

# Create systemd service
create_systemd_service() {
  echo "Creating systemd service..."
  
  cat > /etc/systemd/system/node_exporter.service <<EOF
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/node_exporter \\
  --web.listen-address=:9100 \\
  --collector.cpu \\
  --collector.meminfo \\
  --collector.loadavg \\
  --collector.diskstats \\
  --collector.netdev \\
  --collector.filesystem \\
  --no-collector.arp \\
  --no-collector.bcache \\
  --no-collector.bonding \\
  --no-collector.btrfs \\
  --no-collector.conntrack \\
  --no-collector.edac \\
  --no-collector.entropy \\
  --no-collector.fibrechannel \\
  --no-collector.hwmon \\
  --no-collector.infiniband \\
  --no-collector.ipvs \\
  --no-collector.mdadm \\
  --no-collector.nfs \\
  --no-collector.nfsd \\
  --no-collector.nvme \\
  --no-collector.powersupplyclass \\
  --no-collector.pressure \\
  --no-collector.rapl \\
  --no-collector.schedstat \\
  --no-collector.sockstat \\
  --no-collector.softnet \\
  --no-collector.stat \\
  --no-collector.tapestats \\
  --no-collector.textfile \\
  --no-collector.thermal_zone \\
  --no-collector.time \\
  --no-collector.timex \\
  --no-collector.udp_queues \\
  --no-collector.uname \\
  --no-collector.vmstat \\
  --no-collector.xfs \\
  --no-collector.zfs

SyslogIdentifier=node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable node_exporter
  systemctl start node_exporter
  
  echo -e "${GREEN}✓ Systemd service created and started${NC}"
}

# Configure firewall
configure_firewall() {
  echo "Configuring firewall..."
  
  # Check if ufw is installed
  if command -v ufw &> /dev/null; then
    ufw allow 9100/tcp comment 'Node Exporter'
    echo -e "${GREEN}✓ UFW rule added${NC}"
  elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=9100/tcp
    firewall-cmd --reload
    echo -e "${GREEN}✓ Firewalld rule added${NC}"
  else
    echo -e "${YELLOW}⚠ No firewall detected. Make sure port 9100 is accessible.${NC}"
  fi
}

# Verify installation
verify_installation() {
  echo ""
  echo "Verifying installation..."
  
  if systemctl is-active --quiet node_exporter; then
    echo -e "${GREEN}✓ Node Exporter is running${NC}"
  else
    echo -e "${RED}✗ Node Exporter is not running${NC}"
    exit 1
  fi
  
  # Test metrics endpoint
  sleep 2
  if curl -s http://localhost:9100/metrics | grep -q "node_cpu"; then
    echo -e "${GREEN}✓ Metrics endpoint is responding${NC}"
  else
    echo -e "${RED}✗ Metrics endpoint is not responding${NC}"
    exit 1
  fi
}

# Main installation
main() {
  echo "This script will install Prometheus Node Exporter for system monitoring."
  echo ""
  read -p "Continue? (y/n) " -n 1 -r
  echo
  
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
  fi
  
  echo ""
  
  # Check if already installed
  if systemctl is-active --quiet node_exporter; then
    echo -e "${YELLOW}Node Exporter is already running${NC}"
    read -p "Reinstall? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      systemctl stop node_exporter
      systemctl disable node_exporter
    else
      echo "Keeping existing installation."
      exit 0
    fi
  fi
  
  install_node_exporter
  create_systemd_service
  configure_firewall
  verify_installation
  
  echo ""
  echo "========================================"
  echo -e "${GREEN}Installation Complete!${NC}"
  echo "========================================"
  echo ""
  echo "Node Exporter is now running on port 9100"
  echo ""
  echo "Test it with:"
  echo "  curl http://$(hostname -I | awk '{print $1}'):9100/metrics"
  echo ""
  echo "Useful commands:"
  echo "  systemctl status node_exporter    # Check status"
  echo "  systemctl stop node_exporter      # Stop service"
  echo "  systemctl start node_exporter     # Start service"
  echo "  journalctl -u node_exporter -f    # View logs"
  echo ""
}

main
