import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

from odoo import fields, http, tools
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# SSRF: rangos de IP privados/loopback bloqueados para llamadas salientes del nodo Webhook
BLOCKED_IP_PREFIXES = (
    # Loopback
    "127.", "::1",
    # RFC 1918 - Private IPv4
    "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.", "192.168.",
    # Link-local IPv4 (API metadata cloud)
    "169.254.",
    # RFC 4193 - ULA IPv6 (Unique Local Addresses)
    "fc00.", "fd00.",
    # Link-local IPv6
    "fe80.",
    # Docker/K8s common bridges
    "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.",
    # CGNAT / Shared address space (RFC 6598)
    "100.64.", "100.65.", "100.66.", "100.67.", "100.68.", "100.69.", "100.70.",
    "100.71.", "100.72.", "100.73.", "100.74.", "100.75.", "100.76.", "100.77.",
    "100.78.", "100.79.", "100.80.", "100.81.", "100.82.", "100.83.", "100.84.",
    "100.85.", "100.86.", "100.87.", "100.88.", "100.89.", "100.90.", "100.91.",
    "100.92.", "100.93.", "100.94.", "100.95.", "100.96.", "100.97.", "100.98.",
    "100.99.", "100.100.", "100.101.", "100.102.", "100.103.", "100.104.",
    "100.105.", "100.106.", "100.107.", "100.108.", "100.109.", "100.110.",
    "100.111.", "100.112.", "100.113.", "100.114.", "100.115.", "100.116.",
    "100.117.", "100.118.", "100.119.", "100.120.", "100.121.", "100.122.",
    "100.123.", "100.124.", "100.125.", "100.126.", "100.127.",
)
WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB


def fields_datetime_now():
    return fields.Datetime.now()


