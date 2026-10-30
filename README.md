# AI Workflow Studio

[![Odoo 19.0](https://img.shields.io/badge/Odoo-19.0-blue)](https://www.odoo.com/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL-3-blue.svg)](LICENSE)

Visual, no-code workflow automation based on AI agents for **Odoo 19 Community**.

## ¿Qué permite hacer?

Diseñar flujos de automatización visuales dentro de Odoo sin programar:

- Nodos: Inicio, Fin, Condición, Acción Odoo, Webhook, Correo, Script Python, Agente IA.
- Editor visual con lienzo SVG, arrastrar soltar, conexiones, zoom y validación de grafo.
- Ejecución manual (botón) y programada (`ir.cron`).
- Historial completo de ejecuciones y trazabilidad por nodo (entrada, salida, estado, duración, error).
- Capa de proveedores IA desacoplada (stub en V1, lista para OpenAI, Gemini, Claude, Ollama, OpenCode).

## Alcance V1 (esta entrega)

**Real:** creación/edición de workflows, todos los tipos de nodo, conexiones, ejecución manual y por disparador programado simple, historial, visualización de ejecuciones y trazabilidad.

**Stub:** Agente IA (respuesta simulada a través de la interfaz de proveedor, sin llamadas de red reales).

**Fuera de V1:** integraciones IA reales, marketplace de plantillas, versionado avanzado, Script Python sandbox.

## Instalación

1. Copie este módulo en el carpeta de addons de Odoo (ej. `custom_addons/`).
2. Actualice la lista de aplicaciones en Odoo y instale "AI Workflow Studio".
3. Dependencias: `base`, `mail`, `web` (ya incluidas en Odoo Community).

## Seguridad

- Grupos: `AIWS User` (ver/ejecutar), `AIWS Editor` (crear/editar flujos), `AIWS Administrator` (credenciales, configuración).
- Reglas de registro multi-compañía en todos los modelos.
- Las API keys se almacenan en campos tipo contraseña y nunca se escriben en logs.
- Los nodos Webhook aplican protección SSRF (sin IPs privadas/loopback), timeout y límite de respuesta.
- El nodo Acción Odoo se ejecuta con el usuario que lanza el flujo (sin `sudo()` implícito).
- El nodo Script Python no es ejecutable en V1 (diferido a V2 por seguridad).

## Comandos de prueba (BD de desarrollo)

```bash
./odoo-bin -c odoo.conf -d odoodb -u ai_workflow_studio --test-tags /ai_workflow_studio --stop-after-init
```

## Estructura del módulo

```
ai_workflow_studio/
├── __manifest__.py
├── models/          aiws.workflow, aiws.node, aiws.connection, aiws.execution,
│                    aiws.execution_log, aiws.ai_provider
├── services/        motor de ejecución y interfaz de proveedores IA
├── security/        grupos, ACL y reglas de registro multi-compañía
├── views/           vistas, menús, acciones y página del editor OWL
├── controllers/     guardado de grafo, ejecución y webhooks
├── static/src/editor/   componente OWL del editor visual
├── tests/           pruebas del motor, seguridad, stub IA y grafo
├── i18n/            ai_workflow_studio.pot
├── LICENSE          (LGPL-3)
└── tests/...
```

## Roadmap

- V2: nodo Script Python con sandbox seguro, ejecutor asíncrono, disparadores por eventos de Odoo.
- V3: proveedores IA reales, marketplace de plantillas, versionado de workflows.

## Licencia

LGPL-3. Véase el archivo `LICENSE`.

## Soporte

Este módulo se entrega como código abierto comunitario, sin garantías comerciales.
Abra issues en el repositorio del proyecto para errores o propuestas de mejora.
