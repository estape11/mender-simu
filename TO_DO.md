# TO DO - Mejoras del Mender Fleet Simulator

## Rendimiento

### Criticos
- [ ] **N+1 en inicializacion** (`main.py:175-202`) — Fetch unico de dispositivos y agrupar en memoria por industria
- [x] **Reutilizar sesiones HTTP** (`client/`) — Compartir `aiohttp.ClientSession` entre clientes por dispositivo
- [ ] **Parallelizar preauth** (`main.py:207-213`) — Usar `asyncio.gather()` en vez de loop secuencial

### Medios
- [ ] **Reducir commits SQLite** (`device_simulator.py:251-262`) — Agrupar o reducir frecuencia durante progreso de descarga
- [ ] **Eliminar `get_inventory()` si no se usa** (`inventory.py`) — Codigo muerto potencial
- [ ] **Revisar `get_success_probability()`** (`profiles.py`) — No se usa; el simulador usa `config.simulator.success_rate` directamente

## Convenciones

- [x] **Sintaxis de tipos Python 3.9** (`preauth.py:20`) — Cambiar `X | None` a `Optional[X]`
- [ ] **Ordenar imports** — Estandarizar orden alfabetico y agrupacion en todos los archivos
- [ ] **Logger consistente** (`decommission.py:23`) — Usar `__name__` en vez de string hardcodeado
- [ ] **Estandarizar type hints** — Elegir entre `List[...]` (viejo) o `list[...]` (PEP 585) y unificar

## Claridad de codigo

- [ ] **Constante para puertos por estacion** (`profiles.py:198-199`) — Reemplazar magic number `4`
- [x] **Enum para device status** (`models.py`, `device_simulator.py`) — Crear `DeviceState` enum
- [ ] **Renombrar `check_token_valid()`** (`auth.py:100-123`) — Nombre no refleja lo que hace
- [ ] **Simplificar filtro preauth** (`main.py:207-211`) — Reducir complejidad del list comprehension
- [ ] **Renombrar `_identity_key()`** (`decommission.py:29-31`) — Nombre mas descriptivo

## Limpieza de codigo

- [x] **Clase base para clientes HTTP** — Extraer `_ensure_session()` y `close()` duplicados en 4 archivos
- [ ] **Unificar enrichers** (`profiles.py:218-270`) — Los 6 metodos siguen el mismo patron
- [ ] **Eliminar metodos de telemetria vacios** (`profiles.py`) — `_update_medical_telemetry()`, `_update_retail_telemetry()`
- [x] **Usar `__version__` en CLI** (`main.py:356`) — Evitar hardcodear la version

## Mejores practicas

### Altos
- [x] **Agregar timeouts HTTP** — `aiohttp.ClientTimeout(total=30)` en todas las llamadas
- [ ] **Excepciones especificas en crypto** (`crypto.py:79-95`) — Capturar solo excepciones de `cryptography`
- [ ] **Redactar tokens en logs** (`auth.py:78`) — No loguear tenant token en DEBUG
- [ ] **Agregar retry con backoff** — Reintentar errores transitorios (5xx, connection errors)

### Medios
- [ ] **Encriptar claves RSA en BD** (`database.py:41`) — Opcional para simulador
- [ ] **Validacion profunda de config** — Validar `count >= 0`, `bandwidth_kbps > 0`, URLs validas

## KISS

- [ ] **Simplificar `_identity_key()`** (`decommission.py:29-31`) — Usar `frozenset()` directamente
- [ ] **Simplificar `_format_inventory()`** (`inventory.py:38-53`) — Reducir logica innecesaria
- [ ] **Evaluar DeploymentState** — Enum vs constantes de string
- [ ] **Simplificar dispatch en profiles** (`profiles.py:29-39`) — Approach mas declarativo
