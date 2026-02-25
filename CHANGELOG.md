# Changelog y Decisiones del Proyecto

Este archivo documenta las decisiones de diseño y cambios realizados durante el desarrollo del Mender Fleet Simulator.

## [1.2.2] - 2026-02-24

### Nuevas Funcionalidades

#### SIGUSR1 para Poll Inmediato
- **Funcionalidad**: Enviar `kill -USR1 <pid>` fuerza un ciclo de inventario + verificación de updates
- **Uso**: Útil para testing sin esperar al `poll_interval`
- **Implementación**: Usa `asyncio.Event` para interrumpir el sleep del polling

---

## [1.2.1] - 2026-02-24

### Cambios

#### Inventario sin Telemetría en Tiempo Real
- **Cambio**: Eliminados atributos tipo telemetría (temperatura, voltaje, CPU, etc.)
- **Razón**: Mender NO es un sistema de telemetría en tiempo real
- **Resultado**: Solo atributos de estado del dispositivo que cambian infrecuentemente

#### Logs solo en Fallos
- **Cambio**: No se envían logs en deployments exitosos
- **Razón**: Solo es relevante registrar errores para diagnóstico

---

## [1.2.0] - 2026-02-24

### Correcciones

#### Formato de artifact_name y rootfs-image.version
- **Problema**: "Current software" y "Root filesystem version" se mostraban incorrectamente en Mender UI
- **Solución**: Ambos atributos ahora usan formato `{device_type}-{version}` (ej: `tcu-4g-lte-v1.0.0`)
- El config mantiene `artifact_name: "v1.0.0"` y el código genera el nombre completo

#### success_rate del Config
- **Problema**: El `success_rate` en config.yaml se ignoraba, usaba valores fijos por industria
- **Solución**: Ahora usa el valor del config (`success_rate: 1.0` = 100% éxito)

#### Timestamps RFC3339
- **Problema**: Mender rechazaba logs con error de parsing de timestamp
- **Solución**: Timestamps ahora incluyen `Z` al final (formato RFC3339)

#### Compatibilidad Bash 3.2
- **Problema**: `create-demo-artifacts.sh` fallaba en macOS (bash 3.2)
- **Solución**: Eliminado uso de arrays asociativos (`declare -A`)

### Mejoras

#### Tests para Scripts Bash
- Agregado `tests/test_scripts.py` con 16 tests para los scripts
- Cobertura de `cleanup-devices.sh` y `create-demo-artifacts.sh`

#### Inventario Inmediato Post-Update
- Después de un deployment exitoso, el inventario se envía inmediatamente
- Antes esperaba al siguiente ciclo de polling

---

## [1.1.0] - 2026-02-24

### Mejoras

#### Identity vs Inventory
- **Decisión**: Separar claramente identity (autenticación) de inventory (atributos)
- **Identity** solo contiene: `mac` + identificador único (serial_number, vin, pos_sn)
- **Inventory** contiene: device_type, firmware, y atributos dinámicos
- **Razón**: Sigue las mejores prácticas de Mender

#### Device Types Específicos
- Cambiado de nombres genéricos a específicos sin marcas:
  - `tcu-4g-lte` (Automotive)
  - `bms-controller-hvac` (Smart Buildings)
  - `patient-monitor-icu` (Medical)
  - `plc-gateway-modbus` (Industrial IoT)
  - `pos-terminal-emv` (Retail)

#### Re-autenticación Automática
- **Problema**: Dispositivos descomisionados quedaban en loop de errores 401
- **Solución**: `AuthenticationError` exception que invalida el token
- El dispositivo se re-autentica en el siguiente ciclo de polling

#### Script de Artefactos
- Agregado `scripts/create-demo-artifacts.sh`
- Genera artefactos de prueba por industria
- Versiones: v1.0.0, v1.1.0, v1.2.0, v2.0.0

---

## [1.0.0] - 2024-XX-XX

### Decisiones de Arquitectura

