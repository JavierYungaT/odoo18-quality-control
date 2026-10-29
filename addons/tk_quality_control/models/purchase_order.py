from odoo import api, fields, models

DEFAULT_MIN_SCORE = 80


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    supplier_quality_score = fields.Float(
        related="partner_id.commercial_partner_id.supplier_quality_score"
    )
    supplier_quality_check_count = fields.Integer(
        related="partner_id.commercial_partner_id.supplier_quality_check_count"
    )
    tk_show_quality_warning = fields.Boolean(compute="_compute_tk_show_quality_warning")

    @api.depends("supplier_quality_score", "supplier_quality_check_count")
    def _compute_tk_show_quality_warning(self):
        min_score = int(self.env["ir.config_parameter"].sudo().get_param(
            "tk_quality_control.supplier_min_score", DEFAULT_MIN_SCORE
        ))
        for order in self:
            order.tk_show_quality_warning = bool(
                order.supplier_quality_check_count
                and order.supplier_quality_score < min_score
            )
