from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    tk_supplier_check_ids = fields.One2many(
        "tk.quality.check", "supplier_id", string="Supplier Quality Checks"
    )
    supplier_quality_check_count = fields.Integer(
        string="Inspected Receipts", compute="_compute_supplier_quality", store=True
    )
    supplier_quality_score = fields.Float(
        string="Supplier Quality Score",
        compute="_compute_supplier_quality",
        store=True,
        aggregator="avg",
        digits=(5, 1),
        help="Percentage of passed checks over all finished checks of this vendor.",
    )
    tk_quality_alert_count = fields.Integer(compute="_compute_tk_quality_alert_count")

    @api.depends("tk_supplier_check_ids.state")
    def _compute_supplier_quality(self):
        for partner in self:
            done = partner.tk_supplier_check_ids.filtered(lambda c: c.state in ("pass", "fail"))
            passed = done.filtered(lambda c: c.state == "pass")
            partner.supplier_quality_check_count = len(done)
            partner.supplier_quality_score = 100.0 * len(passed) / len(done) if done else 0.0

    def _compute_tk_quality_alert_count(self):
        counts = dict(self.env["tk.quality.alert"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"]
        ))
        for partner in self:
            partner.tk_quality_alert_count = counts.get(partner, 0)

    def action_tk_view_supplier_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_check"
        )
        action["domain"] = [("supplier_id", "=", self.id)]
        action["context"] = {"create": False, "search_default_done": 1}
        return action

    def action_tk_view_quality_alerts(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_alert"
        )
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
