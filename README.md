# Mender Fleet Simulator

Simulador profesional de flota de dispositivos para Mender.io. Este proyecto permite simular cientos de dispositivos IoT de diferentes verticales industriales para pruebas de plataforma.

## Características

- **Persistencia**: Dispositivos almacenados en SQLite con llaves RSA, identidad e inventario
- **Concurrencia**: Arquitectura asyncio para manejar cientos de dispositivos en un solo proceso
- **Multi-industria**: Perfiles configurables para Automotive, Smart Buildings, Medical, Industrial IoT y Retail
- **Simulación realista**:
  - Descarga con tiempo basado en ancho de banda virtual
  - Estados de actualización: Downloading → Installing → Rebooting → Success/Failure
  - Tasa de éxito configurable (80% por defecto)
  - Logs de error realistas
- **Manejo de señales**: Cierre graceful con SIGTERM/SIGINT

## Requisitos

- Python 3.9+
- Cuenta en Mender.io (hosted o self-hosted)

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/your-org/mender-simulator.git
cd mender-simulator
```

### 2. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# o
venv\Scripts\activate  # Windows
```

### 3. Instalar el paquete

```bash
pip install -e .
```

Esto instala el simulador en modo editable junto con todas las dependencias.

### 4. Configurar

```bash
cp config/config.yaml config/config.local.yaml
# Editar config/config.local.yaml con tu tenant_token
```

## Configuración

Edita `config/config.yaml`:

```yaml
server:
  url: "https://hosted.mender.io"
  tenant_token: "TU_TENANT_TOKEN"
  poll_interval: 30

simulator:
  success_rate: 0.8  # 80% de actualizaciones exitosas
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

### Perfiles de Industria

| Industria | Device Type | Identity | Bandwidth | Success Rate |
|-----------|-------------|----------|-----------|--------------|
| Automotive | tcu-4g-lte | mac, vin | 500 KB/s | 80% |
| Smart Buildings | bms-controller-hvac | mac, serial_number | 1000 KB/s | 80% |
| Medical | patient-monitor-icu | mac, serial_number | 2000 KB/s | 95% |
| Industrial IoT | plc-gateway-modbus | mac, serial_number | 250 KB/s | 75% |
| Retail | pos-terminal-emv | mac, pos_sn | 800 KB/s | 80% |

**Nota:** `device_type` es parte del inventory, no del identity.

### Atributos de Inventario

Los atributos de inventario se dividen en **estáticos** (se generan una vez al crear el dispositivo) y **telemetría** (se actualizan en cada ciclo de polling).

#### Atributos Comunes (todos los dispositivos)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| device_id | Estático | Identificador único del dispositivo |
| device_type | Estático | Tipo de dispositivo (de config.yaml) |
| industry | Estático | Vertical industrial |
| artifact_name | Estático | Versión actual del firmware |
| kernel_version | Estático | Versión del kernel |
| firmware_version | Estático | Versión del firmware |
| simulator_version | Estático | Versión del simulador |
| last_seen | Telemetría | Última conexión (ISO 8601) |

#### Automotive (tcu-4g-lte)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| oem_variant | Estático | Variante OEM (standard, premium, sport) |
| odometer_km | Telemetría | Kilómetros recorridos (incrementa) |
| battery_voltage | Telemetría | Voltaje de batería (11.8-14.4V) |
| engine_running | Telemetría | Estado del motor (true/false) |

#### Smart Buildings (bms-controller-hvac)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| zone_type | Estático | Tipo de zona (hvac, lighting, security) |
| floor | Estático | Piso del edificio (1-50) |
| room_count | Estático | Número de habitaciones |
| temperature_c | Telemetría | Temperatura actual (18-26°C) |
| humidity_pct | Telemetría | Humedad relativa (30-70%) |
| hvac_mode | Telemetría | Modo HVAC (cooling, heating, idle, fan) |

#### Medical (patient-monitor-icu)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| fda_device_class | Estático | Clase FDA (II, III) |
| compliance_standards | Estático | Estándares de cumplimiento |
| calibration_due | Estático | Fecha de próxima calibración |
| software_validated | Estático | Software validado (true) |
| patients_monitored | Telemetría | Pacientes monitoreados (0-10) |
| active_alerts | Telemetría | Alertas activas (0-3) |
| cpu_usage_pct | Telemetría | Uso de CPU (10-80%) |

#### Industrial IoT (plc-gateway-modbus)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| plant_id | Estático | ID de planta (PLANT-A, B, C) |
| line | Estático | Línea de producción (L01-L10) |
| unit | Estático | Unidad (U000-U099) |
| supported_protocols | Estático | Protocolos soportados |
| plc_connected | Estático | PLC conectado (true/false) |
| uptime_hours | Telemetría | Horas de uptime (incrementa) |
| cpu_temp_c | Telemetría | Temperatura CPU (35-75°C) |
| messages_per_min | Telemetría | Mensajes por minuto (10-500) |

#### Retail (pos-terminal-emv)

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| region | Estático | Región (NA, EU, APAC, LATAM) |
| store_id | Estático | ID de tienda (1000-9999) |
| payment_modules | Estático | Módulos de pago (chip, nfc, magstripe) |
| receipt_printer | Estático | Impresora conectada (true/false) |
| transactions_today | Telemetría | Transacciones del día (incrementa) |
| last_transaction_mins_ago | Telemetría | Minutos desde última transacción |
| drawer_open | Telemetría | Cajón abierto (true/false) |

## Uso

### Ejecución directa

```bash
# Usando configuración por defecto
python -m mender_simulator

