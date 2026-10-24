# Simulación de Systems y Componentes (Mender Orchestrator)

> Diseño para extender mender-simu con dispositivos tier **System**: dispositivos
> que orquestan updates multi-componente mediante Manifests. Basado en el testing
> real del epic *Orchestrator Management Interface* (MEN-7756) contra
> staging.hosted.mender.io realizado en octubre 2026, donde validamos el
> protocolo completo con dispositivos reales (contenedores con mender-client 5.1.1
> + mender-orchestrator 0.7.0). Todo lo descrito aquí está verificado contra el
> comportamiento real del servidor.

## 1. Contexto: qué es un System device

Mender Orchestrator introduce un nuevo tier de dispositivo: **System**. Un System
device (p. ej. un gateway) agrupa N **Componentes** (sub-dispositivos: MCUs, RTOS,
sensores) y orquesta sus actualizaciones de forma atómica mediante **Manifests** —
un YAML que declara qué versión de software corresponde a cada `component_type`
y en qué orden se actualiza, con rollback coordinado si un componente falla.

Del lado servidor (Hosted Mender, plan enterprise):
- Los System devices tienen su propio device limit (`max_system_devices`).
- Los Manifests viven separados de las Releases (tab Software → Manifests).
- El servidor **solo** sirve Manifests a devices tier=system, y **no** sirve
  artifacts normales a devices tier=system (verificado: incluso con spoofing de
  inventario, el bloqueo es por tier de devauth y el device queda en `noartifact`).

## 2. Protocolo a emular (verificado contra staging)

Esto es lo que un dispositivo simulado debe hacer distinto de un device estándar.

### 2.1 Autenticación — declarar el tier

El body del auth request (`POST /api/devices/v1/authentication/auth_requests`)
lleva un campo adicional `tier` (confirmado en el código de mender-auth,
`src/mender-auth/api/auth/auth.cpp`):

```json
{
  "id_data": "{\"mac\":\"...\",\"hostname\":\"...\"}",
  "pubkey": "-----BEGIN PUBLIC KEY-----...",
  "tenant_token": "...",
  "tier": "system"
}
```

Valores válidos: `standard` (default), `system`, `micro`. El tier queda fijado en
el auth set de devauth; el tenant debe tener `max_system_devices > 0` o la
aceptación falla.

### 2.2 Inventario — system_type y componentes

El device reporta los componentes vía atributos de inventario con prefijo
`mender-orchestrator-manifest.` y formato `<component_id>/<valor>` (así los envía
el script de inventario real, que ejecuta `mender-orchestrator show-inventory`):

```
system_type=system-core
mender-orchestrator-manifest.component_id=GW001
mender-orchestrator-manifest.component_id=R123
mender-orchestrator-manifest.component_type=GW001/gateway
mender-orchestrator-manifest.component_type=R123/rtos
mender-orchestrator-manifest.version=GW001/gateway-v2
mender-orchestrator-manifest.version=R123/rtos-v2
mender-orchestrator-manifest.<attr-custom>=R123/<valor>     # atributos extra por componente
data-partition.mender-orchestrator-manifest.version=system-core-v2   # manifest instalado
artifact_name=system-core-v2
update_modules=["directory","mender-orchestrator-manifest","rootfs-image","single-file"]
```

En el PATCH de inventario los valores repetidos van como listas
(`"value": ["GW001", "R123", ...]` y `["GW001/gateway", "R123/rtos", ...]`).
El servidor los parsea y expone por componente en
`GET /api/management/v2alpha1/inventory/devices/{id}/components` — que es lo que
renderiza el tab **System** de la UI (el tab solo aparece si `device.tier === "system"`;
para devices estándar el endpoint responde `400 "device needs to be system tier"`).

Cualquier atributo adicional `mender-orchestrator-manifest.X=<id>/<valor>` aparece
como atributo del componente `<id>` en ese endpoint (verificado con
`serial_number` y `fw_build`).

### 2.3 Deployments — recibir e instalar un Manifest

- El deployment llega por el flujo normal de `deployments/next`. El artifact es
  tipo `mender-orchestrator-manifest` y su payload es **un único archivo YAML**
  (el manifest). El matching servidor-side usa el `system_type` del inventario
  contra `system_types_compatible` del manifest, más el tier de devauth.
- Manifest de ejemplo (formato real):

