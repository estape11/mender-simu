# Mender Fleet Simulator

Professional device fleet simulator for Mender.io. This project allows simulating hundreds of IoT devices from different industrial verticals for platform testing.

## Features

- **Persistence**: Devices stored in SQLite with RSA keys, identity, and inventory
- **Concurrency**: asyncio architecture to handle hundreds of devices in a single process
- **Multi-industry**: Configurable profiles for Automotive, Smart Buildings, Medical, Industrial IoT, and Retail
- **Realistic simulation**:
  - Download time based on virtual bandwidth
  - Update states: Downloading → Installing → Rebooting → Success/Failure
  - Configurable success rate (80% by default)
  - Realistic error logs
- **Signal handling**: Graceful shutdown with SIGTERM/SIGINT

## Requirements

- Python 3.9+
- Mender.io account (hosted or self-hosted)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-org/mender-simulator.git
cd mender-simulator
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

### 3. Install the package

```bash
pip install -e .
```

This installs the simulator in editable mode along with all dependencies.

### 4. Configure

```bash
cp config/config.yaml config/config.local.yaml
# Edit config/config.local.yaml with your tenant_token
```

## Configuration

Edit `config/config.yaml`:

```yaml
server:
  url: "https://hosted.mender.io"
  tenant_token: "YOUR_TENANT_TOKEN"
  poll_interval: 30

simulator:
  success_rate: 0.8  # 80% of successful updates
  log_file: "simulator.log"
  log_level: "INFO"
  database_path: "devices.db"

industries:
  automotive:
    enabled: true
    count: 10
    bandwidth_kbps: 500
    # ...
```

### Industry Profiles

| Industry | Device Type | Identity | Bandwidth |
|----------|-------------|----------|-----------|
| Automotive | tcu-4g-lte | mac, vin | 500 KB/s |
| Smart Buildings | bms-controller-hvac | mac, serial_number | 1000 KB/s |
| Medical | patient-monitor-icu | mac, serial_number | 2000 KB/s |
| Industrial IoT | plc-gateway-modbus | mac, serial_number | 250 KB/s |
| Retail | pos-terminal-emv | mac, pos_sn | 800 KB/s |
| EV Charging | ev-charger-ocpp-2.0 | mac, evse_id | 1000 KB/s |

**Notes:**
- `device_type` is part of the inventory, not the identity
- `success_rate` in config.yaml controls the global success rate (0.8 = 80%)

### Inventory Attributes

Inventory attributes are primarily **static** and represent device state, not real-time telemetry.

> **Note:** Mender is NOT a real-time telemetry system. Inventory attributes are updated during polling (every 30-60 seconds) and represent device information, not sensor metrics.

#### Common Attributes (all devices)

| Attribute | Description |
|-----------|-------------|
| device_id | Unique device identifier |
| device_type | Device type (from config.yaml) |
| industry | Industrial vertical |
| artifact_name | Artifact name (format: `{device_type}-{version}`) |
| rootfs-image.version | rootfs version (same as artifact_name) |
| kernel_version | Kernel version |
| firmware_version | Firmware version |
| simulator_version | Simulator version |
| last_seen | Last connection (ISO 8601) |

#### Automotive (tcu-4g-lte)

| Attribute | Description |
|-----------|-------------|
| oem_variant | OEM variant (standard, premium, sport) |
| odometer_km | Kilometers driven |

#### Smart Buildings (bms-controller-hvac)

| Attribute | Description |
|-----------|-------------|
| zone_type | Zone type (hvac, lighting, security) |
| floor | Building floor (1-50) |
| room_count | Number of rooms |
| hvac_mode | HVAC mode (cooling, heating, idle, auto) |

#### Medical (patient-monitor-icu)

| Attribute | Description |
|-----------|-------------|
| fda_device_class | FDA class (II, III) |
| compliance_standards | Compliance standards |
| calibration_due | Next calibration date |
| software_validated | Software validated (true) |

#### Industrial IoT (plc-gateway-modbus)

| Attribute | Description |
|-----------|-------------|
| plant_id | Plant ID (PLANT-A, B, C) |
| line | Production line (L01-L10) |
| unit | Unit (U000-U099) |
| supported_protocols | Supported protocols |
| plc_connected | PLC connected (true/false) |
| uptime_hours | Uptime hours since last reboot |

#### Retail (pos-terminal-emv)

| Attribute | Description |
|-----------|-------------|
| region | Region (NA, EU, APAC, LATAM) |
| store_id | Store ID (1000-9999) |
| payment_modules | Payment modules (chip, nfc, magstripe) |
| receipt_printer | Printer connected (true/false) |

#### EV Charging (ev-charger-ocpp-2.0)

| Attribute | Description |
|-----------|-------------|
| evse_id | EVSE identifier (EVC-{network}-{station}-{port}) |
| charger_type | Charger type (ac-level2-7kW, dc-fast-50kW) |
| supported_protocols | Supported protocols (ocpp-2.0.1) |
| connector_type | Connector type (ccs2, type2) |
| max_power_kw | Maximum power output in kW |
| location_type | Location (highway, urban, shopping-center, workplace, residential) |
| sessions_total | Total charging sessions completed |
| charger_status | Current status (available, charging, faulted) |

## Usage

### Direct execution

