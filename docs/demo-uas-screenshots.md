# Demo UAS: setup y guía de screenshots

Guía para reproducir en el dashboard de Mender (hosted) la flota UAS de las
animaciones del demo ("OTA UAS fleet management", escenas 01–08) usando los
perfiles `uas_airframe` y `uas_gcs` del simulador, y qué screenshot tomar para
cada escena.

La flota simulada: **airframes** (`device_type: quad-x`, tail numbers
`UAS-0140…`, `flight-os` en versiones mixtas 2.1/2.2/2.3) y **ground control
stations** (`device_type: gcs`, `gcs-os` 4.8/4.9/5.0).

## 1. Configuración

Creá `config/config.demo.local.yaml` (cualquier `config/*.local.yaml` está
gitignoreado — ahí van las credenciales reales). Contenido sugerido (solo las
industrias UAS habilitadas; usa DB y log propios para no tocar `devices.db`):

```yaml
server:
  url: "https://hosted.mender.io"
  tenant_token: "<tenant token>"
  poll_interval: 15          # polls frecuentes para no esperar en el demo
  personal_access_token: "<PAT>"

simulator:
  success_rate: 1.0          # escena 01: el rollout converge sin fallos
  log_file: "uas-demo.log"
  database_path: "uas-demo.db"   # DB propia del demo, no toca devices.db

industries:
  automotive:      { enabled: false }
  smart_buildings: { enabled: false }
  medical:         { enabled: false }
  industrial_iot:  { enabled: false }
  retail:          { enabled: false }
  ev_charging:     { enabled: false }

  uas_airframe:
    enabled: true
    preauth: true
    count: 26                # la escena arranca con 26 airframes
    bandwidth_kbps: 400
    id_prefix: "UAS"
    id_format: "UAS-{tail_number}"
    tail_number_start: 140
    os_name: "flight-os"
    os_versions: ["2.1", "2.2", "2.3"]
    inventory:
      device_type: "quad-x"
      artifact_name: "2.3"
      kernel_version: "6.1.0-uas-rt"
      firmware_version: "FC-4.2"
      system_type: "uas-mk2"

  uas_gcs:
    enabled: true
    preauth: true
    count: 4                 # la escena muestra 4 estaciones
    bandwidth_kbps: 5000
    id_prefix: "GCS"
    id_format: "GCS-{station_id}"
    os_name: "gcs-os"
    os_versions: ["4.8", "4.9", "5.0"]
    inventory:
      device_type: "gcs"
      artifact_name: "5.0"
      kernel_version: "6.1.0-gcs"
      firmware_version: "GCS-5.0"
```

Correr: `python -m mender_simulator -c config/config.demo.local.yaml`

## 2. Setup en el dashboard de Mender (una vez)

1. **Identity attribute visible**: en Devices, agregá la columna
   `tail_number` / `station_id` (o configurá el atributo de identidad por
   defecto) para que los dispositivos se lean como `UAS-0142`, `GCS-01`.
2. **Grupos** (como en la escena 01):
   - Grupo **dinámico** `airframes` con filtro `device_type = quad-x`.
   - Grupo **estático** `gcs` con las 4 estaciones.
3. **Releases**: subí/generá artefactos dummy (p. ej. con `mender-artifact` o
   `scripts/`) con estos nombres y compatibilidad:
   - `flight-os-2.4` y `flight-os-2.5` → device type `quad-x`
   - `gcs-os-5.1` → device type `gcs`
   - (opcional, escena 01 "NEW") `flight-os-1.6` no hace falta como artefacto:
     los dispositivos nuevos se simulan cambiando `os_versions: ["1.6"]` y
     subiendo `count`.

## 3. Escena → screenshots

Cada escena corresponde a una animación del paquete del demo (compartido por
Drive como `drive-download-*/`, ocho HTML/MP4 de 1920×1080). El archivo fuente
se indica en cada título; los HTML se pueden abrir en el navegador (espacio
pausa, `?t=12.5` congela un frame) para comparar lado a lado con el screenshot.

### Escena 01 — Fleet rollout (grupos + deployment faseado)

> Fuente: `01-fleet-rollout.html` (27 s) — flota de versiones mixtas
> convergida por deployments por grupo; el grupo dinámico absorbe airframes
> nuevos.

1. **Flota mixta**: Devices → grupo `airframes`, columna "Current software":
   mezcla de `flight-os-2.1/2.2/2.3`. *(screenshot: la deriva de versiones)*
2. **Deployment faseado**: Create deployment → release `flight-os-2.4` → grupo
   `airframes` → phased rollout 10% / 40% / 50%. *(screenshot: el diálogo con
   las 3 fases antes de confirmar)*
3. **In progress**: vista del deployment con el donut de progreso y la lista
   de dispositivos en distintos estados (downloading/installing/rebooting).
   *(screenshot)*
4. **Deployment paralelo a `gcs`**: `gcs-os-5.1` al grupo estático `gcs`;
   screenshot de la lista de Deployments con ambos corriendo a la vez.
5. **Convergencia**: Devices → `airframes` con todos en `flight-os-2.4`, y el
   deployment en Finished. *(screenshot)*