```yaml
api_version: "mender/v1"
kind: "manifest"
name: "system-core-v2"              # DEBE ser igual al artifact name (validación del server)
system_types_compatible: ["system-core"]
component_types:
  gateway:
    artifact_name: gateway-v2
    update_strategy: { order: 10 }   # menor orden se actualiza primero
  rtos:
    artifact_name: rtos-v2
    update_strategy: { order: 20 }
```

- Al completar la instalación, el device reporta success y actualiza inventario:
  `artifact_name` y `data-partition.mender-orchestrator-manifest.version` pasan a
  ser el nombre del manifest, y la `version` de **cada componente** pasa al
  `artifact_name` que el manifest define para su `component_type`.
- En fallo de un componente: rollback de todos los componentes ya actualizados a
  su versión previa, status `failure` con logs que identifican el componente.

### 2.4 APIs de management útiles (para tooling/demos)

| Operación | Endpoint |
|---|---|
| Subir Manifest (.mender) | `POST /api/management/v1alpha1/deployments/manifests` (multipart `size`+`artifact`) |
| Subir Manifest (YAML crudo) | `POST /api/management/v1alpha1/deployments/manifests/generate` |
| Listar / detalle / tags / borrar | `GET /manifests`, `GET/PATCH/DELETE /manifests/{name}` (misma base v1alpha1) |
| Componentes de un device | `GET /api/management/v2alpha1/inventory/devices/{id}/components` |
| Marcar test device (staging) | `PUT /api/management/v2/devauth/devices/{id}/flags` `{"test_device": true}` |
| Límite de tier | `GET /api/management/v2/devauth/limits/max_system_devices` |

Hallazgos adicionales del smoke de la simulación contra staging (2026-10-23,
verificados contra el código del server):

- **Matching de manifests**: es el chequeo clásico de `device_type` de los
  `device_provides` de `deployments/next` contra los compatible types del
  artifact — y el artifact de manifest lleva el **system type** como
  compatible type. El stack orchestrator reporta el system type como
  `device_type` en `/next` (el `device_type` del inventario es solo display,
  p. ej. `gateway`). Con el device_type "normal" el server resuelve
  `noartifact` instantáneamente (precalcula con el cache de provides).
