# CLAUDE.md

Guía para agentes (Claude Code) y devs nuevos en **Mender Fleet Simulator**.
Este archivo es el punto de entrada; para el detalle, seguí los enlaces.

## Qué es

Simulador de flota de dispositivos para **Mender.io**: simula cientos de
dispositivos IoT (asyncio) de distintas verticales industriales para pruebas de
plataforma. Python ≥ 3.9, persistencia SQLite, despliegue por `install.sh` +
systemd. No hay Docker.

Dos clases de dispositivo:
- **Estándar** (rootfs único): `automotive`, `smart_buildings`, `medical`,
  `industrial_iot`, `retail`, `ev_charging`, `uas_airframe`, `uas_gcs`.
- **System / Orchestrator** (`tier: system`, agrupan componentes y se
  actualizan con Manifests): `system_core`, `grid_site`, `ev_vehicle`,
  `charging_hub`. Ver **`docs/orchestrator-simulation.md`**.

## Setup y comandos

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .                 # instala runtime + herramientas de dev

pytest                           # correr tests (153, todos deben pasar)
pytest --cov --cov-report=term-missing   # cobertura; gate: fail_under=55 (ver pyproject)
black --check src/ tests/        # formato (gate de CI)
flake8 src/ tests/               # lint (gate de CI)
shellcheck scripts/*.sh          # lint de scripts (gate de CI)
mypy                             # tipos (informativo hasta v1.4.0, ver ROADMAP)

python -m mender_simulator -c config/config.local.yaml   # ejecutar
```

El CI (`.github/workflows/ci.yml`) corre **lint + tests (3.9/3.11/3.12) +
shellcheck** como gate duro, más `typecheck` (mypy) y `audit` (pip-audit)
informativos. `main` está **protegido**: PR obligatorio con esos checks en
verde; sin verde no se mergea. Dependencias con cotas superiores en
`requirements.txt` (Dependabot propone los bumps).

## Cómo se trabaja (importante)

- **Flujo:** GitHub Flow. Todo cambio entra por PR a `main`; nunca commits
  directos. Rama `<tipo>/issue-<N>-<resumen>`. Ver **`GUIA_DESARROLLO.md`**.
- **Commits:** Conventional Commits, firmados (`-S`), ≤70 chars en el título.
- **Cada PR** agrega su entrada en `CHANGELOG.md` bajo `[Unreleased]` con `(#N)`,
  incluye pruebas con comandos exactos, y una sección **Hallazgos**.
- **CLAUDE Code / IA:** abre PRs pero no mergea los suyos (flujo `controlado`);
  el merge lo hace un humano.

## Dónde está el trabajo

- **`ROADMAP.md`** — releases planeadas (v1.3.0 confiabilidad · v1.4.0 calidad +
  tests · v2.0.0 observabilidad).
- **GitHub Issues** — backlog accionable con labels/milestones (`gh issue list`).
- **`TO_DO.md`** — backlog técnico detallado con referencias a archivo:línea.

## Arquitectura (en `src/mender_simulator/`)

- `main.py` — `FleetOrchestrator`: carga config, crea/lee dispositivos, maneja
  señales (SIGTERM/SIGINT, SIGUSR1 = poll inmediato).
- `client/` — cliente HTTP de Mender: `auth`, `inventory`, `deployments`,
  `preauth`, todos sobre `base.BaseClient` (sesión aiohttp compartida + timeouts).
- `simulation/` — `device_simulator.py` (loop y máquina de estados de deployment),
  `profiles.py` (identidad/inventario por industria), `system_simulator.py` +
  `manifest.py` (tier System / Orchestrator: componentes y deployments de
  manifests, ver `docs/orchestrator-simulation.md`).
- `db/` — `database.py` (SQLite async vía aiosqlite) y `models.py`
  (incluye `components_data` para System devices, con migración aditiva).
- `utils/` — `config.py` (YAML) y `crypto.py` (llaves RSA + firma).
- `scripts/` — `create-demo-artifacts.sh` (artifacts rootfs por industria),
  `create-orchestrator-material.sh` (manifests + artifacts de componentes;
  `TOKEN=<PAT>` los sube) + `mender-orchestrator-manifest-gen` (vendored),
  y `cleanup-devices.sh` (decomisionar).

## Gotchas

- **`VERSION`** (raíz) es la fuente de verdad de la versión; `setup.py` y
  `__init__.py` la leen. No hardcodear versiones.
- **Release:** taguear `vX.Y.Z` (== `VERSION` == sección del CHANGELOG) dispara
  `release.yml` → build sdist/wheel + GitHub Release. Ver `GUIA_DESARROLLO.md` §9.
- **Tests de `client/`:** inyectan una sesión aiohttp falsa (ver
  `tests/test_client.py::FakeSession`); no tocan la red.
- **Tier System (Orchestrator):** requiere tenant enterprise con
  `max_system_devices > 0`; el `tier` viaja en auth **y** preauth; el
  inventario de systems va por **PUT** (PATCH dropea los atributos de
  componentes); exactamente un `system_component` por topología; la unidad
  de deploy es el Manifest. Protocolo completo:
  `docs/orchestrator-simulation.md`.
- **PRs apilados:** al mergear una pila de PRs (uno con base en la rama de
  otro), **verificar que `main` quede con el contenido esperado** — mergear el
  PR base no arrastra los commits de los apilados. Confirmá con
  `git diff origin/main..<rama-punta> -- src/` (debe ser vacío) antes de dar
  por cerrado. Mejor: mergear la punta de la pila, no cada PR por separado.
- **Secretos:** nunca en el repo. `.env`, `*.db`, `*.log` están gitignoreados.
  Config sensible (tenant token, PAT) por `config/*local*.yaml` (cualquier
  nombre con `local`, no solo `*.local.yaml`).
- Los tests viejos insertan `src/` en `sys.path` (deuda, se limpia en #15); los
  tests nuevos usan imports directos (el paquete se instala con `pip install -e .`).
