# 03. Diseño técnico — ai_workflow_studio

**Estado:** Cerrado (revisión pendiente en Fase 6 QA global)

---

## 1. Modelo de seguridad completo

### 1.1 Grupos (security/aiws_groups.xml)

| Grupo | Código XML | Implícito en | Permisos funcionales |
|-------|-----------|--------------|----------------------|
| Usuario | `aiws_group_user` | base.group_user | Ver workflows y ejecuciones; ejecutar workflows |
| Editor | `aiws_group_editor` | aiws_group_user | Crear/editar/borrar workflows, nodos, conexiones; activar disparadores |
| Administrador | `aiws_group_admin` | base.group_system | Todo lo anterior + credenciales IA, nodos Script Python, configuración del sistema |

Herencia: `aiws_group_editor` hereda de `aiws_group_user`; `aiws_group_admin` hereda de `base.group_system` (y por tanto de todo).

### 1.2 ACL (security/ir.model.access.csv)

| Modelo | Grupo | read | write | create | unlink |
|--------|-------|------|-------|--------|--------|
| aiws.workflow | aiws_group_user | 1 | 0 | 0 | 0 |
| aiws.workflow | aiws_group_editor | 1 | 1 | 1 | 1 |
| aiws.node | aiws_group_user | 1 | 0 | 0 | 0 |
| aiws.node | aiws_group_editor | 1 | 1 | 1 | 1 |
| aiws.connection | aiws_group_user | 1 | 0 | 0 | 0 |
| aiws.connection | aiws_group_editor | 1 | 1 | 1 | 1 |
| aiws.execution | aiws_group_user | 1 | 0 | 0 | 0 |
| aiws.execution_log | aiws_group_user | 1 | 0 | 0 | 0 |
| aiws.ai_provider | aiws_group_admin | 1 | 1 | 1 | 1 |
| aiws.ai_provider | otros grupos | 0 | 0 | 0 | 0 |

### 1.3 Reglas de registro (multi-compañía)

Todos los modelos transaccionales llevan `company_id`. Reglas de registro en `security/aiws_security.xml` con domain `[('company_id', '=', company_id)]` o `['|', ('company_id', '=', False), ('company_id', '=company_id')]` para registros sin compañía. Los usuarios ven solo registros de su compañía (salvo admin con todas las compañías).

`company_id` default: `res.company` del usuario (`default_company_id` / contexto).

### 1.4 Reglas no negociables aplicadas

- Script Python: modelo `aiws.node` escritura de `configuration` cuando `node_type == 'python_script'` restringida a `aiws_group_admin` vía regla de registro + comprobación en `write()`/`create()` del modelo.
- Webhook: validación de URL (no loopback/privada) en `create()`/`write()`; no hay almacenamiento de credenciales de webhook.
- Acción Odoo: ejecución con `self.env.user` (sin sudo).
- Credenciales IA: campo `api_key` tipo `password`; excluido de `aiws.execution_log.output_data`; lectura restringida a admin vía ACL.
- Correo: usa `mail.template` y `mail.mail` (respeta firma del usuario y configuración de correo saliente).

---

## 2. Contrato de la capa de proveedores IA (stub en V1)

Interfaz abstracta en `services/ai_provider.py`:

```python
class AIProviderInterface:
    def __init__(self, provider_record): ...
    def is_configured(self) -> bool
    def generate(self, prompt: str, context: dict) -> AIResponse
```

```python
class AIResponse:
    text: str
    provider: str
    model: str
    stub: bool   # True en V1
```

Registro de proveedores (dict por `provider` field): `openai`, `gemini`, `claude`, `ollama`, `opencode`, `other`.

En V1, **todos los proveedores devuelven respuesta simulada**:
```python
{"text": "Respuesta simulada (stub) del nodo Agente IA.", "provider": "stub", "model": "stub", "stub": True}
```
No hay llamadas de red real en V1. Los nodos `ai_agent` llaman al servicio a través de la interfaz, sin conocer la implementación.

Los nodos no dependen de proveedores concretos: reciben el `aiws.ai_provider` configurado en el workflow/nodo y delegan en `AIProviderInterface`.

---

## 3. Contrato del motor de ejecución

Clase `aiws.execution` con método público `action_run()` y método interno `_run_graph()`.

### Entrada
- `workflow_id`, contexto inicial (dict), `res_model`/`res_id` opcional, usuario ejecutor.

### Salida
- `aiws.execution` con state `done`/`error`; `aiws.execution_log` por nodo.

### Reglas del motor
1. Validación de grafo antes de ejecutar (un nodo `start`, al menos un `end`, aciclico).
2. Contexto de variables: dict compartido entre nodos; cada nodo lee/escribe.
3. Condiciones: expresión segura evaluada con `odoo.tools.safe_eval.safe_eval` sobre un sandbox con solo variables del contexto (sin builtins peligrosos).
4. Detección de ciclos: DFS sobre nodos y conexiones antes de ejecutar.
5. Límites: 100 pasos máx., 300 s máx. ejecución, 30 s por paso, 3 reintentos por nodo.
6. Nodo `start`: inicializa contexto.
7. Nodo `end`: finaliza ejecución.
8. Nodo `condition`: evalúa condición, elige conexión de salida.
9. Nodo `odoo_action`: ejecuta operación sobre `res_model` con `self.env.user`.
10. Nodo `webhook`: llamada HTTP saliente con lista de IP permitidas, timeout 10 s, respuesta max 1 MB.
11. Nodo `mail`: envía `mail.mail` desde `mail.template`.
12. Nodo `python_script`: (V1) raise `NotImplementedError` / respuesta simulada; (V2) `safe_eval` sandbox.
13. Nodo `ai_agent`: llama a `AIProviderInterface.generate()` (stub en V1).