- **Ingestión de componentes**: el server SOLO procesa los atributos
  `mender-orchestrator-manifest.*` en el **PUT** (replace completo) de
  inventario, que es lo que usa el cliente real; en PATCH los dropea a
  propósito (`inventory.go`: "semantics … with partial updates is
  undefined"). El simulador envía PUT para systems, con fallback a PATCH.
- **Regresión en staging** (al 2026-10-23), aparentemente un rollback del
  feature set de Orchestrator en un deploy ~21-oct, en dos frentes:
  1. `PUT /api/devices/v1/inventory/device/attributes` devuelve `500 internal
     error` con cualquier payload (hasta 1 atributo trivial) → la ingestión de
     components queda vacía para dispositivos nuevos. Reproducido también con
     un cliente real (mender-client 5.1.1, último submit exitoso 19-oct).
     Sospechoso: commit `b9d6dcdd` (2026-10-21, "remove
     orchestrator_attributes_processing_enabled feature flag"). Request IDs:
     `5d71e38d…`, `813248b3…`, `bffb36ab…`.
  2. El frontend desplegado ya no incluye la UI de Orchestrator: el bundle del
     1-oct (`5e3f002e…`) la contenía (tab System por tier, tab Manifests,
     endpoints v1alpha1); el del 23-oct (`41bc89f6…`) tiene cero ocurrencias
     de `tier==="system"`, `system_type`, `Manifests` o `DeviceSystem` — el
     único tab "System" restante es el de Mender Gateway
     (`mender_is_gateway`). Por eso el tab no aparece para ningún device,
     simulado o real.
  Draft del reporte (sub-tasks de MEN-10170) con la evidencia consolidada:
  `~/Documents/orchestrator/findings/MEN-10170-draft.md`.

Gotchas verificados:
- El endpoint clásico de artifacts **rechaza** manifests
  (`invalid update type: mender-orchestrator-manifest`); usar la API v1alpha1.
- El `name` del YAML debe ser **igual** al artifact name o el upload falla con 400
  (los ejemplos de la doc oficial violan esto — bug conocido, OBS-3 del testing).
- Deployments bloqueados por tier terminan en `noartifact` (no hay status más
  explicativo hoy; `incompatible_tier` existe en las stats pero no dispara — OBS-4).
- En staging, marcar los devices como test device o el rate limit (3s/endpoint,
  60 req/min) castiga flotas grandes.

## 3. Diseño de integración en mender-simu

Principio: **un System device es un DeviceSimulator con estado de componentes y
un procesador de deployments distinto**. Nada del resto cambia (auth loop, DB,
preauth, concurrencia asyncio).

### 3.1 Config (`config/*.yaml`)

Extender `IndustryConfig` con campos opcionales; una industria con `tier: system`
se convierte en flota de Systems:

```yaml
industries:
  grid_site:
    enabled: true
    preauth: true
    count: 10
    tier: "system"                    # NUEVO → usa SystemDeviceSimulator
    system_type: "grid-monitoring-site" # NUEVO
    id_prefix: "GRID"
    id_format: "GRID-SITE-{site_id}"
    inventory:
      device_type: "grid-gateway"
      artifact_name: "grid-site-v1"
    components:                        # NUEVO
      - component_type: "edge-gateway"
        id_format: "GW-{site_id}"
        count: 1
        initial_version: "gridgw-v1"
      - component_type: "line-sensor"
        id_format: "LS-{site_id}-{n}"
        count: 3
        initial_version: "lsensor-fw-v1"
        telemetry: line_sensor         # generador de telemetría por componente
```

### 3.2 Código

```
src/mender_simulator/
├── client/auth.py            # + parámetro opcional tier en el body del auth request
├── simulation/
│   ├── system_simulator.py   # NUEVO: SystemDeviceSimulator(DeviceSimulator)
│   ├── manifest.py           # NUEVO: parseo del artifact .mender → YAML → plan de update
│   └── profiles.py           # + perfiles system (generic-core, grid_site)
├── db/models.py              # Device.components_data: JSON {id: {type, version, attrs}}
└── db/database.py            # migración: columna components_data
```

`SystemDeviceSimulator` sobreescribe:

1. **`_authenticate`** → pasa `tier="system"`.
2. **`_update_inventory`** → agrega `system_type`, los atributos
   `mender-orchestrator-manifest.*` en formato `id/valor` desde
   `components_data`, y `data-partition.mender-orchestrator-manifest.version`.
3. **`_process_deployment`** → si el artifact es tipo
   `mender-orchestrator-manifest`:
   - Descarga el artifact y extrae el YAML (el .mender es un tar; el payload
     está en `data/0000.tar[.gz]`). Alternativa simple para simulación: derivar
     las versiones objetivo del `artifact_name` por convención del perfil.
   - Ordena `component_types` por `update_strategy.order` y los "instala" en
     secuencia (sleep por componente, progress por etapas Downloading →
     Installing → Rebooting como hoy).
   - `success_rate` aplica **por componente**: si un componente falla, rollback
     de los ya instalados (restaurar `components_data` previo) y reporte de
     `failure` con logs estilo orchestrator que nombran al componente culpable:
     `"##### [rtos-interface 2] Failing ArtifactCommit"` /
     `"Rollback: component LS-04-2 (line-sensor) restored to lsensor-fw-v1"`.
   - En success: actualizar `components_data` + inventario inmediato (igual que
     hoy se hace con `artifact_name`).

### 3.3 Tooling de artifacts/manifests (reutilizable del testing)

En `~/Documents/orchestrator` (repo del testing MEN-7756) ya existe y funciona:
- `tools/mender-orchestrator-manifest-gen` — generador oficial (vendored).
- `material/gen-material.sh` — genera artifacts de componentes (module-image,
  payload vacío) + manifests válidos e inválidos. Adaptarlo a `scripts/` de este
  repo parametrizando component_types y versiones.

Los artifacts de componentes son `module-image` triviales
(`--type <interface> --compatible-types <component_type> --artifact-name <ver>`),
el servidor no valida su contenido — perfecto para simulación.

## 4. Demo A — Genérico Orchestrator (`system-core`)

Réplica a escala del setup validado en staging. Objetivo: demostrar el feature
end-to-end sin dominio específico.

- **Flota**: 15 systems `SYS-001..015`, system_type `system-core`,
  device_type `gateway`. Componentes por system: 1 `gateway` (GW-xxx) +
  2 `rtos` (R-xxx-1/2). Más 5 devices estándar de contraste (sin tab System).
- **Software**: manifests `system-core-v1` / `system-core-v2`; artifacts
  `gateway-v1/v2`, `rtos-v1/v2`.
- **Guion**:
  1. Flota converge en v1 → tab System muestra componentes y versiones; filtros
     por tier, por versión de componente y por manifest instalado.
  2. Deployment de `system-core-v2` a toda la flota → éxito masivo, componentes
     actualizados en orden (gateway primero).
  3. Con `success_rate < 1`, algunos sites fallan un componente → rollback
     coordinado visible + logs por componente.
  4. Deployment de un manifest a un device estándar y de un artifact normal a un
     system → ambos bloqueados por el server (`noartifact`).

## 5. Demo B — Industria eléctrica de potencia (`grid-monitoring-site`)

Caso: monitoreo de líneas de transmisión eléctrica con sensores **non-contact**
montados en torres, que miden temperatura del conductor, sag (catenaria) y
vibración/galloping, y habilitan **Dynamic Line Rating** (DLR: capacidad
dinámica de la línea según condiciones reales). Arquitectura física típica: por
sitio de monitoreo (torre/vano), un compute/gateway con backhaul celular +
2-3 unidades sensoras apuntando a las fases + estación meteorológica. Es un
caso natural de Orchestrator: el firmware de sensores y el software del gateway
deben actualizarse como un conjunto coherente por sitio.

- **System** = sitio de monitoreo. `system_type: grid-monitoring-site`,
  device_type `grid-gateway`, IDs `GRID-SITE-0401..0410` (10 sitios a lo largo de un
  corredor de transmisión; usar `geo_data.py` para distribuirlos
  geográficamente, atributos `geo_lat`/`geo_lon` + `line_id` tipo
  `TL-115kV-North`, `span_id`).
- **Componentes por sitio**:
  | id | component_type | software | ejemplo versión |
  |---|---|---|---|
  | GW-0401 | edge-gateway | SO del compute | `gridgw-v2.1` |
  | LS-0401-1..3 | line-sensor | firmware sensor | `lsensor-fw-v3.4` |
  | WX-0401 | weather-station | firmware meteo | `wx-fw-v1.2` |
- **Atributos dinámicos** (dan vida al demo, pero non-realtime: el inventario
  de Mender no es un canal de telemetría — modelan agregados/estado que cambia
  lento, no lecturas en vivo): por componente sensor `conductor_temp_c` y
  `sag_m` (último agregado horario, deriva ocasional) + `sensor_status`
  (ok / needs-calibration); por sitio `ampacity_rating_a` (DLR recalculado
  ~1/hora), `backhaul_rssi_dbm` (deriva lenta) y `battery_health`.
- **Manifests**: `grid-site-v1` → `grid-site-v2` (p. ej. "actualización de firmware
  de sensores para mejorar el modelo de DLR"), orden: gateway (10) → sensores
  (20) → meteo (30).
- **Guion**: igual que el demo A pero narrado en dominio utility: "rollout del
  nuevo firmware de line sensors al corredor norte", un sitio hace rollback por
  fallo en un sensor (se ve exactamente **qué componente** de **qué torre**
  falló), filtro de flota por `lsensor-fw` para encontrar sitios con firmware
  vulnerable/viejo (ese filtro por versión de componente es acceptance criterion
  del epic).

## 6. Fases de implementación sugeridas

1. **F1 — Protocolo**: `tier` en AuthClient + inventario de componentes estático
   (hardcodeado desde config). Resultado: devices aparecen como System con tab
   System poblado. *(~1 día)*
2. **F2 — Manifests**: procesamiento de deployments de manifests (por convención
   de nombres, sin parsear el .mender), update de componentes en orden, success
   path. Resultado: demo A guion 1-2. *(~1-2 días)*
3. **F3 — Fallos**: fallo por componente, rollback, logs estilo orchestrator.
   Parseo real del YAML del artifact. Resultado: demo A completo. *(~1 día)*
4. **F4 — Perfil grid**: perfil + telemetría + geo + script de generación
   de artifacts/manifests `grid-*`. Resultado: demo B. *(~1 día)*

## 7. Referencias

- Repo del testing (setup real reproducible, scripts, hallazgos):
  `~/Documents/orchestrator` — ver `TEST_ESTAPE.md`, `RESULTS_ESTAPE.md`
  (OBS-1..4), `device/`, `material/`, `tools/`.
- Docs oficiales: [Orchestrator overview](https://docs.mender.io/orchestrate-updates/overview),
  [mock components](https://docs.mender.io/orchestrate-updates/examples/mock-components).
- Upstream: [mendersoftware/mender-orchestrator-support](https://github.com/mendersoftware/mender-orchestrator-support)
  (interfaces mock, demo, manifest-gen, premade artifacts).
- Cliente (wire format del tier): `mendersoftware/mender`,
  `src/mender-auth/api/auth/auth.cpp` y `src/common/device_tier.hpp`.
- Requisito de tenant: plan enterprise + `max_system_devices > 0` (Admin Panel).
