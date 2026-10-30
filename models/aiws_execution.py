from odoo import models, fields


class AiwsExecution(models.Model):
    _name = "aiws.execution"
    _description = "AIWS Execution"
    _order = "started_at desc, id desc"

    STATE = [("running", "Running"), ("done", "Done"), ("error", "Error")]

    workflow_id = fields.Many2one(
        "aiws.workflow", string="Workflow", required=True, ondelete="cascade", index=True
    )
    state = fields.Selection(STATE, string="State", default="running", readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
    context = fields.Text(string="Context (JSON)")
    res_model = fields.Char(string="Target Model")
    res_id = fields.Integer(string="Target Record ID")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="workflow_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    started_at = fields.Datetime(string="Started at", readonly=True)
    finished_at = fields.Datetime(string="Finished at", readonly=True)
    duration_seconds = fields.Float(string="Duration (s)", compute="_compute_duration", readonly=True)
    log_ids = fields.One2many("aiws.execution_log", "execution_id", string="Logs")

    def _compute_duration(self):
        for execution in self:
            if execution.started_at and execution.finished_at:
                delta = execution.finished_at - execution.started_at
                execution.duration_seconds = delta.total_seconds()
            else:
                execution.duration_seconds = 0.0

    def action_run(self):
        """Ejecuta el workflow de forma síncrona (botón Ejecutar/Reintentar).

        Crea una NUEVA ejecución (copia) para no mezclar logs de reintentos.
        """
        self.ensure_one()
        # Crear nueva ejecución clonando la actual
        new_execution = self.env["aiws.execution"].create({
            "workflow_id": self.workflow_id.id,
            "state": "running",
            "context": self.context,
            "started_at": fields.Datetime.now(),
        })
        from ..services.engine import WorkflowEngine
        engine = WorkflowEngine(self.env)
        engine.run(new_execution)
        return {
            "type": "ir.actions.act_window",
            "res_model": "aiws.execution",
            "res_id": new_execution.id,
            "view_mode": "form",
            "target": "current",
        }