class AiwsController(http.Controller):
    @http.route("/aiws/workflow/<int:workflow_id>/save_graph", type="jsonrpc", auth="user")
    def save_graph(self, workflow_id, nodes=None, connections=None):
        """Guarda el grafo completo (nodos + conexiones) desde el editor visual.

        Valida el grafo antes de persistir: un nodo Inicio, al menos un Fin,
        sin ciclos.
        """
        workflow = request.env["aiws.workflow"].browse(workflow_id)
        if not workflow.exists():
            return {"error": "workflow_not_found"}

        nodes = nodes or []
        connections = connections or []

        # Borrado/recreación idempotente del grafo del workflow.
        # Archivamos nodos antiguos (soft delete) para preservar historial de ejecuciones.
        workflow.connection_ids.unlink()
        workflow.node_ids.write({"active": False})

        node_records = {}
        for node_data in nodes:
            node = request.env["aiws.node"].create(
                {
                    "workflow_id": workflow.id,
                    "name": node_data.get("name") or "Nodo",
                    "node_type": node_data.get("node_type") or "odoo_action",
                    "configuration": node_data.get("configuration") or "{}",
                    "condition": node_data.get("condition") or False,
                    "position_x": int(node_data.get("position_x") or 0),
                    "position_y": int(node_data.get("position_y") or 0),
                    "sequence": int(node_data.get("sequence") or 10),
                }
            )
            node_records[node_data.get("id")] = node

        for conn_data in connections:
            source = node_records.get(conn_data.get("source"))
            target = node_records.get(conn_data.get("target"))
            if not source or not target:
                continue
            request.env["aiws.connection"].create(
                {
                    "workflow_id": workflow.id,
                    "source_node_id": source.id,
                    "target_node_id": target.id,
                    "label": conn_data.get("label") or "",
                    "condition": conn_data.get("condition") or "",
                    "branch": conn_data.get("branch") or False,
                    "sequence": int(conn_data.get("sequence") or 10),
                }
            )

        # Validación de grafo antes de confirmar.
        from ..services.engine import WorkflowEngine

        engine = WorkflowEngine(request.env)
        errors = engine.validate_graph(workflow)
        if errors:
            return {"error": "graph_invalid", "errors": errors}

        return {"status": "ok"}

    @http.route("/aiws/workflow/<int:workflow_id>/graph", type="jsonrpc", auth="user")
    def graph(self, workflow_id):
        """Devuelve nodos y conexiones de un workflow para el editor visual."""
        workflow = request.env["aiws.workflow"].browse(workflow_id)
        if not workflow.exists():
            return {"error": "workflow_not_found"}
        nodes = request.env["aiws.node"].search_read(
            [("workflow_id", "=", workflow_id), ("active", "=", True)],
            ["name", "node_type", "configuration", "condition", "position_x", "position_y", "sequence"],
        )
        connections = request.env["aiws.connection"].search_read(
            [("workflow_id", "=", workflow_id)],
            ["source_node_id", "target_node_id", "label", "condition", "branch", "sequence"],
        )
        # Proveedores activos para el selector del nodo AI Agent.
        # Se leen con sudo y sin api_key: solo se expone nombre/tipo/modelo.
        providers = request.env["aiws.ai_provider"].sudo().search_read(
            [("active", "=", True)],
            ["name", "provider", "model"],
            order="name",
        )
        return {
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "model": workflow.model,
            },
            "nodes": nodes,
            "connections": connections,
            "providers": providers,
        }

    @http.route("/aiws/workflow/<int:workflow_id>/run", type="jsonrpc", auth="user")
    def run_workflow(self, workflow_id, context="{}"):
        """Ejecuta un workflow manualmente desde el cliente."""
        workflow = request.env["aiws.workflow"].browse(workflow_id)
        if not workflow.exists():
            return {"error": "workflow_not_found"}

        # Asegurar estado limpio de la conexión antes de empezar
        try:
            request.env.cr.rollback()
        except Exception:  # noqa: BLE001
            pass

        execution = request.env["aiws.execution"].create(
            {
                "workflow_id": workflow.id,
                "state": "running",
                "context": context or "{}",
                "started_at": fields_datetime_now(),
            }
        )

        from ..services.engine import WorkflowEngine

        engine = WorkflowEngine(request.env)
        try:
            engine.run(execution)
        except Exception as exc:  # noqa: BLE001 - errores inesperados se reportan al cliente
            _logger.exception("Error ejecutando workflow %s", workflow_id)
            # Rollback para limpiar transacción abortada por error de nodo
            try:
                request.env.cr.rollback()
            except Exception:  # noqa: BLE001
                pass
            # Crear registro de error en cursor aislado (conexión ya limpia tras rollback)
            try:
                new_cr = request.env.cr.new_cursor()
                new_env = request.env(cr=new_cr)
                new_env["aiws.execution"].create(
                    {
                        "workflow_id": workflow.id,
                        "state": "error",
                        "error_message": str(exc),
                        "context": context or "{}",
                        "started_at": fields_datetime_now(),
                        "finished_at": fields_datetime_now(),
                    }
                )
                new_cr.commit()
                new_cr.close()
            except Exception:  # noqa: BLE001
                pass
            # Dejar conexión limpia antes del flush de Odoo
            try:
                request.env.cr.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                request.env.cr.commit()
            except Exception:  # noqa: BLE001
                pass
            return {"error": "execution_error", "message": str(exc)}

        if execution.state == "error":
            return {
                "error": "execution_error",
                "message": execution.error_message or "Error ejecutando el workflow",
            }

        return {
            "execution_id": execution.id,
            "state": execution.state,
        }

    @http.route("/aiws/webhook/<int:workflow_id>", type="http", auth="public", csrf=False, methods=["POST"])
    def webhook(self, workflow_id, **post):
        """Punto de entrada público para disparar un workflow por webhook.

        La ejecución se ejecuta con el usuario público (sin privilegios extra).
        Valida HMAC-SHA256 signature si el workflow tiene webhook_secret configurado.
        """
        workflow = request.env["aiws.workflow"].sudo().browse(workflow_id)
        if not workflow.exists() or not workflow.active:
            return request.make_response(json.dumps({"error": "workflow_not_found"}), status=404)

        # Get raw payload
        payload = request.httprequest.get_data(as_text=True)
        
        # Validate HMAC signature if webhook_secret is set
        signature_header = request.httprequest.headers.get("X-AIWS-Signature", "")
        if workflow.webhook_secret:
            if not workflow.validate_webhook_signature(payload, signature_header):
                _logger.warning("Invalid HMAC signature for webhook workflow %s", workflow_id)
                return request.make_response(json.dumps({"error": "invalid_signature"}), status=401)

        context = {}
        if payload:
            try:
                context = json.loads(payload)
            except Exception:  # noqa: BLE001
                context = {"raw": payload}

        # Disparador anónimo: la ejecución se inicia con el usuario del sistema
        Execution = request.env["aiws.execution"].sudo()
        execution = Execution.create(
            {
                "workflow_id": workflow.id,
                "state": "running",
                "context": json.dumps(context),
                "started_at": fields_datetime_now(),
            }
        )

        from ..services.engine import WorkflowEngine
        from odoo import SUPERUSER_ID

        # Ejecutar motor con superuser para que pueda crear logs como sistema
        engine = WorkflowEngine(request.env(user=SUPERUSER_ID))
        try:
            engine.run(execution)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Webhook execution failed for workflow %s", workflow_id)
            return request.make_response(json.dumps({"error": "execution_error", "message": str(exc)}), status=500)

        return request.make_response(json.dumps({"execution_id": execution.id, "state": execution.state}), headers={"Content-Type": "application/json"})

    @http.route("/aiws/node/webhook/call", type="jsonrpc", auth="user")
    def call_webhook(self, url, method="GET", headers=None, json=None, timeout=WEBHOOK_TIMEOUT_SECONDS):
        """Llama a un webhook externo desde el nodo Webhook con protección SSRF.

        Soporta headers, JSON payload, y métodos GET/POST/PUT/DELETE.
        Solo accesible desde el servidor (motor de ejecución).
        """
        headers = headers or {}
        json_payload = json or {}

        parsed = urlparse(url)
        host = parsed.hostname or ""
        if any(host.startswith(prefix) for prefix in BLOCKED_IP_PREFIXES):
            raise UserError("Webhook bloqueado: dirección IP no permitida (SSRF).")
        if parsed.scheme not in ("http", "https"):
            raise UserError("Esquema no permitido: use http o https.")

        # Preparar datos
        data = None
        if json_payload:
            data = json.dumps(json_payload).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

        # Headers por defecto
        final_headers = {"User-Agent": "Odoo-AIWS/1.0"}
        final_headers.update(headers)

        try:
            req = urllib.request.Request(url, data=data, headers=final_headers, method=method.upper())
            with urllib.request.urlopen(req, timeout=min(int(timeout), WEBHOOK_TIMEOUT_SECONDS)) as response:
                content = response.read(WEBHOOK_MAX_RESPONSE_BYTES)
                return {
                    "status_code": response.status,
                    "body": content.decode("utf-8", errors="replace"),
                    "headers": dict(response.headers),
                }
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Webhook call failed to %s", url)
            raise UserError("Error llamando al webhook: %s" % exc)

    @http.route("/aiws/editor/<int:workflow_id>", type="http", auth="user")
    def editor(self, workflow_id):
        """Página del editor visual OWL para un workflow (standalone, sin WebClient)."""
        workflow = request.env["aiws.workflow"].browse(workflow_id)
        if not workflow.exists():
            return request.not_found()
        csrf_token = request.csrf_token(None)
        session_info = request.env["ir.http"].session_info()
        debug = bool(tools.config.options.get("debug_mode"))
        import logging as _logging
        _logger_editor = _logging.getLogger(__name__ + ".editor")
        _logger_editor.warning("AIWS EDITOR CONTROLLER CALLED for workflow %s", workflow.id)

        html = """<!DOCTYPE html>
<html>
<head>
    <title>AIWS Editor</title>
    <meta name="csrf_token" content="%s"/>
    <script type="text/javascript">
        window.odoo = {
            csrf_token: "%s",
            debug: %s,
            __session_info__: %s,
        };
    </script>
    <link rel="stylesheet" type="text/css" href="/aiws/static/editor.css"/>
    <script type="text/javascript" src="/aiws/static/owl.js"></script>
    <script type="text/javascript" src="/aiws/static/editor_standalone.js"></script>
</head>
<body>
    <div id="aiws-editor-root" data-workflow-id="%s"></div>
</body>
</html>""" % (
            csrf_token,
            csrf_token,
            "true" if debug else "false",
            json.dumps(session_info),
            workflow.id,
        )
        _logger_editor.warning("AIWS EDITOR: returning HTML response, length=%d", len(html))
        return request.make_response(
            html,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                ("X-Content-Type-Options", "nosniff"),
                ("Cache-Control", "no-cache, no-store, must-revalidate"),
                ("Pragma", "no-cache"),
                ("Expires", "0"),
            ],
        )

    @http.route(
        "/aiws/static/<path:filename>", type="http", auth="public"
    )
    def aiws_static(self, filename, **kw):
        """Sirve archivos estáticos del addon (OWL, editor JS) sin bundle de Odoo."""
        import mimetypes
        import os
        import logging as _logging
        _logger_static = _logging.getLogger(__name__ + ".static")

        addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(addon_dir, "static", "src", "editor", filename)
        _logger_static.warning("AIWS STATIC REQUEST: filename=%s, path=%s, exists=%s", filename, file_path, os.path.isfile(file_path))
        if not os.path.isfile(file_path):
            return request.not_found()
        content_type, _ = mimetypes.guess_type(file_path)
        with open(file_path, "rb") as f:
            content = f.read()
        return request.make_response(
            content,
            headers=[
                ("Content-Type", content_type or "application/octet-stream"),
                ("X-Content-Type-Options", "nosniff"),
                ("Cache-Control", "no-cache, no-store, must-revalidate"),
            ],
        )
