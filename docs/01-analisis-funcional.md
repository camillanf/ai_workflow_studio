# 01. Análisis funcional — ai_workflow_studio

**Módulo:** ai_workflow_studio  
**Versión:** 19.0.1.0.0  
**Licencia:** LGPL-3  
**Objetivo Odoo:** Odoo 19 Community  
**Estado:** Cerrado (revisado por Analista — ver docs/reviews/fase1.md)

---

## 1. Visión y problema

Las operaciones internas de una empresa (aprobaciones, notificaciones, llamadas a servicios externos, actualización de registros) requieren hoy flujos de trabajo diseñados por desarrolladores (código Python, server actions, webhooks sueltos). Los usuarios de negocio no pueden crear ni modificar esos flujos sin tocar código.

**Propuesta de valor:** un editor visual sin código dentro de Odoo para crear flujos de automatización basados en nodos (Inicio, Fin, Condición, Acción Odoo, Webhook, Correo, Script Python, Agente IA), con ejecución manual y programada, trazabilidad completa por ejecución y por nodo, y capacidad de extensión para IA sin acoplar el módulo a ningún proveedor concreto.

---

## 2. Usuarios objetivo

| Perfil | Qué puede hacer | Grupo Odoo |
|--------|-----------------|------------|
| Usuario final | Ejecutar workflows disponibles, ver historial de sus ejecuciones | `aiws_group_user` |
| Editor de flujos | Crear, editar, borrar y activar/desactivar workflows y nodos | `aiws_group_editor` |
| Administrador | Gestionar credenciales de proveedores IA, nodos de Script Python, configuración del sistema | `aiws_group_admin` |

---

## 3. Casos de uso (V1)

1. **CU-01 Crear workflow:** el Editor crea un workflow vacío, define nombre, modelo objetivo y nodo de inicio.
2. **CU-02 Añadir nodos y conexiones:** el Editor arrastra nodos en el editor visual y conecta salidas a entradas.
3. **CU-03 Configurar nodo:** el Editor rellena el formulario de cada nodo (acción Odoo, destinatario de correo, URL de webhook, condición, etc.).
4. **CU-04 Ejecutar workflow manualmente:** el Usuario lanza la ejecución sobre un registro (o sin registro).
5. **CU-05 Ejecutar por disparador simple:** ejecución programada vía `ir.cron` (activar/desactivar).
6. **CU-06 Ver historial y trazabilidad:** cualquier usuario con permiso ve la lista de ejecuciones, su estado y el detalle entrada/salida/duración/error por nodo.
7. **CU-07 Agente IA (stub):** el nodo Agente IA devuelve una respuesta simulada a través de la interfaz de proveedor (sin llamada real en V1).

---

## 4. Entidades del dominio (V1)

| Entidad | Responsabilidad |
|---------|-----------------|
| `aiws.workflow` | Definición del flujo: nombre, modelo, activo, versión, nodo inicial, fecha creación/escritura, compañía. |
| `aiws.node` | Nodo de un workflow: tipo (start/end/condition/odoo_action/webhook/mail/python_script/ai_agent), nombre, configuración JSON, posición visual (x/y), orden. |
| `aiws.connection` | Conexión entre dos nodos: origen, destino, etiqueta, condición de salida opcional. |
| `aiws.execution` | Instancia de ejecución de un workflow: estado (running/done/error), contexto inicial, fecha inicio/fin, registro objetivo (res_model/res_id), compañía. |
| `aiws.execution_log` | Trazabilidad por nodo dentro de una ejecución: nodo, entrada, salida, estado, duración, error, marca de tiempo. |
| `aiws.ai_provider` | Credenciales/configuración de un proveedor IA (name, endpoint, api_key cifrada, activo). Solo administradores. |

---

## 5. Reglas funcionales y restricciones

- Un workflow debe tener exactamente un nodo de tipo `start` y al menos un nodo de tipo `end`.
- Las conexiones no pueden crear ciclos (se valida al guardar).
- Un nodo `condition` debe tener al menos dos conexiones de salida con condiciones distintas.
- La ejecución no puede superar 100 pasos ni 300 segundos (timeout por ejecución, configurable).
- Cada paso de nodo tiene timeout individual de 30 segundos.
- Máximo 3 reintentos por nodo en caso de error transitorio.
- El nodo Script Python solo puede ser creado/editado por miembros de `aiws_group_admin`; su ejecución usa `safe_eval` sin `os`, `sys`, red ni acceso a archivos (diferido a V2 si el revisor lo decide — ver DECISIONES.md).
- El nodo Webhook prohíbe URLs de IPs internas/loopback (SSRF), timeout 10 s, respuesta máxima 1 MB.
- El nodo Acción Odoo se ejecuta con el usuario que lanza el workflow (nunca `sudo()` implícito); respeta ACL y reglas de registro.
- Las claves API nunca se escriben en logs ni son visibles para usuarios no administradores.
- Todos los modelos llevan `company_id` con reglas de registro multi-compañía.
- El nodo Correo usa `mail.template` y `mail.mail` del core.

