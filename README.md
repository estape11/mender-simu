# Mender Fleet Simulator

Simulador profesional de flota de dispositivos para Mender.io. Este proyecto permite simular cientos de dispositivos IoT de diferentes verticales industriales para pruebas de plataforma.

## Características

- **Persistencia**: Dispositivos almacenados en SQLite con llaves RSA, identidad e inventario
- **Concurrencia**: Arquitectura asyncio para manejar cientos de dispositivos en un solo proceso
- **Multi-industria**: Perfiles configurables para Automotive, Smart Buildings, Medical, Industrial IoT, Retail, EV Charging y flotas UAS
- **Systems (Mender Orchestrator)**: dispositivos tier `system` que agrupan componentes (con su bus físico) y procesan deployments de Manifests con updates ordenados, skip de componentes en target y rollback coordinado
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

| Industria | Device Type | Identity | Bandwidth |
|-----------|-------------|----------|-----------|
| Automotive | tcu-4g-lte | mac, vin | 500 KB/s |
| Smart Buildings | bms-controller-hvac | mac, serial_number | 1000 KB/s |
| Medical | patient-monitor-icu | mac, serial_number | 2000 KB/s |
| Industrial IoT | plc-gateway-modbus | mac, serial_number | 250 KB/s |
| Retail | pos-terminal-emv | mac, pos_sn | 800 KB/s |
| EV Charging | ev-charger-ocpp-2.0 | mac, evse_id | 1000 KB/s |
| UAS Airframe | quad-x | mac, tail_number | 400 KB/s |
| UAS GCS | gcs | mac, station_id | 5000 KB/s |

