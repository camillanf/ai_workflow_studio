from odoo import models, fields


class AiwsConnection(models.Model):
    _name = "aiws.connection"
    _description = "AIWS Connection"
    _order = "sequence, id"

    workflow_id = fields.Many2one(
        "aiws.workflow", string="Workflow", required=True, ondelete="cascade", index=True
    )
    source_node_id = fields.Many2one(
        "aiws.node", string="Source Node", required=True, ondelete="cascade", index=True
    )
    target_node_id = fields.Many2one(
        "aiws.node", string="Target Node", required=True, ondelete="cascade", index=True
    )
    label = fields.Char(string="Label")
    condition = fields.Text(string="Condition (safe expression)", help="Legacy condition field. For Condition nodes, use the node's condition field instead.")
    branch = fields.Selection([
        ("true", "True"),
        ("false", "False"),
    ], string="Branch", help="For connections from a Condition node: True branch or False branch.")
    sequence = fields.Integer(string="Sequence", default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="workflow_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