---

## 6. Roadmap

| Versión | Alcance |
|---------|---------|
| **V1 (esta entrega)** | Editor visual, todos los tipos de nodo, conexiones, ejecución manual y por `ir.cron` simple, historial, trazabilidad, Agente IA stub, grupos y seguridad base. |
| V2 | Nodo Script Python habilitado con sandbox, ejecutor asíncrono vía cola de jobs, reintentos condicionales, disparadores basados en eventos de Odoo (create/write/unlink). |
| V3 | Integraciones IA reales (proveedores configurables), marketplace de plantillas, versionado de workflows, exportación/importación JSON. |

---

## 7. Historias de usuario con criterios de aceptación

### US-01: Crear un workflow vacío
Como Editor, quiero crear un workflow desde el menú para poder definir un proceso automatizado.
- **AC1:** Existe menú "Flujos de trabajo IA" con acción de lista y formulario de `aiws.workflow`.
- **AC2:** Al crear un workflow se genera automáticamente un nodo de tipo `start`.
- **AC3:** El workflow se guarda en estado borrador (activo = False).

### US-02: Diseñar el flujo en el editor visual
Como Editor, quiero añadir nodos y conectarlos visualmente.
- **AC1:** El editor muestra lienzo con nodos (círculos/cajas) y conexiones (líneas con flecha).
- **AC2:** Se pueden arrastrar nodos y crear conexiones arrastrando de un puerto a otro.
- **AC3:** Se puede eliminar nodos y conexiones.
- **AC4:** Al guardar se valida: un nodo start, al menos un end, sin ciclos.

### US-03: Configurar un nodo Acción Odoo
Como Editor, quiero que un nodo escriba en un modelo de Odoo.
- **AC1:** El formulario del nodo permite elegir modelo, acción (create/write) y valores de campos.
- **AC2:** La ejecución respeta el usuario actual y sus ACL.

### US-04: Ejecutar un workflow
Como Usuario, quiero lanzar un workflow sobre un registro.
- **AC1:** Botón "Ejecutar" en el formulario del workflow y en la lista.
- **AC2:** Se crea un registro `aiws.execution` con estado `running` y luego `done` o `error`.
- **AC3:** Se genera al menos un `aiws.execution_log` por nodo recorrido.

### US-05: Ejecutar programadamente
Como Editor, quiero activar un workflow para que se ejecute cada X minutos.
- **AC1:** Campo "Activo" y "Intervalo (minutos)" en el workflow; al activar se crea/actualiza un `ir.cron`.
- **AC2:** La ejecución programada crea `aiws.execution` sin intervención manual.

### US-06: Ver trazabilidad
Como Usuario, quiero ver qué pasó en cada ejecución.
- **AC1:** Vista lista de ejecuciones con estado y duración.
- **AC2:** Vista de detalle de ejecución con lista de logs por nodo (entrada, salida, error, duración).
- **AC3:** Los errores se muestran claramente sin claves API.

### US-07: Nodo Agente IA (stub)
Como Editor, quiero disponer de un nodo Agente IA preparado para conectar proveedores reales.
- **AC1:** Existe tipo de nodo `ai_agent` con formulario de proveedor/modelo/prompt.
- **AC2:** Al ejecutar, devuelve una respuesta simulada (`{"response": "stub"}`) sin llamada de red real.
- **AC3:** La interfaz de proveedor está desacoplada de los nodos.

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación V1 |
|--------|---------|---------------|
| Colisión con módulo nativo `ai` de Odoo | Medio | Prefijo `aiws.` en todos los modelos; verificado en código fuente de Odoo 19. |
| Ejecución insegura de Script Python | Alto | Nodo de script diferido a V2 o sandbox estricto con `safe_eval` restringido. |
| SSRF en webhooks | Medio | Lista de IP bloqueadas (loopback/privadas) y timeout de respuesta. |
| Ejecuciones sin fin (ciclos/infinito) | Alto | Límite de 100 pasos y timeout de ejecución. |
| Credenciales filtradas en logs | Alto | Los logs excluyen campos `api_key`; solo admin ve credenciales. |

---

## 9. Criterios de salida Fase 1

- [x] Visión, usuarios, casos de uso, entidades, reglas, restricciones, roadmap, historias con AC, riesgos definidos.
- [x] Documento entregado en `docs/01-analisis-funcional.md`.
- [ ] Revisión del Analista registrada en `docs/reviews/fase1.md` sin hallazgos críticos abiertos.
