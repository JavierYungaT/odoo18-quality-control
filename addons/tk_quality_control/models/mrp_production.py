from odoo import api, fields, models

from .stock_picking import QUALITY_STATES, _check_quality_before_done, _quality_state


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    tk_quality_check_ids = fields.One2many(
        "tk.quality.check", "production_id", string="Quality Checks"
    )
    tk_quality_check_count = fields.Integer(compute="_compute_tk_quality")
    tk_quality_state = fields.Selection(
        QUALITY_STATES, string="Quality Status", compute="_compute_tk_quality"
    )

    @api.depends("tk_quality_check_ids.state")
    def _compute_tk_quality(self):
        for production in self:
            checks = production.sudo().tk_quality_check_ids
            production.tk_quality_check_count = len(checks)
            production.tk_quality_state = _quality_state(checks)

    def _tk_generate_quality_checks(self):
        """Inspect the finished product of each manufacturing order."""
        Point = self.env["tk.quality.point"].sudo()
        vals_list = []
        for production in self.filtered(lambda p: p.state not in ("done", "cancel")):
            existing = production.sudo().tk_quality_check_ids.point_id
            points = Point._get_points(production.picking_type_id, production.company_id)
            for point in points - existing:
                if point._applies_to(production.product_id):
                    vals_list.append({
                        "point_id": point.id,
                        "product_id": production.product_id.id,
                        "lot_id": production.lot_producing_id.id,
                        "production_id": production.id,
                        "company_id": production.company_id.id,
                    })
        return self.env["tk.quality.check"].sudo().create(vals_list)

    def button_mark_done(self):
        _check_quality_before_done(self, "tk_quality_check_ids")
        return super().button_mark_done()

    def action_tk_view_quality_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_check"
        )
        action["domain"] = [("production_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
