# DECISIONES.md — ai_workflow_studio

Registro de decisiones de arquitectura y diseño. Cada entrada incluye contexto, opciones consideradas y justificación.

---

## D-001: Prefijo de modelos `aiws.`

**Contexto:** Los modelos mínimos de referencia son workflow, node, connection, execution, execution_log, agent/provider. Es necesario evitar colisiones con módulos de Odoo, en particular el módulo nativo `ai`.

**Opciones consideradas:**
1. `aiwf.` (ai workflow)
2. `aiws.` (ai workflow studio)
3. `workflow_` (genérico, alto riesgo de colisión)

**Decisión:** `aiws.`

**Justificación:** Se verificó en el código fuente de Odoo 19 (`odoo/addons/`) que no existe módulo nativo `ai`. El prefijo `aiws.` es corto, explícito del nombre del módulo y elimina riesgo de colisión. Aplica a todos los modelos y nombres técnicos.

---

## D-002: Persistencia del grafo relacional

**Contexto:** Persistir nodos y conexiones como modelos relacionales vs. un único campo JSON en `aiws.workflow`.

**Opciones consideradas:**
1. Modelos relacionales `aiws.node` + `aiws.connection` (elegido)
2. Campo JSON `graph_data` en `aiws.workflow`

**Decisión:** Relacional.

**Justificación:** Permite consultas SQL eficientes, reglas de registro multi-compañía por entidad, ACL granulares, trazabilidad por nodo (`aiws.execution_log` apunta a `aiws.node`) y sincronización simple con el editor visual (grafo completo enviado al guardar, borrado/recreado idempotente).

---

## D-003: Editor visual en Community

**Contexto:** Editor visual de flujos sin librerías de Enterprise ni dependencias de pago.

**Opciones consideradas:**
1. Componente OWL puro (SVG/HTML) (elegido)
2. Librería JS de diagramado vendorizada (licencia compatible)
3. iframe con librería externa (CDN)

**Decisión:** Componente OWL puro SVG/HTML, sin librerías externas.

**Justificación:** Odoo 19 Community usa OWL; evita dependencias no justificadas, problemas de licencia y llamadas a CDN. Zoom, arrastrar, conectar, validar y guardar se implementan con SVG nativo.

---

## D-004: Nodo Script Python

**Contexto:** El nodo Script Python permite ejecutar código arbitrario, lo que es un riesgo de seguridad.

**Opciones consideradas:**
1. Habilitar en V1 con `safe_eval` de `odoo.tools` sin `os`/`sys`/red/archivos
2. Diferir a V2 (nodo presente pero no ejecutable, respuesta simulada o error controlado)
3. Habilitar sin restricciones (rechazado: incumple seguridad)

**Decisión:** Diferir a V2. En V1 el nodo `python_script` existe en el modelo y el editor, pero su ejecución lanza `NotImplementedError` / respuesta simulada; su edición está restringida a `aiws_group_admin`.

**Justificación:** Seguridad no negociable. `safe_eval` reduce pero no elimina el riesgo; sin un sandbox probado a fondo se prefiere no ejecutar código de usuario en V1.

---

## D-005: Capa de proveedores IA

**Contexto:** El módulo debe estar "preparado para IA" sin acoplar nodos a un proveedor.

**Opciones consideradas:**
1. Interfaz abstracta `AIProviderInterface` (provider, model, request, response) + stub en V1 (elegido)
2. Integración directa OpenAI en V1
3. Nodo IA sin interfaz, llamada hardcodeada

**Decisión:** Interfaz abstracta desacoplada; en V1 todos los proveedores devuelven respuesta simulada (`stub: true`), sin llamadas de red reales.

**Justificación:** Permite añadir proveedores reales (OpenAI, Gemini, Claude, Ollama, OpenCode) en V3 sin tocar los nodos. Cumple el alcance V1 (stub) y evita dependencias de red ni claves API en esta entrega.

---

## D-006: Ejecución manual y programada

**Contexto:** Los workflows deben ejecutarse a demanda y de forma programada.

**Opciones consideradas:**
1. Solo manual (botón)
2. Solo `ir.cron`
3. Manual + `ir.cron` (elegido)

**Decisión:** Ejecución manual síncrona (botón/controlador) + ejecución programada vía `ir.cron` nativo de Odoo 19 (`_trigger`, `method_direct_trigger`).

**Justificación:** Cubre ambos casos de uso sin módulos externos. `ir.cron` es el estándar de Odoo para tareas programadas.

---

## D-007: Límites de ejecución

**Contexto:** Evitar bucles infinitos y ejecución descontrolada.

**Opciones consideradas:** Sin límites / Límites fijos / Límites configurables por parámetro del sistema.

**Decisión:** Límites fijos en V1 (pasos máx. 100, timeout ejecución 300 s, timeout por paso 30 s, reintentos 3), revisados para configurables en V2.

**Justificación:** Simplicidad y seguridad. Previene ejecuciones sin fin y consumo ilimitado de recursos.

---

## D-008: Almacenamiento de credenciales IA

**Contexto:** `aiws.ai_provider.api_key` debe protegerse.

**Opciones consideradas:**
1. Campo `password` de Odoo (widget password, no se guarda en logs) (elegido)
2. Campo `char` normal
3. Cifrado a nivel de aplicación con clave maestra

**Decisión:** Campo `password` (Char con widget password) + exclusión de logs + ACL solo admin.

**Justificación:** El widget `password` de Odoo oculta el valor en la interfaz y no lo incluye en los logs del servidor por defecto. Combinado con ACL de solo lectura para admin, cubre el requisito V1 sin complejidad criptográfica adicional.

---

**Última actualización:** Fase 2 (arquitectura). Pendiente de revisión QA en Fase 6.
