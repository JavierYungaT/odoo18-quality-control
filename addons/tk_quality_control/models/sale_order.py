from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    tk_quality_alert_ids = fields.One2many(
        "tk.quality.alert", "sale_order_id", string="Quality Alerts"
    )
    tk_quality_alert_count = fields.Integer(compute="_compute_tk_quality_alert_count")

    @api.depends("tk_quality_alert_ids")
    def _compute_tk_quality_alert_count(self):
        for order in self:
            order.tk_quality_alert_count = len(order.sudo().tk_quality_alert_ids)

    def action_tk_report_quality_issue(self):
        """Open a customer complaint pre-filled from the order."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Customer Complaint"),
            "res_model": "tk.quality.alert",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_origin": "customer",
                "default_sale_order_id": self.id,
                "default_partner_id": self.partner_id.commercial_partner_id.id,
                "default_product_id": self.order_line.product_id[:1].id,
                "default_title": _("Customer complaint on %s", self.name),
                "default_company_id": self.company_id.id,
            },
        }

    def action_tk_view_quality_alerts(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_alert"
        )
        action["domain"] = [("sale_order_id", "=", self.id)]
        action["context"] = {
            "default_origin": "customer",
            "default_sale_order_id": self.id,
            "default_partner_id": self.partner_id.commercial_partner_id.id,
        }
        return action
