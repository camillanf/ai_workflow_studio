from odoo import models, fields, api
from odoo.exceptions import ValidationError
import hmac
import hashlib


class AiwsWorkflow(models.Model):
    _name = "aiws.workflow"
    _description = "AIWS Workflow"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    model = fields.Char(
        string="Target Model",
        help="Odoo model on which the workflow operates (e.g. sale.order). Leave empty for global workflows.",
    )
    active = fields.Boolean(string="Active", default=True)
    is_trigger_enabled = fields.Boolean(string="Scheduled Trigger Enabled", default=False)
    trigger_interval_minutes = fields.Integer(string="Trigger Interval (minutes)", default=60)
    webhook_secret = fields.Char(string="Webhook Secret", groups="ai_workflow_studio.aiws_group_admin", help="Secret key for HMAC validation of incoming webhooks")
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company, index=True
    )
    node_ids = fields.One2many("aiws.node", "workflow_id", string="Nodes")
    connection_ids = fields.One2many("aiws.connection", "workflow_id", string="Connections")
    start_node_id = fields.Many2one("aiws.node", string="Start Node", compute="_compute_start_node", store=True)
    cron_id = fields.Many2one("ir.cron", string="Scheduled Cron", readonly=True, copy=False, ondelete="set null")

    @api.depends("node_ids.node_type", "node_ids.active")
    def _compute_start_node(self):
        for workflow in self:
            start_nodes = workflow.node_ids.filtered(lambda n: n.node_type == "start" and n.active)
            workflow.start_node_id = start_nodes[0].id if start_nodes else False

    def action_run(self):
        """Manual execution entry point from the client action/button.
        Creates the execution record and runs the workflow engine synchronously.
        """
        self.ensure_one()
        execution = self.env["aiws.execution"].create(
            {
                "workflow_id": self.id,
                "state": "running",
                "context": "{}",
                "started_at": fields.Datetime.now(),
            }
        )
        # Run the workflow engine synchronously
        from ..services.engine import WorkflowEngine

        engine = WorkflowEngine(self.env)
        try:
            engine.run(execution)
        except Exception as exc:  # noqa: BLE001 - evitar que la excepción suba y aborte la transacción HTTP
            _logger.exception("Error ejecutando workflow %s", self.id)
            # Rollback para limpiar transacción abortada por el error del nodo
            try:
                self.env.cr.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                execution.write(
                    {
                        "state": "error",
                        "error_message": str(exc),
                        "finished_at": fields.Datetime.now(),
                    }
                )
            except Exception:  # transacción abortada, usar cursor nuevo
                try:
                    new_cr = self.env.cr.new_cursor()
                    new_env = self.env(cr=new_cr)
                    new_env["aiws.execution"].browse(execution.id).sudo().write(
                        {
                            "state": "error",
                            "error_message": str(exc),
                            "finished_at": fields.Datetime.now(),
                        }
                    )
                    new_cr.commit()
                    new_cr.close()
                except Exception:  # noqa: BLE001
                    pass
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error ejecutando workflow",
                    "message": str(exc),
                    "type": "danger",
                    "sticky": False,
                },
            }

        if execution.state == "error":
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Workflow terminó con error",
                    "message": execution.error_message or "Error ejecutando el workflow",
                    "type": "warning",
                    "sticky": False,
                },
            }

        return {
            "type": "ir.actions.act_window",
            "res_model": "aiws.execution",
            "res_id": execution.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_editor(self):
        """Abre el editor visual OWL del workflow."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/aiws/editor/%s" % self.id,
            "target": "new",
        }

    # ------------------------------------------------------------------
    # Cron management for scheduled triggers
    # ------------------------------------------------------------------
    def _get_cron_vals(self):
        """Prepare vals for creating/updating the ir.cron record."""
        self.ensure_one()
        # Odoo 19 uses ir.cron.trigger with remaining/done fields instead of numbercall
        # For infinite runs, we don't set a trigger with remaining limit
        return {
            "name": "AIWS: %s" % self.name,
            "model_id": self.env["ir.model"]._get("aiws.workflow").id,
            "state": "code",
            "code": "model.action_run_cron(%d)" % self.id,
            "interval_type": "minutes",
            "interval_number": self.trigger_interval_minutes or 60,
            "active": self.is_trigger_enabled and self.active,
            "user_id": self.env.user.id,
        }

    def _create_or_update_cron(self):
        """Create or update the ir.cron record based on trigger fields."""
        for workflow in self:
            if workflow.cron_id:
                # Update existing cron
                workflow.cron_id.write(workflow._get_cron_vals())
            elif workflow.is_trigger_enabled:
                # Create new cron
                cron = self.env["ir.cron"].create(workflow._get_cron_vals())
                workflow.cron_id = cron.id

    def _remove_cron(self):
        """Remove the associated cron record."""
        for workflow in self:
            if workflow.cron_id:
                workflow.cron_id.unlink()
                workflow.cron_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._create_or_update_cron()
        return records

    def write(self, vals):
        # Track if trigger fields are changing
        trigger_fields = {"is_trigger_enabled", "trigger_interval_minutes", "active", "name"}
        needs_cron_update = bool(trigger_fields & set(vals.keys()))
        result = super().write(vals)
        if needs_cron_update:
            self._create_or_update_cron()
        return result

    def unlink(self):
        self._remove_cron()
        return super().unlink()

    def action_run_cron(self, workflow_id=None):
        """Entry point called by ir.cron to run the workflow on schedule.

        ir.cron invoca: model.action_run_cron(<workflow_id>) con el id del workflow.
        """
        if workflow_id:
            self = self.browse(workflow_id)
        self.ensure_one()
        if not self.active or not self.is_trigger_enabled:
            return
        execution = self.env["aiws.execution"].create(
            {
                "workflow_id": self.id,
                "state": "running",
                "context": "{}",
                "started_at": fields.Datetime.now(),
            }
        )
        from ..services.engine import WorkflowEngine
        engine = WorkflowEngine(self.env)
        try:
            engine.run(execution)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Error en cron para workflow %s", self.id)
            try:
                self.env.cr.rollback()
            except Exception:  # noqa: BLE001
                pass
            try:
                execution.write(
                    {
                        "state": "error",
                        "error_message": str(exc),
                        "finished_at": fields.Datetime.now(),
                    }
                )
            except Exception:  # noqa: BLE001
                try:
                    new_cr = self.env.cr.new_cursor()
                    new_env = self.env(cr=new_cr)
                    new_env["aiws.execution"].browse(execution.id).sudo().write(
                        {
                            "state": "error",
                            "error_message": str(exc),
                            "finished_at": fields.Datetime.now(),
                        }
                    )
                    new_cr.commit()
                    new_cr.close()
                except Exception:  # noqa: BLE001
                    pass
        return True

    def validate_webhook_signature(self, payload, signature_header):
        """Validate HMAC-SHA256 signature of webhook payload.
        
        Args:
            payload: Raw request body as bytes or string
            signature_header: Value of X-AIWS-Signature header (format: sha256=<hex>)
        
        Returns:
            True if valid, False otherwise
        """
        if not self.webhook_secret:
            return False
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected_signature = "sha256=" + hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload if isinstance(payload, bytes) else payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature_header)