6. **Dispositivos nuevos absorbidos**: editá la sección `uas_airframe` del
   config (`count: 30` y `os_versions: ["1.6"]`) y reiniciá el simulador: solo
   se crean los 4 faltantes (`UAS-0166…0169`) y nacen en `flight-os-1.6`; los
   26 existentes conservan su inventario (está en la DB). Mostralos entrando
   al grupo dinámico en 1.6 y actualizándose a 2.4. *(screenshots: antes y
   después)* — Nota: el deployment original ya habrá terminado; creá uno nuevo
   a `airframes`, el punto visual es el grupo dinámico absorbiendo
   dispositivos. No bajes `count`: el simulador decomisiona los sobrantes.

### Escena 02 — A/B + rollback automático

> Fuente: `02-ab-rollback.html` (31 s) — particiones A/B, commit tras boot
> exitoso, boot fallido → rollback automático del bootloader.

1. Bajá `success_rate` a `0.0` (o `0.2`) y deployá `flight-os-2.5` a
   `airframes`.
2. **Failure con rollback**: deployment en estado Failed; entrá a un
   dispositivo fallido y abrí el **deployment log** — el simulador reporta
   errores tipo "Rollback triggered: health check failed after 3 attempts".
   *(screenshots: donut con failures + log del dispositivo)*
3. **Sigue en la versión anterior**: Devices → el dispositivo fallido sigue
   reportando `flight-os-2.4` como Current software (nunca hizo commit de
   2.5). *(screenshot)*
4. Atributos A/B en el inventario del device: `update_scheme: dual-rootfs-ab`,
   `active_partition`, `data_partition: luks-encrypted-key-sealed-in-tpm`.
   *(screenshot del inventory expandido)*

### Escena 03 — Network environments (polling saliente)

> Fuente: `03-network-environments.html` (21 s) — polling HTTPS iniciado por
> el dispositivo, reanudación tras pérdida de enlace, delta por SATCOM, sin
> puertos de entrada.

- Device details de tres airframes con `network_environment` / `link_type`
  distintos: `depot-maintenance/wired-lan`, `forward-deployed/tactical-lte`,
  `remote-outpost/satcom`, y el atributo `poll_interval_seconds`. *(screenshot
  por cada uno, o la lista filtrada por `link_type`)*
- El mapa de dispositivos (atributos `geo-*`) muestra la flota dispersa.
  *(screenshot opcional)*

### Escena 04 — Air-gapped / Trusted Intermediary

> Fuente: `04-air-gapped-trusted-intermediary.html` (25 s) — sync del Trusted
> Intermediary, transferencia física, update local, reporte de estado al
> volver.

- No es simulable contra hosted Mender (es transferencia física). No hay
  screenshot del dashboard; usar la animación sola.

### Escena 05 — Identidad TPM

> Fuente: `05-tpm-device-identity.html` (24 s) — llave privada en el TPM firma
> los auth requests, clon de storage rechazado, solo artefactos firmados.

- Device details → inventario: `tpm_version: 2.0`,
  `identity_key_storage: tpm`, `artifact_verification: signed-only`.
  *(screenshot)*
- Devices → pestaña de **pending/rejected**: si corrés una segunda instancia
  con la misma identidad pero otra llave (clon), queda rechazada/pending.
  Alternativa simple: screenshot de la vista de auth del device (public key
  aceptada).

### Escena 06 — Orchestrator (componentes)

> Fuente: `06-orchestrator-system-update.html` (31 s) — un manifiesto, updates
> ordenados por componente sobre CAN/UART/Ethernet/SMBus, componentes sin
> cambios se saltan, rollback de sistema completo ante fallo. (Feature en
> preview según mender-docs.)

- Mender real no muestra el orchestrator (preview); lo que sí se puede
  mostrar: inventario del airframe con las versiones por componente
  (`flight_controller_version`, `gnss_receiver_version`,
  `eo_ir_payload_version`, `battery_mgmt_version`,
  `mission_computer_version`, `component_buses`) y `system_type: uas-mk2`.
  *(screenshot del inventory como "estado del sistema por componente")*

### Escena 07 — Configure

> Fuente: `07-configure.html` (20 s, standalone) — edición en consola →
> configuration deployment → el dispositivo (`UAS-0142`) aplica y reporta.

- El inventario reporta las mismas claves de la animación:
  `telemetry_rate_hz: 10`, `geofence_profile: training`,
  `datalink_channel: 4`, `log_level: info` en `UAS-0142`. *(screenshot)*
- Si el tenant tiene el add-on Configure: pestaña Configuration del device
  editando `geofence_profile → range-b`. El simulador no aplica config
  deployments (no implementado), así que el screenshot útil es el de la UI de
  edición / desired vs reported.

### Escena 08 — Troubleshoot

> Fuente: `08-troubleshoot.html` (26 s, standalone) — terminal remota, file
> transfer y port forward sobre WebSocket saliente en `UAS-0142`; audit log
> con replay de sesión.

- Requiere `mender-connect` real; el simulador no lo implementa. Si hace
  falta, tomar el screenshot de Remote terminal/File transfer con un
  dispositivo real del tenant, o solo usar la animación.

## 4. Orden sugerido de captura

1. Flota mixta (01.1) → grupos creados (01.2) → deployment faseado corriendo
   (01.3–01.4) → convergencia (01.5).
2. Inventarios: TPM (05), componentes (06), config (07), red (03) — todos son
   el mismo tipo de screenshot (device details) con el dispositivo `UAS-0142`
   para que calce con las escenas 07/08.
3. Failure/rollback al final (02), porque ensucia el historial de deployments.
