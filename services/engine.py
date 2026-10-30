import json
import logging
from datetime import datetime

from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Motor de ejecución de flujos de trabajo.

    Patrón de estrategia por tipo de nodo. Toda la lógica es síncrona;
    la ejecución programada se dispara desde ir.cron y llama a este motor.
    """

    MAX_STEPS = 100
    MAX_DURATION_SECONDS = 300
    MAX_STEP_DURATION_SECONDS = 30
    MAX_RETRIES = 3

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------
    # Validación de grafo
    # ------------------------------------------------------------------
    def validate_graph(self, workflow):
        """Valida que el grafo del workflow sea ejecutable.

        Devuelve una lista de errores estructurados (vacía si es válido).
        Cada error es un dict con: type, message, node_id, connection_id.
        """
        errors = []
        nodes = workflow.node_ids.filtered(lambda n: n.active)
        start_nodes = nodes.filtered(lambda n: n.node_type == "start")
        end_nodes = nodes.filtered(lambda n: n.node_type == "end")

        if len(start_nodes) != 1:
            errors.append({
                "type": "node",
                "node_id": start_nodes[0].id if start_nodes else None,
                "message": "El workflow debe tener exactamente un nodo de tipo Inicio.",
            })
        if not end_nodes:
            errors.append({
                "type": "node",
                "node_id": None,
                "message": "El workflow debe tener al menos un nodo de tipo Fin.",
            })

        if not nodes:
            return errors

        # Detección de ciclos con DFS sobre conexiones.
        # Solo considerar conexiones entre nodos activos.
        active_node_ids = set(nodes.ids)
        adjacency = {}
        connection_map = {}  # (source, target) -> connection_id
        for connection in workflow.connection_ids:
            if connection.source_node_id.id in active_node_ids and connection.target_node_id.id in active_node_ids:
                adjacency.setdefault(connection.source_node_id.id, []).append(
                    connection.target_node_id.id
                )
                connection_map[(connection.source_node_id.id, connection.target_node_id.id)] = connection.id
        visited = set()
        stack = set()
        cycle_path = []

        def dfs(node_id):
            nonlocal cycle_path
            if node_id in stack:
                # Encontrar el ciclo
                idx = cycle_path.index(node_id)
                cycle_path = cycle_path[idx:]
                return True  # ciclo
            if node_id in visited:
                return False
            visited.add(node_id)
            stack.add(node_id)
            cycle_path.append(node_id)
            for target in adjacency.get(node_id, []):
                if dfs(target):
                    return True
            stack.remove(node_id)
            cycle_path.pop()
            return False

        for node in nodes:
            if node.id not in visited:
                cycle_path = [node.id]
                if dfs(node.id):
                    # Construir error con info del ciclo
                    cycle_edges = []
                    for i in range(len(cycle_path)):
                        src = cycle_path[i]
                        tgt = cycle_path[(i + 1) % len(cycle_path)]
                        conn_id = connection_map.get((src, tgt))
                        if conn_id:
                            cycle_edges.append(conn_id)
                    errors.append({
                        "type": "cycle",
                        "node_id": cycle_path[0],
                        "connection_id": cycle_edges[0] if cycle_edges else None,
                        "message": "El grafo contiene un ciclo. Los flujos deben ser acíclicos.",
                        "cycle_nodes": cycle_path,
                        "cycle_connections": cycle_edges,
                    })
                    break

        return errors

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------
    def run(self, execution):
        """Ejecuta un workflow hasta un nodo Fin o error.

        Crea/actualiza aiws.execution_log por nodo recorrido.
        """
        workflow = execution.workflow_id
        errors = self.validate_graph(workflow)
        if errors:
            # Extraer mensajes de errores estructurados
            messages = []
            for err in errors:
                if isinstance(err, dict):
                    messages.append(err.get("message", str(err)))
                else:
                    messages.append(str(err))
            message = "; ".join(messages)
            execution.write(
                {
                    "state": "error",
                    "error_message": message,
                    "finished_at": datetime.now(),
                }
            )
            _logger.error("Validación falló para ejecución %s: %s", execution.id, message)
            return

        context = {}
        if execution.context:
            try:
                context = json.loads(execution.context) or {}
            except Exception:  # noqa: BLE001 - contexto inválido, se parte de cero
                context = {}

        current = workflow.start_node_id
        steps = 0
        start_time = datetime.now()

        while current:
            steps += 1
            if steps > self.MAX_STEPS:
                self._fail(execution, "Límite de pasos excedido (100).")
                return
            if (datetime.now() - start_time).total_seconds() > self.MAX_DURATION_SECONDS:
                self._fail(execution, "Tiempo máximo de ejecución excedido (300 s).")
                return

            node = current
            step_start = datetime.now()

            # Savepoint por nodo: un error en un nodo no aborta la transacción principal
            self.env.cr.execute("SAVEPOINT aiws_node_%s" % node.id)
            try:
                log = self.env["aiws.execution_log"].create(
                    {
                        "execution_id": execution.id,
                        "node_id": node.id,
                        "node_type": node.node_type,
                        "input_data": self._safe_json(context),
                        "state": "done",
                        "executed_at": step_start,
                    }
                )

                # Estrategia por tipo de nodo
                handler = getattr(self, "_handle_%s" % node.node_type, self._handle_unknown)
                outputs = handler(node, context, workflow)
                context = outputs.get("context", context)
                next_node_id = outputs.get("next_node_id")

                log.write(
                    {
                        "output_data": self._safe_json({k: v for k, v in outputs.items() if k not in ("context", "next_node_id")}),
                        "duration_seconds": (datetime.now() - step_start).total_seconds(),
                        "executed_at": step_start,
                    }
                )

                if node.node_type == "end":
                    execution.write({"state": "done", "finished_at": datetime.now()})
                    self.env.cr.execute("RELEASE SAVEPOINT aiws_node_%s" % node.id)
                    return

                if next_node_id is None and node.node_type != "condition":
                    # Por defecto se sigue la primera conexión saliente del nodo hacia un nodo activo.
                    outgoing = workflow.connection_ids.filtered(
                        lambda c: c.source_node_id.id == node.id and c.target_node_id.active
                    ).sorted("sequence")
                    next_node_id = outgoing[0].target_node_id.id if outgoing else None

                # Liberar savepoint del nodo ejecutado con éxito
                self.env.cr.execute("RELEASE SAVEPOINT aiws_node_%s" % node.id)

            except Exception as exc:  # noqa: BLE001 - errores de nodo se capturan por nodo
                _logger.exception("Error ejecutando nodo %s", node.name)
                # Rollback al savepoint: deshace cambios del nodo fallido, mantiene la transacción viva
                try:
                    self.env.cr.execute("ROLLBACK TO SAVEPOINT aiws_node_%s" % node.id)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self.env.cr.execute("RELEASE SAVEPOINT aiws_node_%s" % node.id)
                except Exception:  # noqa: BLE001
                    pass

                # Actualizar log como error (usa cursor aislado si es necesario)
                try:
                    log.write(
                        {
                            "state": "error",
                            "error_message": str(exc),
                            "duration_seconds": (datetime.now() - step_start).total_seconds(),
                            "executed_at": step_start,
                        }
                    )
                except Exception:  # noqa: BLE001
                    try:
                        new_cr = self.env.cr.new_cursor()
                        new_env = self.env(cr=new_cr)
                        new_env["aiws.execution_log"].browse(log.id).sudo().write(
                            {
                                "state": "error",
                                "error_message": str(exc),
                                "duration_seconds": (datetime.now() - step_start).total_seconds(),
                                "executed_at": step_start,
                            }
                        )
                        new_cr.commit()
                        new_cr.close()
                    except Exception:  # noqa: BLE001
                        pass
                self._fail(execution, "Error en nodo '%s': %s" % (node.name, exc))
                return

            current = self.env["aiws.node"].browse(next_node_id) if next_node_id else None
            # Evitar bucles en tiempo de ejecución (defensa en profundidad)
            if current and current.id in {n.id for n in self._visited_nodes(execution)}:
                self._fail(execution, "Bucle detectado en tiempo de ejecución.")
                return

        execution.write({"state": "error", "finished_at": datetime.now()})

    # ------------------------------------------------------------------
    # Handlers por tipo de nodo (estrategia)
    # ------------------------------------------------------------------
    def _handle_start(self, node, context, workflow):
        return {"context": context}

    def _handle_end(self, node, context, workflow):
        return {"context": context}

    # Whitelist de builtins permitidos para safe_eval en condiciones
    _SAFE_EVAL_BUILTINS = {
        "True": True,
        "False": False,
        "true": True,   # alias lowercase
        "false": False, # alias lowercase
        "None": None,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "sum": sum,
        "min": min,
        "max": max,
        "sorted": sorted,
        "enumerate": enumerate,
        "zip": zip,
        "range": range,
        "isinstance": isinstance,
        "hasattr": hasattr,
        "getattr": getattr,
        "abs": abs,
        "round": round,
        "all": all,
        "any": any,
    }

    def _handle_condition(self, node, context, workflow):
        """Evalúa la condición del nodo Condition y sigue la conexión por rama (True/False).

        La condición se almacena en el nodo (campo condition), no en las conexiones.
        Las conexiones salientes del nodo Condition deben tener el campo branch
        etiquetado como 'true' o 'false' para indicar qué rama tomar.
        """
        condition_expr = node.condition or ""
        result = False

        if condition_expr:
            try:
                safe_globals = {
                    "__builtins__": self._SAFE_EVAL_BUILTINS,
                    "context": context,
                    "true": True,
                    "false": False,
                }
                result = safe_eval.safe_eval(condition_expr, safe_globals)
            except Exception:  # noqa: BLE001
                _logger.warning("Error evaluando condición en nodo %s", node.id)
                result = False

        branch_label = "true" if result else "false"
        _logger.info(
            "Nodo Condition %s: condición=%s resultado=%s rama=%s",
            node.id, condition_expr, result, branch_label,
        )

        connections = workflow.connection_ids.filtered(
            lambda c: c.source_node_id.id == node.id and c.target_node_id.active and c.branch == branch_label
        ).sorted("sequence")

        if connections:
            return {"context": context, "next_node_id": connections[0].target_node_id.id}

        # Si no hay conexión con branch coincidente, intentar con cualquier conexión saliente
        # (compatibilidad hacia atrás para workflows sin branch)
        outgoing = workflow.connection_ids.filtered(
            lambda c: c.source_node_id.id == node.id and c.target_node_id.active
        ).sorted("sequence")
        if outgoing:
            return {"context": context, "next_node_id": outgoing[0].target_node_id.id}

        # Sin coincidencia: fin silencioso
        return {"context": context, "next_node_id": None}

    def _handle_odoo_action(self, node, context, workflow):
        """Ejecuta acción real sobre un modelo de Odoo.

        Configuración esperada (JSON):
        {
            "model": "res.partner",           # obligatorio (o workflow.model)
            "action": "create|write|unlink|search|call_method",
            "domain": [],                     # para search/write/unlink
            "values": {},                     # para create/write
            "method": "action_confirm",       # para call_method
            "args": [],                       # args para call_method
            "kwargs": {},                     # kwargs para call_method
            "limit": 1,                       # para search (default 1)
            "output_key": "records"           # clave para guardar en context
        }
        """
        configuration = self._safe_eval(node.configuration or "{}")
        model_name = configuration.get("model") or workflow.model
        action = configuration.get("action", "search")

        if not model_name:
            raise ValueError("Nodo Odoo Action: 'model' es obligatorio")

        try:
            Model = self.env[model_name]
        except KeyError:
            raise ValueError(f"Nodo Odoo Action: el modelo '{model_name}' no existe en Odoo")

        if action == "search":
            domain = self._safe_get(configuration, "domain", [])
            limit = int(configuration.get("limit") or 1)
            records = Model.search(domain, limit=limit)
            output_key = configuration.get("output_key", "records")
            return {
                "context": {**context, output_key: records.ids},
                "records": records.ids,
            }

        elif action == "create":
            values = self._safe_get(configuration, "values", {})
            # Resolver plantillas {{ ctx.key }} en values
            values = self._render_templates(values, context)
            record = Model.create(values)
            output_key = configuration.get("output_key", "record")
            return {
                "context": {**context, output_key: record.id},
                "record_id": record.id,
            }

        elif action == "write":
            domain = self._safe_get(configuration, "domain", [])
            values = self._safe_get(configuration, "values", {})
            values = self._render_templates(values, context)
            records = Model.search(domain)
            if not records:
                raise ValueError("Nodo Odoo Action (write): no se encontraron registros con el domain")
            records.write(values)
            output_key = configuration.get("output_key", "records")
            return {
                "context": {**context, output_key: records.ids},
                "records": records.ids,
            }

        elif action == "unlink":
            domain = self._safe_get(configuration, "domain", [])
            records = Model.search(domain)
            if not records:
                raise ValueError("Nodo Odoo Action (unlink): no se encontraron registros con el domain")
            count = len(records)
            records.unlink()
            return {"context": context, "deleted_count": count}

        elif action == "call_method":
            domain = self._safe_get(configuration, "domain", [])
            method_name = configuration.get("method")
            if not method_name:
                raise ValueError("Nodo Odoo Action (call_method): 'method' es obligatorio")
            args = self._safe_get(configuration, "args", [])
            kwargs = self._safe_get(configuration, "kwargs", {})
            records = Model.search(domain)
            if not records:
                raise ValueError("Nodo Odoo Action (call_method): no se encontraron registros con el domain")
            results = []
            for record in records:
                method = getattr(record, method_name, None)
                if not method:
                    raise ValueError("Método '%s' no existe en modelo '%s'" % (method_name, model_name))
                result = method(*args, **kwargs)
                results.append(result)
            output_key = configuration.get("output_key", "results")
            return {
                "context": {**context, output_key: results},
                "results": results,
            }

        else:
            raise ValueError("Acción Odoo desconocida: %s" % action)

    def _handle_webhook(self, node, context, workflow):
        """Llama a un webhook externo vía controlador interno (con protección SSRF).

        Configuración esperada (JSON):
        {
            "url": "https://api.ejemplo.com/endpoint",
            "method": "POST",              # GET, POST, PUT, DELETE
            "headers": {},                 # opcional
            "payload": {},                 # JSON body (para POST/PUT)
            "timeout": 10,                 # segundos (max 30)
            "output_key": "webhook_response"
        }
        """
        configuration = self._safe_eval(node.configuration or "{}")
        url = configuration.get("url")
        method = configuration.get("method", "POST").upper()
        headers = self._safe_get(configuration, "headers", {})
        payload = self._safe_get(configuration, "payload", {})
        timeout = int(configuration.get("timeout", 10))
        output_key = configuration.get("output_key", "webhook_response")

        if not url:
            raise ValueError("Nodo Webhook: 'url' es obligatorio")

        # Renderizar plantillas en payload/headers
        payload = self._render_templates(payload, context)
        headers = self._render_templates(headers, context)

        # Llamar al endpoint interno que valida SSRF
        try:
            result = self._call_webhook(url, method=method, headers=headers, json=payload, timeout=timeout)
        except Exception as exc:
            raise ValueError("Error llamando al webhook: %s" % exc)

        return {
            "context": {**context, output_key: result},
            "webhook_result": result,
        }

    def _handle_mail(self, node, context, workflow):
        """Envía un correo real usando mail.mail o mail.template.

        Configuración esperada (JSON):
        {
            "template_xmlid": "modulo.nombre_template",  # opcional: usa mail.template
            "email_to": "destino@ejemplo.com",           # obligatorio si no hay template
            "email_cc": "copia@ejemplo.com",             # opcional
            "subject": "Asunto del correo",
            "body_html": "<p>Cuerpo HTML</p>",           # si no hay template
            "body": "Cuerpo texto plano",                # alternativa a body_html
            "output_key": "mail_result"
        }
        """
        configuration = self._safe_eval(node.configuration or "{}")
        template_xmlid = configuration.get("template_xmlid")
        email_to = configuration.get("email_to")
        email_cc = configuration.get("email_cc")
        subject = configuration.get("subject")
        body_html = configuration.get("body_html")
        body = configuration.get("body")
        output_key = configuration.get("output_key", "mail_result")

        if not template_xmlid and not email_to:
            raise ValueError("Nodo Mail: 'email_to' o 'template_xmlid' es obligatorio")

        # Renderizar plantillas en campos de texto
        if email_to:
            email_to = self._render_template_str(email_to, context)
        if email_cc:
            email_cc = self._render_template_str(email_cc, context)
        if subject:
            subject = self._render_template_str(subject, context)
        if body_html:
            body_html = self._render_template_str(body_html, context)
        if body:
            body = self._render_template_str(body, context)

        Mail = self.env["mail.mail"]

        if template_xmlid:
            # Usar mail.template
            try:
                template = self.env.ref(template_xmlid, raise_if_not_found=False)
            except Exception:
                template = None
            if not template:
                raise ValueError("Template '%s' no encontrado" % template_xmlid)

            # Valores por defecto del template + overrides
            values = template.generate_email(res_ids=[0])[0]
            if email_to:
                values["email_to"] = email_to
            if email_cc:
                values["email_cc"] = email_cc
            if subject:
                values["subject"] = subject
            if body_html:
                values["body_html"] = body_html
            if body:
                values["body"] = body

            mail = Mail.create(values)
        else:
            # Crear mail.mail directamente
            if not subject:
                raise ValueError("Nodo Mail: 'subject' es obligatorio sin template")
            if not body_html and not body:
                raise ValueError("Nodo Mail: 'body_html' o 'body' es obligatorio sin template")

            mail = Mail.create({
                "email_to": email_to,
                "email_cc": email_cc,
                "subject": subject,
                "body_html": body_html or body,
                "body": body or body_html,
                "auto_delete": True,
            })

        mail.send()
        return {
            "context": {**context, output_key: {"mail_id": mail.id, "state": "sent"}},
            "mail_id": mail.id,
        }

    def _handle_python_script(self, node, context, workflow):
        """Ejecuta código Python en un entorno sandbox seguro.

        Configuración esperada (JSON):
        {
            "code": "result = ctx['records'][0] * 2\noutput = {'doubled': result}",
            "timeout": 5,              # segundos (máx 30)
            "output_key": "py_result"  # clave para guardar en context
        }

        El script tiene acceso a:
        - ctx: diccionario con el contexto de ejecución
        - output: dict donde escribir resultados (se devuelve en context)
        - safe builtins: len, str, int, float, bool, list, dict, tuple, set, sum, min, max, sorted, enumerate, zip, range, isinstance, hasattr, getattr

        Seguridad:
        - Sin acceso a __import__, open, eval, exec, compile, __builtins__
        - Sin acceso a filesystem, network, os, sys, subprocess
        - Timeout configurable (máx 30s)
        - Memoria y CPU limitadas por el proceso Odoo
        """
        configuration = self._safe_eval(node.configuration or "{}")
        code = configuration.get("code", "")
        timeout = min(int(configuration.get("timeout", 5)), 30)
        output_key = configuration.get("output_key", "py_result")

        if not code or not code.strip():
            raise ValueError("Nodo Python Script: 'code' es obligatorio")

        # Entorno seguro
        safe_globals = {
            "__builtins__": {
                "len": len, "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set,
                "sum": sum, "min": min, "max": max, "sorted": sorted,
                "enumerate": enumerate, "zip": zip, "range": range,
                "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
                "abs": abs, "round": round, "pow": pow, "divmod": divmod,
                "all": all, "any": any, "map": map, "filter": filter,
                "reversed": reversed, "slice": slice, "property": property,
                "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
                "KeyError": KeyError, "IndexError": IndexError,
            },
            "ctx": context,
            "output": {},
        }

        # Ejecutar con timeout
        import signal
        import threading

        result_container = {"output": {}, "error": None}

        def run_code():
            try:
                exec(code, safe_globals, safe_globals)
                result_container["output"] = safe_globals.get("output", {})
            except Exception as e:
                result_container["error"] = e

        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Timeout - no podemos matar el thread en Python, pero marcamos error
            raise ValueError("Python Script: timeout excedido (%ds)" % timeout)

        if result_container["error"]:
            raise ValueError("Python Script error: %s" % result_container["error"])

        output = result_container["output"]
        return {
            "context": {**context, output_key: output},
            "python_result": output,
        }

    def _handle_ai_agent(self, node, context, workflow):
        # Delegación en la capa de proveedores.
        import json as _json

        from .ai_provider import get_provider

        config = {}
        raw = node.configuration
        if isinstance(raw, dict):
            config = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                config = _json.loads(raw)
            except Exception:  # noqa: BLE001 - compatibilidad con literales Python
                config = self._safe_eval(raw)
        if not isinstance(config, dict):
            config = {}

        prompt = self._render_templates(config.get("prompt") or "", context)
        system_prompt = self._render_templates(config.get("system_prompt") or "", context)
        if not prompt:
            raise ValueError("El nodo AI Agent no tiene 'prompt' configurado")

        # Selección del proveedor: id explícito, nombre/tipo, o primer activo.
        provider_id = config.get("provider_id")
        provider_ref = config.get("provider")
        if not provider_id and isinstance(provider_ref, int):
            provider_id = provider_ref
            provider_ref = None

        provider = get_provider(
            self.env,
            provider_id=provider_id,
            provider_ref=provider_ref if not provider_id else None,
        )
        response = provider.generate(
            prompt=prompt,
            context=context,
            system_prompt=system_prompt,
        )

        output_key = config.get("output_variable") or config.get("output_key") or "ai_response"
        new_context = dict(context)
        new_context[output_key] = response.text
        # Alias estable para nodos que ya usaban ai_response
        new_context["ai_response"] = response.text

        return {
            "context": new_context,
            "ai_response": response.text,
            "ai_provider": response.provider,
            "ai_model": response.model,
            "ai_stub": response.stub,
        }

    def _handle_unknown(self, node, context, workflow):
        raise ValueError("Tipo de nodo desconocido: %s" % node.node_type)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _fail(self, execution, message):
        # La transacción puede estar abortada por el error del nodo.
        # Usamos un cursor nuevo para poder escribir el estado de error.
        try:
            execution.write(
                {
                    "state": "error",
                    "error_message": message,
                    "finished_at": datetime.now(),
                }
            )
        except Exception:  # noqa: BLE001 - transacción abortada, intentar con cursor nuevo
            try:
                new_cr = self.env.cr.new_cursor()
                new_env = self.env(cr=new_cr)
                new_env["aiws.execution"].browse(execution.id).sudo().write(
                    {
                        "state": "error",
                        "error_message": message,
                        "finished_at": datetime.now(),
                    }
                )
                new_cr.commit()
                new_cr.close()
            except Exception as exc:  # noqa: BLE001
                _logger.error("No se pudo actualizar estado de ejecución %s: %s", execution.id, exc)
        _logger.error("Ejecución %s falló: %s", execution.id, message)

    @staticmethod
    def _safe_json(value):
        import json

        try:
            return json.dumps(value, default=str)
        except Exception:  # noqa: BLE001
            return "{}"

    @staticmethod
    def _safe_eval(text):
        import json

        try:
            result = safe_eval.safe_eval(text, {})
            # Ensure dict/list for domain/values
            if result is None:
                return {}
            return result
        except Exception:  # noqa: BLE001
            return {}

    def _safe_get(self, config, key, default=None):
        """Obtiene un valor del config: si es string, hace _safe_eval; si ya es dict/list, lo usa tal cual.

        Esto evita pasar un dict ya parseado a _safe_eval (que espera un string),
        lo que causaba que el valor se perdiera y quedara vacío.
        """
        val = config.get(key, default)
        if isinstance(val, str):
            return self._safe_eval(val)
        return val if val is not None else default

    def _render_templates(self, obj, context):
        """Recursively render {{ ctx.key }} templates in dict/list/str using context."""
        if isinstance(obj, dict):
            return {k: self._render_templates(v, context) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._render_templates(v, context) for v in obj]
        if isinstance(obj, str):
            return self._render_template_str(obj, context)
        return obj

    def _render_template_str(self, text, context):
        """Render {{ ctx.key }} templates in a string using context."""
        if not isinstance(text, str):
            return text
        # Simple template replacement: {{ ctx.key }} -> context.get('key')
        import re
        def repl(match):
            key = match.group(1).strip()
            if key.startswith("ctx."):
                key = key[4:]
            return str(context.get(key, match.group(0)))
        return re.sub(r"\{\{\s*(.*?)\s*\}\}", repl, text)

    def _call_webhook(self, url, method="GET", headers=None, json=None, timeout=10):
        """Call internal webhook controller endpoint."""
        # Use the controller method via the registry
        from ..controllers.main import AiwsController
        controller = AiwsController()
        return controller.call_webhook(url, method=method, headers=headers or {}, json=json or {}, timeout=timeout)

    def _visited_nodes(self, execution):
        return execution.log_ids.mapped("node_id")