### Ejecución programada
`ir.cron` (`aiws.workflow._trigger_flows`) ejecuta workflows con `is_trigger_enabled = True`, cada `trigger_interval_minutes`, creando `aiws.execution` como `ir.cron` user (configurable: usuario del workflow o usuario sistema).

---

## 4. Wireframes textuales

### 4.1 Menú principal
```
Aplicaciones > IA Workflow Studio
├── Flujos de trabajo (lista de aiws.workflow)        [grupo: user+]
│   └── Formulario flujo > botón "Ejecutar"
│   └── Editor visual (vista personalizada OWL)        [grupo: editor+]
├── Ejecuciones (lista de aiws.execution)              [grupo: user+]
│   └── Detalle ejecución + lista de logs por nodo
├── Proveedores IA (aiws.ai_provider)                  [grupo: admin]
└── Configuración (parámetros del sistema)             [grupo: admin]
```

### 4.2 Formulario workflow
Cabecera: nombre, descripción, modelo objetivo, activo, disparador activado, intervalo (min), compañía.
Cuerpo: pestaña "Diseño" con componente OWL del editor visual; pestaña "Ejecuciones" (lista enlazada aiws.execution).

### 4.3 Editor visual (OWL)
- Lienzo SVG central (fondo con grid opcional).
- Barra lateral izquierda: paleta de nodos (Inicio, Fin, Condición, Acción Odoo, Webhook, Correo, Script Python, Agente IA) arrastrables.
- Nodo en lienzo: rectángulo con nombre, tipo, puertos de entrada (arriba/izquierda) y salida (abajo/derecha).
- Conexión: línea SVG con flecha entre puertos.
- Panel derecho: propiedades del nodo seleccionado (formulario embebido según tipo).
- Barra superior: Guardar, Validar, Ejecutar, Cerrar.
- Notificaciones Odoo para errores de validación (ciclo, falta start/end).

### 4.4 Lista de ejecuciones
Columnas: flujo, estado (badge), registro objetivo, usuario, started_at, finished_at, duración, acciones (ver logs).

### 4.5 Detalle de ejecución / trazabilidad
Cabecera: flujo, estado, duración total.
Tabla de logs: nodo, tipo, estado, entrada (truncada), salida (truncada, sin credenciales), error, duración, executed_at.

---

## 5. Árbol de menús y acciones

| XML | Menú | Acción | Modelo | Grupo |
|-----|------|--------|--------|-------|
| aiws_menu_workflows | Flujos de trabajo | ir.actions.act_window | aiws.workflow | user |
| aiws_menu_executions | Ejecuciones | ir.actions.act_window | aiws.execution | user |
| aiws_menu_providers | Proveedores IA | ir.actions.act_window | aiws.ai_provider | admin |
| aiws_menu_config | Configuración | ir.actions.act_window | res.config.settings | admin |

Vistas por modelo: list (form heredado), form, search. No kanban (no aporta valor en V1).

---

## 6. Plan de pruebas

| Test | Tipo | Tag | Qué verifica |
|------|------|-----|--------------|
| test_engine.py | TransactionCase | ai_workflow_studio | Ejecución end-to-end de grafo simple, estados done/error |
| test_security.py | TransactionCase | ai_workflow_studio | ACL por grupo, reglas multi-compañía, Script Python solo admin, webhook SSRF bloqueado |
| test_stub_ia.py | TransactionCase | ai_workflow_studio | Nodo ai_agent devuelve stub sin red |
| test_graph_validation.py | TransactionCase | ai_workflow_studio | Ciclos detectados, falta start/end rechazado |

Ejecución:
`odoo-bin -c odoo.conf -d odoodb -i ai_workflow_studio --test-tags /ai_workflow_studio --stop-after-init`

---

## 7. Archivos técnicos resultantes

- `models/aiws_workflow.py`, `models/aiws_node.py`, `models/aiws_connection.py`, `models/aiws_execution.py`, `models/aiws_execution_log.py`, `models/aiws_ai_provider.py`
- `services/ai_provider.py`, `services/engine.py`
- `security/ir.model.access.csv`, `security/aiws_groups.xml`, `security/aiws_security.xml`
- `views/aiws_workflow_views.xml`, `views/aiws_execution_views.xml`, `views/aiws_execution_log_views.xml`, `views/aiws_ai_provider_views.xml`, `views/menus.xml`, `views/actions.xml`
- `controllers/main.py` (guardado de grafo, ejecución manual)
- `static/src/components/aiws_editor/` (componente OWL del editor visual)
- `data/aiws_data.xml` (grupos por defecto, usuario de demostración opcional)
- `tests/__init__.py`, `tests/test_engine.py`, `tests/test_security.py`, `tests/test_stub_ia.py`, `tests/test_graph_validation.py`
- `__manifest__.py`, `__init__.py`

**Fase 3 cerrada.**