#### 1. Estructura del Proyecto
- **Decisión**: Organización modular con separación clara de responsabilidades
- **Razón**: Facilita testing, mantenimiento y extensibilidad
- **Estructura**:
  - `db/` - Capa de persistencia
  - `client/` - Comunicación con Mender API
  - `simulation/` - Lógica de negocio y perfiles
  - `utils/` - Funciones auxiliares

#### 2. Asyncio vs Threading
- **Decisión**: Usar `asyncio` para concurrencia
- **Razón**: Mejor rendimiento para operaciones I/O-bound (HTTP requests, DB)
- **Beneficio**: Un solo proceso puede manejar cientos de dispositivos

#### 3. SQLite con aiosqlite
- **Decisión**: SQLite para persistencia con wrapper async
- **Razón**:
  - Sin dependencias externas (no requiere servidor de BD)
  - Portable y fácil de respaldar
  - Suficiente para el caso de uso (cientos de dispositivos)
- **Alternativas consideradas**: PostgreSQL (descartado por complejidad)

#### 4. Perfiles de Industria
- **Decisión**: Configuración YAML con perfiles por vertical
- **Razón**: Flexibilidad para agregar nuevas industrias sin cambiar código
- **Implementación**: Clase `IndustryProfile` con generadores específicos

#### 5. Simulación de Bandwidth
- **Decisión**: Tiempo de descarga basado en Content-Length / bandwidth_kbps
- **Razón**: Realismo en la simulación de actualizaciones
- **Fórmula**: `download_time = artifact_size / (bandwidth_kbps * 1024)`

#### 6. Tasa de Éxito Probabilística
- **Decisión**: 80% éxito por defecto, configurable por industria
- **Razón**: Simular escenarios reales con fallos
- **Implementación**: `random.random() < success_rate`

#### 7. Mensajes de Error Realistas
- **Decisión**: Lista de errores típicos en config.yaml
- **Razón**: Logs útiles para testing de alertas y dashboards
- **Ejemplos**: Kernel panic, checksum mismatch, out of memory

### Implementación

#### Módulos Creados

1. **db/models.py**
   - `Device`: Dataclass con serialización JSON
   - `DeploymentStatus`: Seguimiento de actualizaciones

2. **db/database.py**
   - `DatabaseManager`: CRUD async para SQLite
   - Métodos para dispositivos y estados de deployment

3. **client/auth.py**
   - Autenticación con firma RSA
   - Manejo de tokens JWT

4. **client/inventory.py**
   - Actualización de atributos de inventario
   - Formato compatible con Mender API

5. **client/deployments.py**
   - Polling de deployments
   - Actualización de estados
   - Envío de logs

6. **simulation/profiles.py**
   - Generación de identidades por industria
   - Enriquecimiento de inventario
   - Cálculo de tiempos de descarga

7. **simulation/device_simulator.py**
   - Loop principal de cada dispositivo
   - Máquina de estados para actualizaciones
   - Generación de logs realistas

8. **main.py**
   - `FleetOrchestrator`: Coordina todos los dispositivos
   - Manejo de señales (SIGTERM, SIGINT)
   - Inicialización de base de datos

### Tests

- `test_crypto.py`: Generación y verificación de llaves RSA
- `test_config.py`: Carga y validación de configuración
- `test_database.py`: Operaciones CRUD async
- `test_profiles.py`: Generación de identidades e inventario

### Configuración

- **config.yaml**: Configuración principal con:
  - Credenciales del servidor Mender
  - Parámetros del simulador
  - Perfiles de industria
  - Mensajes de error

### Deployment

- **mender-simulator.service**: Unidad systemd con:
  - Hardening de seguridad
  - Restart automático
  - Logging a journal

---

## Próximos Pasos (Backlog)

1. [ ] Métricas Prometheus
2. [ ] Dashboard web para monitoreo
3. [ ] Soporte para mTLS
4. [ ] Simulación de pérdida de conectividad
5. [ ] Integración con CI/CD
