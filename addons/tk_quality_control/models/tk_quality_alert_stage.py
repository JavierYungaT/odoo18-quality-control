from odoo import fields, models


class TkQualityAlertStage(models.Model):
    _name = "tk.quality.alert.stage"
    _description = "Quality Alert Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(string="Folded in Kanban")
    is_closed = fields.Boolean(
        string="Closing Stage",
        help="Alerts in this stage are considered solved. A root cause and a "
        "corrective action are required to reach it.",
    )
    description = fields.Text(translate=True)