# Especificando archivo de configuración
python -m mender_simulator -c config/config.local.yaml
```

### Como servicio systemd

```bash
# Copiar archivo de servicio
sudo cp mender-simulator.service /etc/systemd/system/

# Crear usuario
sudo useradd -r -s /bin/false mender-simulator

# Crear directorios
sudo mkdir -p /opt/mender-simulator/{data,config}
sudo mkdir -p /var/log/mender-simulator

# Copiar archivos
sudo cp -r src/* /opt/mender-simulator/
sudo cp config/config.yaml /opt/mender-simulator/config/

# Permisos
sudo chown -R mender-simulator:mender-simulator /opt/mender-simulator
sudo chown -R mender-simulator:mender-simulator /var/log/mender-simulator

# Habilitar y arrancar
sudo systemctl daemon-reload
sudo systemctl enable mender-simulator
sudo systemctl start mender-simulator

# Ver logs
sudo journalctl -u mender-simulator -f
```

## Crear Artefactos de Demo

Para probar despliegues, puedes generar artefactos de demo con el script incluido.

### Requisitos

```bash
# Instalar mender-artifact
brew install mender-artifact  # macOS
# O descargar de https://docs.mender.io/downloads
```

### Generar artefactos por industria

```bash
# Solo una industria
./scripts/create-demo-artifacts.sh smart_buildings
./scripts/create-demo-artifacts.sh automotive
./scripts/create-demo-artifacts.sh medical
./scripts/create-demo-artifacts.sh industrial_iot
./scripts/create-demo-artifacts.sh retail

# Todas las industrias
./scripts/create-demo-artifacts.sh all

# Especificar directorio de salida
./scripts/create-demo-artifacts.sh smart_buildings ./my-artifacts
```

Cada industria genera 4 versiones: v1.0.0, v1.1.0, v1.2.0, v2.0.0

### Subir a Mender

```bash
# Con mender-cli
mender-cli artifacts upload ./artifacts/*.mender

# O usar la UI de Mender para subir manualmente
```

## Tests

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=src/mender_simulator

# Tests específicos
pytest tests/test_crypto.py -v
```

## Arquitectura

```
mender-simulator/
├── src/
│   └── mender_simulator/
│       ├── db/              # Persistencia SQLite
│       │   ├── models.py    # Modelos de datos
│       │   └── database.py  # Manager async
│       ├── client/          # Cliente Mender API
│       │   ├── auth.py      # Autenticación
│       │   ├── inventory.py # Inventario
│       │   └── deployments.py # Despliegues
│       ├── simulation/      # Lógica de simulación
│       │   ├── profiles.py  # Perfiles de industria
│       │   └── device_simulator.py
│       ├── utils/           # Utilidades
│       │   ├── crypto.py    # RSA keys
│       │   └── config.py    # Configuración
│       └── main.py          # Orquestador principal
├── tests/                   # Tests unitarios
├── config/                  # Configuración
└── requirements.txt
```

## API de Mender

El simulador interactúa con los siguientes endpoints:

- `POST /api/devices/v1/authentication/auth_requests` - Autenticación
- `PATCH /api/devices/v1/inventory/device/attributes` - Actualizar inventario
- `GET /api/devices/v1/deployments/device/deployments/next` - Verificar despliegues
- `PUT /api/devices/v1/deployments/device/deployments/{id}/status` - Reportar estado
- `PUT /api/devices/v1/deployments/device/deployments/{id}/log` - Enviar logs

## Flujo de Actualización

1. **Polling**: Cada dispositivo consulta el servidor periódicamente
2. **Deployment Check**: Si hay actualización disponible, inicia el proceso
3. **Downloading**: Simula descarga con tiempo basado en tamaño/bandwidth
4. **Installing**: Simula instalación (5-15 segundos)
5. **Rebooting**: Simula reinicio (3-8 segundos)
6. **Success/Failure**: Basado en `success_rate`, reporta éxito o fallo con logs

## Contribuir

1. Fork el repositorio
2. Crea una rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -am 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crea un Pull Request

## Licencia

MIT License - ver LICENSE para más detalles.
