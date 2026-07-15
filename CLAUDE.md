# CLAUDE.md

Guía para agentes (Claude Code) y devs nuevos en **Mender Fleet Simulator**.
Este archivo es el punto de entrada; para el detalle, seguí los enlaces.

## Qué es

Simulador de flota de dispositivos para **Mender.io**: simula cientos de
dispositivos IoT (asyncio) de distintas verticales industriales para pruebas de
plataforma. Python ≥ 3.9, persistencia SQLite, despliegue por `install.sh` +
systemd. No hay Docker.

## Setup y comandos

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .                 # instala runtime + herramientas de dev

pytest                           # correr tests (103, todos deben pasar)
pytest --cov --cov-report=term-missing
black --check src/ tests/        # formato (gate de CI)
flake8 src/ tests/               # lint (gate de CI)
mypy                             # tipos (informativo hasta v1.4.0, ver ROADMAP)

python -m mender_simulator -c config/config.local.yaml   # ejecutar
```

El CI (`.github/workflows/ci.yml`) corre lint + tests en Python 3.9/3.11/3.12 y
es un **gate duro**: sin verde no se mergea.

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
- `simulation/` — `device_simulator.py` (loop y máquina de estados de deployment)
  y `profiles.py` (identidad/inventario por industria).
- `db/` — `database.py` (SQLite async vía aiosqlite) y `models.py`.
- `utils/` — `config.py` (YAML) y `crypto.py` (llaves RSA + firma).

## Gotchas

- **`VERSION`** (raíz) es la fuente de verdad de la versión; `setup.py` y
  `__init__.py` la leen. No hardcodear versiones.
- **Release:** taguear `vX.Y.Z` (== `VERSION` == sección del CHANGELOG) dispara
  `release.yml` → build sdist/wheel + GitHub Release. Ver `GUIA_DESARROLLO.md` §9.
- **Tests de `client/`:** inyectan una sesión aiohttp falsa (ver
  `tests/test_client.py::FakeSession`); no tocan la red.
- **Secretos:** nunca en el repo. `.env`, `*.db`, `*.log` están gitignoreados.
  Config sensible (tenant token, PAT) por `config/*.local.yaml`.
- Los tests viejos insertan `src/` en `sys.path` (deuda, se limpia en #15); los
  tests nuevos usan imports directos (el paquete se instala con `pip install -e .`).
