# Simulador Profesional de Flota para Mender.io (PoC)
Objetivo: Desarrollar un simulador de dispositivos Mender en Python que sea persistente, realista y escalable, orientado a pruebas de plataforma en distintas verticales industriales.

1. Requisitos de Desarrollo y Workflow
Repositorio: Antes de escribir el código principal, genera una estructura de directorio profesional e inicializa un repositorio Git.

Pruebas: Genera una suite de Unit Tests (usando pytest) para validar la generación de llaves, la carga de configuración y la lógica de estados de actualización.

Documentación: Crea un README.md con instrucciones de instalación, configuración del entorno virtual (venv), ejecución y despliegue como servicio de sistema.

Log de ejecucion y planeación del proyecto: Crea un archivo de logs con cada decisión y cambios que hagamos al plan original.

2. Arquitectura Técnica y Persistencia
Concurrencia: Implementar con asyncio para manejar cientos de dispositivos en un solo proceso.

Base de Datos (SQLite): Los dispositivos no son volátiles. Se debe almacenar: device_id, identity_data, rsa_private_key, rsa_public_key, industry_profile y current_status.

Manejo de Señales: El script debe capturar SIGTERM y SIGINT para cerrar las conexiones y la base de datos de forma segura.

3. Lógica de Simulación por Industria
Crea perfiles configurables en un config.yaml que definan:

Identidad: Generación automática de IDs realistas (ej. VIN para Automotive, MAC para Smart Buildings, Serial/FDA-ID para Medical).

Inventario: Atributos específicos por vertical (versión de firmware, modelo de sensor, versión de kernel virtual, etc.).

Simulación de Red: * Cada industria tiene un "ancho de banda virtual".

Al recibir una actualización, el script debe calcular el tiempo de espera basado en el Content-Length del artefacto de Mender y la velocidad asignada.

Estados: Downloading (con progreso real en logs) -> Installing -> Rebooting -> Success/Failure.

4. Robustez y Telemetría
Sistema de Logs: Generar un archivo simulator.log que registre cada decisión (ej: "Device X decidiendo si acepta actualización") y progreso.

Tasa de Éxito (80%): Implementar una lógica probabilística de fallo.

Logs de Error: En caso de fallo (20%), enviar a Mender logs ficticios pero realistas (ej. "Kernel panic: VFS: Unable to mount root fs", "Checksum mismatch", "Out of memory during artifact extraction").

5. Configuración (YAML)
El archivo debe permitir configurar el tenant_token, server_url, poll_interval y una lista de grupos de dispositivos por industria con su respectivo count.

Entregables esperados:
Archivo requirements.txt.

Módulo de base de datos y modelos.

Lógica del Cliente Mender (Auth, Inventory, Deployments).

Script principal de orquestación asyncio.

Suite de tests unitarios.

Archivo de unidad mender-simulator.service para systemd.