```bash
# Using default configuration
python -m mender-simulator

# Specifying a configuration file
python -m mender-simulator -c config/config.local.yaml
```

### Signals

| Signal | Command | Description |
|--------|---------|-------------|
| SIGINT | `Ctrl+C` | Stop the simulator (graceful shutdown) |
| SIGTERM | `kill <pid>` | Stop the simulator (graceful shutdown) |
| SIGUSR1 | `kill -USR1 <pid>` | Force immediate poll (inventory + check updates) |

**Example: Force immediate poll**
```bash
# Get the simulator PID
pgrep -f mender_simulator

# Force immediate poll
kill -USR1 <pid>
```

### As a systemd service

```bash
# Copy service file
sudo cp mender-simulator.service /etc/systemd/system/

# Create user
sudo useradd -r -s /bin/false mender-simulator

# Create directories
sudo mkdir -p /opt/mender-simulator/{data,config}
sudo mkdir -p /var/log/mender-simulator

# Copy files
sudo cp -r src/* /opt/mender-simulator/
sudo cp config/config.yaml /opt/mender-simulator/config/

# Permissions
sudo chown -R mender-simulator:mender-simulator /opt/mender-simulator
sudo chown -R mender-simulator:mender-simulator /var/log/mender-simulator

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mender-simulator
sudo systemctl start mender-simulator

# View logs
sudo journalctl -u mender-simulator -f
```

## Create Demo Artifacts

To test deployments, you can generate demo artifacts with the included script.

### Requirements

```bash
# Install mender-artifact
brew install mender-artifact  # macOS
# Or download from https://docs.mender.io/downloads
```

### Generate artifacts by industry

```bash
# Single industry
./scripts/create-demo-artifacts.sh smart_buildings
./scripts/create-demo-artifacts.sh automotive
./scripts/create-demo-artifacts.sh medical
./scripts/create-demo-artifacts.sh industrial_iot
./scripts/create-demo-artifacts.sh retail

# All industries
./scripts/create-demo-artifacts.sh all

# Specify output directory
./scripts/create-demo-artifacts.sh smart_buildings ./my-artifacts
```

Each industry generates 4 versions: v1.0.0, v1.1.0, v1.2.0, v2.0.0

### Upload to Mender

```bash
# With mender-cli
mender-cli artifacts upload ./artifacts/*.mender

# Or use the Mender UI to upload manually
```

## Cleanup / Decommission Devices

Script to list and delete devices from Mender.

### Requirements

Obtain a Personal Access Token (PAT) from Mender:
1. Go to Mender UI → Settings → Access Tokens
2. Create a new token
3. Export as an environment variable

```bash
export MENDER_PAT='your-personal-access-token'
```

### List devices

```bash
./scripts/cleanup-devices.sh list              # All
./scripts/cleanup-devices.sh list-pending      # Pending
./scripts/cleanup-devices.sh list-accepted     # Accepted
./scripts/cleanup-devices.sh list-rejected     # Rejected
./scripts/cleanup-devices.sh list-noauth       # Unauthorized
```

### Decommission devices

```bash
./scripts/cleanup-devices.sh decommission-pending   # Pending only
./scripts/cleanup-devices.sh decommission-accepted  # Accepted only
./scripts/cleanup-devices.sh decommission-rejected  # Rejected only
./scripts/cleanup-devices.sh decommission-noauth    # Noauth only
./scripts/cleanup-devices.sh decommission-all       # ALL (be careful!)
```

### Clean local data

```bash
# Deletes devices.db and simulator.log
./scripts/cleanup-devices.sh cleanup-local
```

## Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src/mender_simulator

# Specific tests
pytest tests/test_crypto.py -v
```

## Architecture

```
mender-simulator/
├── src/
│   └── mender_simulator/
│       ├── db/              # SQLite persistence
│       │   ├── models.py    # Data models
│       │   └── database.py  # Async manager
│       ├── client/          # Mender API client
│       │   ├── auth.py      # Authentication
│       │   ├── inventory.py # Inventory
│       │   └── deployments.py # Deployments
│       ├── simulation/      # Simulation logic
│       │   ├── profiles.py  # Industry profiles
│       │   └── device_simulator.py
│       ├── utils/           # Utilities
│       │   ├── crypto.py    # RSA keys
│       │   └── config.py    # Configuration
│       └── main.py          # Main orchestrator
├── tests/                   # Unit tests
├── config/                  # Configuration
└── requirements.txt
```

## Mender API

The simulator interacts with the following endpoints:

- `POST /api/devices/v1/authentication/auth_requests` - Authentication
- `PATCH /api/devices/v1/inventory/device/attributes` - Update inventory
- `GET /api/devices/v1/deployments/device/deployments/next` - Check deployments
- `PUT /api/devices/v1/deployments/device/deployments/{id}/status` - Report status
- `PUT /api/devices/v1/deployments/device/deployments/{id}/log` - Send logs

## Update Flow

1. **Polling**: Each device queries the server periodically
2. **Deployment Check**: If an update is available, starts the process
3. **Downloading**: Simulates download with time based on size/bandwidth
4. **Installing**: Simulates installation (5-15 seconds)
5. **Rebooting**: Simulates reboot (3-8 seconds)
6. **Success/Failure**: Based on `success_rate`, reports success or failure with logs

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## License

MIT License - see LICENSE for more details.
