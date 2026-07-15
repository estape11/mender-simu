# Roadmap

Plan de releases del **Mender Fleet Simulator**. Cada release es una unidad
publicable; `main` siempre listo para usar. Versionado **SemVer** (ver
`GUIA_DESARROLLO.md` §5, fuente de verdad en `VERSION`).

**Convenciones**

- `S` = small (≤1 día), `M` = medium (1–3 días), `L` = large (>3 días).
- Cada release termina con un bump de `VERSION` + tag `vX.Y.Z` y su entrada en
  `CHANGELOG.md`.
- Los items provienen del backlog técnico (`TO_DO.md`) y del backlog de producto.

---

## v1.2.2 — Baseline ✅ (liberada)

Simulador funcional: persistencia SQLite, concurrencia asyncio, perfiles
multi-industria, ciclo de deployment realista, señales, `SIGUSR1` para poll
inmediato. 65 tests unitarios.

---

## v1.3.0 — Gobernanza, confiabilidad y rendimiento (M) 🚧

Adoptar el estándar de desarrollo y cerrar la deuda de rendimiento/robustez.

| Item | Esfuerzo | Origen |
|---|---|---|
| Estándar CIRO: `VERSION`, `ROADMAP`, CI/release, plantillas, labels | M | — |
| N+1 en inicialización: fetch único + agrupar por industria en memoria (`main.py`) | S | TO_DO |
| Reducir commits SQLite durante el progreso de descarga (`device_simulator.py`) | S | TO_DO |
| Retry con backoff para errores transitorios (5xx, connection) | M | TO_DO |
| Redactar tokens en logs (`auth.py`) | S | TO_DO |
| Excepciones específicas en `crypto.py` (solo excepciones de `cryptography`) | S | TO_DO |
| Validación profunda de config (`count>=0`, `bandwidth_kbps>0`, URLs válidas) | S | TO_DO |

**Demo:** una flota grande arranca sin saturar el servidor, reintenta errores
transitorios, y no filtra el tenant token en logs de DEBUG.

---

## v1.4.0 — Calidad de código y cobertura de tests (M)

Elevar la cobertura y limpiar la deuda de convenciones.

| Item | Esfuerzo | Origen |
|---|---|---|
| Tests para `client/` (auth, deployments, inventory, preauth) | M | tests canónicos |
| Tests para `simulation/device_simulator.py` y `decommission.py` | M | tests canónicos |
| Estandarizar type hints (`list[...]` PEP 585), ordenar imports, logger `__name__` | S | TO_DO |
| Unificar los 6 enrichers de `profiles.py` en un patrón declarativo | M | TO_DO |
| Eliminar código muerto (`get_inventory`, `get_success_probability`, telemetría vacía) | S | TO_DO |
| Enums y constantes (DeploymentState, puertos por estación) + renombres descriptivos | S | TO_DO |
| `mypy` como gate duro (quitar `continue-on-error`) | M | infra |

**Demo:** cobertura de los módulos `client/` y del loop de simulación; `mypy` en
verde como gate duro; cero código muerto.

---

## v2.0.0 — Observabilidad y extensibilidad (L)

Funcionalidad nueva que puede cambiar el esquema de config (major bump).

| Item | Esfuerzo |
|---|---|
| Métricas Prometheus (endpoint `/metrics`) | M |
| Dashboard web de monitoreo de la flota | L |
| Soporte mTLS para autenticación de dispositivos | M |
| Simulación de pérdida de conectividad (jitter, drops) | M |
| Perfiles de industria como plugins (sin tocar código del core) | L |
| Empaquetado Docker opcional + imagen en GHCR | M |

**Demo:** dashboard en tiempo real de una flota simulada, con métricas Prometheus
y perfiles de industria cargados como plugins.
