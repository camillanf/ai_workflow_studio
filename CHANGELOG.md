# Changelog — AI Workflow Studio

## [19.0.1.0.0] — 2026-10-17

### Añadido
- Módulo inicial para Odoo 19 Community.
- Modelos: `aiws.workflow`, `aiws.node`, `aiws.connection`, `aiws.execution`, `aiws.execution_log`, `aiws.ai_provider`.
- Grupos de seguridad: AIWS User, AIWS Editor, AIWS Administrator.
- ACL y reglas de registro multi-compañía.
- Vistas lista/formulario de workflows, ejecuciones, logs de ejecución y proveedores IA.
- Árbol de menús de la aplicación.
- Motor de ejecución: validación de grafo (un inicio, al menos un fin, sin ciclos), estrategias por tipo de nodo, contexto de variables entre nodos, límites (100 pasos, 300 s, 30 s/paso, 3 reintentos), detección de bucles en tiempo de ejecución.
- Ejecución manual y programada (`ir.cron`).
- Capa de proveedores IA desacoplada; stub en V1 (sin llamadas de red reales).
- Controlador: guardado de grafo con validación, ejecución manual, webhook entrante, llamada a webhook externo con protección SSRF.
- Editor visual OWL (SVG puro, sin librerías externas): lienzo, nodos, conexiones, arrastrar, zoom, propiedades, validación y guardado.
- Página del editor integrada desde el formulario del workflow.
- Pruebas unitarias: motor, seguridad (ACL, reglas multi-compañía, Script Python solo admin, SSRF), stub IA, validación de grafo.
- Internacionalización: `i18n/ai_workflow_studio.pot`.
- Documentación en `docs/` (fases 1 a 4, decisiones, estado).

### Seguridad
- Nodo Script Python no ejecutable en V1 (diferido a V2; edición restringida a administradores).
- API keys en campos tipo contraseña, excluidas de logs y ocultas a no administradores.
