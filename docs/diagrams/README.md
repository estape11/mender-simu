# Diagramas del Proyecto

Diagramas de arquitectura y flujo del Mender Fleet Simulator.

## Archivos

| Archivo | Formato | Descripción |
|---------|---------|-------------|
| `architecture.puml` | PlantUML | Arquitectura de componentes |
| `device-flow.mmd` | Mermaid | Flujo de un dispositivo |
| `structure.d2` | D2 | Estructura de archivos |
| `update-sequence.puml` | PlantUML | Secuencia de actualización |

## Visualizar con Kroki

### Opción 1: Kroki.io Online

1. Copia el contenido del diagrama
2. Ve a https://kroki.io/
3. Selecciona el formato (PlantUML, Mermaid, D2)
4. Pega el contenido

### Opción 2: URL Directa

Codifica el diagrama en base64 y usa:

```
https://kroki.io/{formato}/svg/{base64}
```

Formatos:
- `plantuml` para archivos `.puml`
- `mermaid` para archivos `.mmd`
- `d2` para archivos `.d2`

### Opción 3: Docker Local

```bash
docker run -d -p 8000:8000 yuzutech/kroki

# Generar SVG
curl -X POST http://localhost:8000/plantuml/svg \
  -H "Content-Type: text/plain" \
  --data-binary @architecture.puml > architecture.svg
```

### Opción 4: CLI con curl

```bash
# PlantUML
cat architecture.puml | curl -s -X POST \
  -H "Content-Type: text/plain" \
  --data-binary @- \
  "https://kroki.io/plantuml/svg" > architecture.svg

# Mermaid
cat device-flow.mmd | curl -s -X POST \
  -H "Content-Type: text/plain" \
  --data-binary @- \
  "https://kroki.io/mermaid/svg" > device-flow.svg

# D2
cat structure.d2 | curl -s -X POST \
  -H "Content-Type: text/plain" \
  --data-binary @- \
  "https://kroki.io/d2/svg" > structure.svg
```

## Previews

### Arquitectura
![Architecture](https://kroki.io/plantuml/svg/eNqFkk1uwzAMhPc-BbeLJkDRRdZd9AY9gCvRjtCfVKKT5vaVndjNoivBw-f5KGLiEnq44YugxSFLBiHHSxEWxDRGWqGXnIQO3R6u5_Pu_nG3pQpZ1mAqYhjVAeYKQ06k5Xvn12CqhDGl7OMzEhuBMhKzNs5pL6zzRJm9fLpBZAYp00CPfCvL4I8BQ8BXWE4W55kpQp_0jyqYy_-SfkIkJaJ0zjn5LDhN0fQrKM_dGMvzWIv5dGLKbJTx6d_JrUe-h_b7s29p_1hqOT5evl7S_A0vX4fV)

### Flujo de Dispositivo
![Device Flow](https://kroki.io/mermaid/svg/eNp1kMEKwjAMhu99ipxFD4L36MUH8AE8S9faLdhubTqHiO9u6hzq8EOSfPn-hEylBOd7qC2Js-M0wUjxgiWNjKmLBHRyAc_RGR4_98v8sFzQQlGDYYrJ0-4AUZPUZlLiOp9qItUqOl33YA8pxzCEhx7_4QZkT-_BsS1N1jE5oUFxqIYe09Ahr5-KfIHjTevjG5VHX-M=)