**Perfiles System (Mender Orchestrator)** — ver la sección [Systems](#systems-mender-orchestrator):

| Industria | System Type | Componentes | Identity |
|-----------|-------------|-------------|----------|
| system_core | system-core | gateway + 2 rtos | mac, system_id |
| grid_site | grid-monitoring-site | edge-gateway + 3 line-sensors + meteo | mac, site_id |
| ev_vehicle | ev-platform | VCU + BMS + 2 inversores + ADAS | mac, vin |
| charging_hub | ev-charging-hub | site controller + 4 charge points + potencia | mac, hub_id |

**Notas:**
- `device_type` es parte del inventory, no del identity
- `success_rate` en config.yaml controla la tasa de éxito global (0.8 = 80%);
  en perfiles system aplica **por componente**

### Atributos de Inventario

Los atributos de inventario son principalmente **estáticos** y representan el estado del dispositivo, no telemetría en tiempo real.

> **Nota:** Mender NO es un sistema de telemetría en tiempo real. Los atributos de inventario se actualizan durante el polling (cada 30-60 segundos) y representan información del dispositivo, no métricas de sensores.

#### Atributos Comunes (todos los dispositivos)

| Atributo | Descripción |
|----------|-------------|
| device_id | Identificador único del dispositivo |
| device_type | Tipo de dispositivo (de config.yaml) |
| industry | Vertical industrial |
| artifact_name | Nombre del artefacto (formato: `{device_type}-{version}`) |
| rootfs-image.version | Versión del rootfs (igual que artifact_name) |
| kernel_version | Versión del kernel |
| firmware_version | Versión del firmware |
| simulator_version | Versión del simulador |
| last_seen | Última conexión (ISO 8601) |

#### Automotive (tcu-4g-lte)

| Atributo | Descripción |
|----------|-------------|
| oem_variant | Variante OEM (standard, premium, sport) |
| odometer_km | Kilómetros recorridos |

#### Smart Buildings (bms-controller-hvac)

| Atributo | Descripción |
|----------|-------------|
| zone_type | Tipo de zona (hvac, lighting, security) |
| floor | Piso del edificio (1-50) |
| room_count | Número de habitaciones |
| hvac_mode | Modo HVAC (cooling, heating, idle, auto) |

#### Medical (patient-monitor-icu)

| Atributo | Descripción |
|----------|-------------|
| fda_device_class | Clase FDA (II, III) |
| compliance_standards | Estándares de cumplimiento |
| calibration_due | Fecha de próxima calibración |
| software_validated | Software validado (true) |

#### Industrial IoT (plc-gateway-modbus)

| Atributo | Descripción |
|----------|-------------|
| plant_id | ID de planta (PLANT-A, B, C) |
| line | Línea de producción (L01-L10) |
| unit | Unidad (U000-U099) |
| supported_protocols | Protocolos soportados |
| plc_connected | PLC conectado (true/false) |
| uptime_hours | Horas de uptime desde último reinicio |

#### Retail (pos-terminal-emv)

| Atributo | Descripción |
|----------|-------------|
| region | Región (NA, EU, APAC, LATAM) |
| store_id | ID de tienda (1000-9999) |
| payment_modules | Módulos de pago (chip, nfc, magstripe) |
| receipt_printer | Impresora conectada (true/false) |

## Uso

### Ejecución directa

```bash
# Usando configuración por defecto
python -m mender_simulator

# Especificando archivo de configuración
python -m mender_simulator -c config/config.local.yaml
```

### Señales

| Señal | Comando | Descripción |
|-------|---------|-------------|
| SIGINT | `Ctrl+C` | Detener el simulador (graceful shutdown) |
| SIGTERM | `kill <pid>` | Detener el simulador (graceful shutdown) |
| SIGUSR1 | `kill -USR1 <pid>` | Forzar poll inmediato (inventario + check updates) |

**Ejemplo: Forzar poll inmediato**
```bash
# Obtener el PID del simulador
pgrep -f mender_simulator

# Forzar poll inmediato
kill -USR1 <pid>
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

## Systems (Mender Orchestrator)

Una industria con `tier: "system"` simula dispositivos **System** de
[Mender Orchestrator](https://docs.mender.io/orchestrate-updates/overview):
un host (p. ej. un gateway) que agrupa N componentes (MCUs, sensores, ECUs)
y los actualiza de forma atómica mediante **Manifests**.

**Requisitos**: tenant Enterprise con `max_system_devices > 0` y
mender-orchestrator ≥ 1.0.0 del lado servidor (protocolo GA, validado
end-to-end contra hosted Mender).

```yaml
industries:
  ev_vehicle:
    tier: "system"
    system_type: "ev-platform"
    inventory:
      device_type: "vcu"
      artifact_name: "ev-platform-v1"   # manifest instalado (nombre verbatim)
    components:
      - component_type: "vcu"
        id_format: "VCU-{site_id}"
        count: 1
        initial_version: "vcu-os-v1"
        system_component: true          # host del orchestrator (exactamente uno)
      - component_type: "bms"
        id_format: "BMS-{site_id}"
        count: 1
        initial_version: "bms-fw-v1"
        attrs: { bus: "can" }           # bus físico, visible en el tab System
```

Qué hace distinto un dispositivo System:

- **Autentica y se preautoriza con `tier: system`** (sin esto el device queda pending).
- **Reporta sus componentes** como atributos `mender-orchestrator-manifest.*`
  (formato `<id>/<valor>`, incluidos `system_component` y `manifest_name`,
  requeridos por el servidor GA) vía **PUT** de inventario — el servidor solo
  ingiere componentes en replaces completos.
- **Procesa deployments de Manifests**: descarga el artifact, parsea el YAML,
  actualiza componentes según `update_strategy.order`, **saltea** los que ya
  están en la versión target (sin reflash) y ante un fallo hace **rollback
  coordinado** de los ya actualizados, con logs que nombran al componente.

**Unidad de deploy**: siempre un Manifest (el servidor no sirve artifacts de
componente directo a un System → `noartifact`). Para actualizar **un solo
componente**, se deploya un manifest que solo cambia ese `component_type`:
los demás se saltean.

### Material de demo (manifests + artifacts de componentes)

```bash
# Genera (y con TOKEN=<PAT> sube) manifests v1/v2 y artifacts por componente
./scripts/create-orchestrator-material.sh system-core
./scripts/create-orchestrator-material.sh grid-site
./scripts/create-orchestrator-material.sh ev-platform
./scripts/create-orchestrator-material.sh ev-charging-hub
```

Protocolo completo, hallazgos verificados contra el servidor y guía de
diseño: [`docs/orchestrator-simulation.md`](docs/orchestrator-simulation.md).

## Cleanup / Decomisionar Dispositivos

Script para listar y eliminar dispositivos de Mender.

### Requisitos

Obtener un Personal Access Token (PAT) de Mender:
1. Ir a Mender UI → Settings → Access Tokens
2. Crear nuevo token
3. Exportar como variable de entorno

```bash
export MENDER_PAT='tu-personal-access-token'
```

### Listar dispositivos

```bash
./scripts/cleanup-devices.sh list              # Todos
./scripts/cleanup-devices.sh list-pending      # Pendientes
./scripts/cleanup-devices.sh list-accepted     # Aceptados
./scripts/cleanup-devices.sh list-rejected     # Rechazados
./scripts/cleanup-devices.sh list-noauth       # Sin autorización
```

### Decomisionar dispositivos

```bash
./scripts/cleanup-devices.sh decommission-pending   # Solo pendientes
./scripts/cleanup-devices.sh decommission-accepted  # Solo aceptados
./scripts/cleanup-devices.sh decommission-rejected  # Solo rechazados
./scripts/cleanup-devices.sh decommission-noauth    # Solo noauth
./scripts/cleanup-devices.sh decommission-all       # TODOS (cuidado!)
```

### Limpiar datos locales

```bash
# Elimina devices.db y simulator.log
./scripts/cleanup-devices.sh cleanup-local
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
