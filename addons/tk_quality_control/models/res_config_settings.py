from odoo import fields, models

from .purchase_order import DEFAULT_MIN_SCORE


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tk_quality_supplier_min_score = fields.Integer(
        string="Minimum Supplier Score",
        config_parameter="tk_quality_control.supplier_min_score",
        default=DEFAULT_MIN_SCORE,
    )
