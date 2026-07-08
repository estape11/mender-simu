# Guía de Desarrollo — Mender Fleet Simulator

> Este proyecto adhiere al **estándar canónico de CIRO Technologies**:
> https://github.com/cirotechnologies/ciro-developer/blob/main/GUIA_DESARROLLO.md
>
> Este documento solo registra lo **específico del proyecto**. Todo lo no
> especificado aquí sigue el estándar canónico (flujo de trabajo, Conventional
> Commits, DoR/DoD, PRs, releases, seguridad).

## Identidad del proyecto

| Parámetro | Valor |
|---|---|
| Repo | `estape11/mender-simu` |
| Base branch | `main` |
| Versionado | `semver` (fuente de verdad: `VERSION`) |
| Lenguaje | Python ≥ 3.9 (asyncio) |
| Distribución | GitHub Release con sdist + wheel (`release.yml`); despliegue vía `install.sh` + systemd |
| Multi-tenant | N/A |

## Áreas de commit / labels `area:`

`client`, `simulation`, `db`, `config`, `crypto`, `scripts`, `infra`, `docs`,
`cross` (ver `.github/labels.yml`).

## Convenciones de código específicas

- **Persistencia:** SQLite vía `aiosqlite`. No hay migraciones SQL versionadas;
  el esquema se crea/actualiza en `db/database.py`. Queries **parametrizadas**
  (`?`), nunca concatenar.
- **Type hints:** compatibles con Python 3.9 (`Optional[X]`, `List[X]`) hasta
  estandarizar a PEP 585 (`list[X]`) en v1.4.0 — ver `ROADMAP.md`.
- **Formato:** `black` (line-length 88) + `flake8` (config en `.flake8`). `mypy`
  es informativo hasta v1.4.0.

## Cómo verificar localmente

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
black --check src/ tests/
flake8 src/ tests/
pytest --cov --cov-report=term-missing
```

## Recursos del proyecto

- `README.md` / `README_en.md` — quickstart.
- `ROADMAP.md` — fases y plan de releases.
- `CHANGELOG.md` — historial (Keep a Changelog).
- `TO_DO.md` — backlog técnico detallado.
