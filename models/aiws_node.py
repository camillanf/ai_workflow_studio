from odoo import models, fields, api
from odoo.exceptions import UserError


class AiwsNode(models.Model):
    _name = "aiws.node"
    _description = "AIWS Node"
    _order = "sequence, id"

    ADMIN_ONLY_TYPES = ("python_script",)

    def _check_admin_only(self):
        for node in self:
            if node.node_type in self.ADMIN_ONLY_TYPES and not self.env.user.has_group(
                "ai_workflow_studio.aiws_group_admin"
            ):
                raise UserError(
                    "Solo los administradores pueden crear o editar nodos de tipo Script Python."
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_admin_only()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._check_admin_only()
        return result

    NODE_TYPES = [
        ("start", "Start"),
        ("end", "End"),
        ("condition", "Condition"),
        ("odoo_action", "Odoo Action"),
        ("webhook", "Webhook"),
        ("mail", "Mail"),
        ("python_script", "Python Script"),
        ("ai_agent", "AI Agent"),
    ]

    workflow_id = fields.Many2one(
        "aiws.workflow", string="Workflow", required=True, ondelete="cascade", index=True
    )
    name = fields.Char(string="Name", required=True)
    node_type = fields.Selection(NODE_TYPES, string="Type", required=True)
    configuration = fields.Text(string="Configuration (JSON)")
    position_x = fields.Integer(string="Position X", default=0)
    position_y = fields.Integer(string="Position Y", default=0)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    condition = fields.Text(string="Condition (safe expression)", help="Condition evaluated when this is a Condition node. Must return True or False.")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="workflow_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
