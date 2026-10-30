# Informe final — ai_workflow_studio (Odoo 19 Community)

## Qué se construyó

Módulo `ai_workflow_studio` v19.0.1.0.0, licencia LGPL-3, dependencias `base`, `mail`, `web`. Permite a usuarios no programar flujos visuales de automatización con agentes IA dentro de Odoo.

## Qué funciona (verificado en BD de desarrollo `odoodb`)

- Instalación/actualización limpia, sin errores ni modelos sin ACL.
- Creación/edición de workflows, nodos y conexiones (grafo relacional persistente).
- Todos los tipos de nodo V1: Inicio, Fin, Condición, Acción Odoo, Webhook, Correo, Script Python, Agente IA.
- Editor visual OWL (SVG puro, sin librerías externas): lienzo, arrastrar, conectar, zoom, validación y guardado (`/aiws/editor/<id>`).
- Ejecución manual (botón) y programada (`ir.cron`).
- Historial de ejecuciones y trazabilidad por nodo (entrada, salida, estado, duración, error).
- Seguridad: 3 grupos (User/Editor/Admin), ACL, reglas de registro multi-compañía, protección SSRF en webhooks, API keys ocultas y fuera de logs, Script Python no ejecutable en V1 (solo admin).
- Agente IA con interfaz de proveedor desacoplada; stub en V1 (respuesta simulada, sin red).

## Verificación ejecutada

```
./odoo-bin -c odoo.conf -d odoodb -u ai_workflow_studio --test-tags /ai_workflow_studio --stop-after-init
```
Resultado: `0 failed, 0 error(s) of 34 tests` (motor, seguridad, stub IA, validación de grafo).

## Qué NO está verificado

- Ejecución del servidor HTTP largo recorrido más allá de las pruebas de humo de los endpoints (grafo, guardar, ejecutar, editor, webhook) — probados manualmente con `curl` sobre `odoodb`.
- Integración IA real (OpenAI, Gemini, etc.): fuera de V1 (stub).

## Decisiones clave (docs/DECISIONES.md)

Prefijo `aiws.`; grafo relacional (no JSON); editor OWL puro sin librerías externas; Script Python diferido a V2; capa IA desacoplada con stub en V1; ejecución manual + `ir.cron`; límites fijos (100 pasos, 300 s, 30 s/paso, 3 reintentos); credenciales en campo `password`, solo administradores.

## Deuda técnica y pendientes

- `ruff` no ejecutado (no instalado en el entorno, no se instaló por regla); estilo PEP8 aplicado manualmente.
- Nodo Script Python ejecutable y sandbox (V2).
- Proveedores IA reales y disparadores por eventos de Odoo (V2/V3).
- Limpieza programada de logs antiguos (parámetro + cron ya documentados).

## Comandos

Instalar/actualizar y probar:
```
./odoo-bin -c odoo.conf -d odoodb -u ai_workflow_studio --test-tags /ai_workflow_studio --stop-after-init
```
Instalación en producción:
```
./odoo-bin -c odoo.conf -d <bd> -i ai_workflow_studio
```
Ruta del módulo: `custom_addons/ai_workflow_studio/`. Documentación: `docs/`.
