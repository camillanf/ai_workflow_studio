from odoo import models, fields


class AiwsExecutionLog(models.Model):
    _name = "aiws.execution_log"
    _description = "AIWS Execution Log"
    _order = "executed_at, id"

    execution_id = fields.Many2one(
        "aiws.execution", string="Execution", required=True, ondelete="cascade", index=True
    )
    node_id = fields.Many2one("aiws.node", string="Node", required=True, index=True)
    node_type = fields.Char(string="Node Type", readonly=True)
    input_data = fields.Text(string="Input (JSON)", readonly=True)
    output_data = fields.Text(string="Output (JSON)", readonly=True)
    state = fields.Selection([("done", "Done"), ("error", "Error")], string="State", default="done", readonly=True)
    error_message = fields.Text(string="Error Message", readonly=True)
    duration_seconds = fields.Float(string="Duration (s)", readonly=True)
    executed_at = fields.Datetime(string="Executed at", readonly=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="execution_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
