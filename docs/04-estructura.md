# 04. Estructura de archivos — ai_workflow_studio

```
ai_workflow_studio/
├── __manifest__.py          # Declaración del módulo: nombre, versión, dependencias (base, mail, web), datos, activos
├── __init__.py              # Importa modelos, servicios y controladores
├── models/
│   ├── __init__.py          # Importa todos los modelos
│   ├── aiws_workflow.py     # aiws.workflow: definición del flujo, estado, disparador, validación de grafo
│   ├── aiws_node.py         # aiws.node: nodo del flujo (tipo, configuración JSON, posición)
│   ├── aiws_connection.py   # aiws.connection: conexión dirigida entre nodos
│   ├── aiws_execution.py    # aiws.execution: instancia de ejecución, acción de ejecución, motor
│   ├── aiws_execution_log.py# aiws.execution_log: trazabilidad por nodo (entrada, salida, error, duración)
│   └── aiws_ai_provider.py  # aiws.ai_provider: credenciales de proveedores IA (solo admin)
├── services/
│   ├── __init__.py
│   ├── engine.py            # Motor de ejecución: estrategias por tipo de nodo, contexto, límites, ciclos
│   └── ai_provider.py       # Capa de proveedores IA: interfaz abstracta, registro, stub en V1
├── security/
│   ├── ir.model.access.csv  # ACL por modelo y grupo
│   ├── aiws_groups.xml      # Grupos aiws_group_user/editor/admin
│   └── aiws_security.xml    # Reglas de registro multi-compañía
├── views/
│   ├── aiws_workflow_views.xml   # List, form, search, editor visual (OWL) de workflows
│   ├── aiws_execution_views.xml  # List, form, search de ejecuciones
│   ├── aiws_execution_log_views.xml# List de logs de ejecución
│   ├── aiws_ai_provider_views.xml# List/form de proveedores IA (solo admin)
│   ├── menus.xml              # Árbol de menús de la aplicación
│   └── actions.xml            # Acciones de ventana y acciones de servidor
├── controllers/
│   ├── __init__.py
│   └── main.py                # Guardado de grafo, ejecución manual, endpoint de webhook
├── data/
│   └── aiws_data.xml          # Datos iniciales (grupos, ejemplo de flujo de prueba)
├── i18n/
│   └── ai_workflow_studio.pot # Plantilla de traducción (es, en)
├── static/
│   ├── description/
│   │   └── icon.png           # Icono del módulo en la lista de aplicaciones
│   └── src/
│       ├── components/
│       │   └── aiws_editor/
│       │       ├── index.js           # Componente OWL del editor visual (registro)
│       │       ├── editor.js          # Lógica del editor: lienzo, nodos, conexiones, drag, zoom
│       │       ├── editor.xml         # Plantilla OWL del editor
│       │       ├── editor.scss        # Estilos del editor
│       │       ├── node.js            # Componente nodo (puertos, arrastrar)
│       │       ├── node.xml           # Plantilla OWL del nodo
│       │       ├── connection.js      # Componente conexión (línea SVG)
│       │       └── connection.xml     # Plantilla OWL de la conexión
│       └── lib/                 # (reservado, sin librerías externas en V1)
├── tests/
│   ├── __init__.py
│   ├── test_engine.py         # Pruezas del motor (TransactionCase)
│   ├── test_security.py       # Pruebas de seguridad (ACL, reglas, SSRF, script admin)
│   ├── test_stub_ia.py        # Prueba del nodo IA stub sin red
│   └── test_graph_validation.py # Validación de grafo (ciclos, start/end)
├── docs/
│   ├── 01-analisis-funcional.md
│   ├── 02-arquitectura.md
│   ├── 03-diseno-tecnico.md
│   ├── 04-estructura.md
│   ├── DECISIONES.md
│   ├── ESTADO.md
│   ├── INFORME-FINAL.md
│   └── reviews/
│       ├── fase1.md
│       ├── fase2.md
│       ├── fase3.md
│       ├── fase4.md
│       ├── fase5.md
│       ├── fase6.md
│       └── fase7.md
├── tests/__init__.py
├── LICENSE                    # LGPL-3
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── .pre-commit-config.yaml
```

## Responsabilidad de cada archivo clave

| Archivo | Responsabilidad |
|---------|-----------------|
| `__manifest__.py` | Dependencias `base`, `mail`, `web`; versión 19.0.1.0.0; licencia LGPL-3; archivos de datos y vistas |
| `models/aiws_workflow.py` | Modelo principal; validación de grafo; disparo de ejecución; relación con ir.cron |
| `models/aiws_node.py` | Nodo con tipo, configuración JSON, posición; restricción de Script Python a admin |
| `models/aiws_connection.py` | Conexión origen→destino con condición opcional |
| `models/aiws_execution.py` | Ejecución; acción `action_run`; creación de logs; estados running/done/error |
| `models/aiws_execution_log.py` | Trazabilidad por nodo; entrada/salida sin credenciales |
| `models/aiws_ai_provider.py` | Credenciales de proveedor; campo password; solo admin |
| `services/engine.py` | Motor: DFS aciclicidad, estrategias de nodo, límites de pasos/tiempo, reintentos |
| `services/ai_provider.py` | Interfaz abstracta proveedor; registro; implementación stub en V1 |
| `security/ir.model.access.csv` | ACL estrictas por grupo |
| `security/aiws_groups.xml` | Definición de los 3 grupos y herencias |
| `security/aiws_security.xml` | Reglas de registro multi-compañía |
| `controllers/main.py` | Endpoint de guardado de grafo; ejecución manual por botón; webhook receptor |
| `static/src/components/aiws_editor/` | Componente OWL: lienzo SVG, nodos, conexiones, drag, zoom, propiedades |
| `tests/*` | Pruebas unitarias con TransactionCase, tags `ai_workflow_studio` |

**Fase 4 cerrada.** Revisión de consistencia estructural: todos los modelos de Fase 2 tienen su archivo Python; todas las vistas de Fase 3 tienen su archivo XML; los tests cubren motor, seguridad, stub IA y validación de grafo.
