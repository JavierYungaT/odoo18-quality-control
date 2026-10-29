from odoo import api, fields, models
from odoo.exceptions import UserError

QUALITY_STATES = [
    ("none", "No Checks"),
    ("pending", "To Do"),
    ("fail", "Failed"),
    ("pass", "Passed"),
]


def _quality_state(checks):
    if not checks:
        return "none"
    states = set(checks.mapped("state"))
    if "pending" in states:
        return "pending"
    if "fail" in states:
        return "fail"
    return "pass"


def _check_quality_before_done(records, checks_field):
    """Block the validation of ``records`` while their checks are not done,
    or when a failed check has no quality alert registered."""
    for record in records:
        checks = record.sudo()[checks_field]
        pending = checks.filtered(lambda c: c.state == "pending")
        if pending:
            raise UserError(
                records.env._("%(record)s still has quality checks to do: %(checks)s",
                              record=record.display_name,
                              checks=", ".join(pending.mapped("name")))
            )
        failed = checks.filtered(lambda c: c.state == "fail" and not c.alert_ids)
        if failed:
            raise UserError(
                records.env._("%(record)s has failed quality checks without a quality alert: "
                              "%(checks)s. Register the non-conformity before validating.",
                              record=record.display_name,
                              checks=", ".join(failed.mapped("name")))
            )


class StockPicking(models.Model):
    _inherit = "stock.picking"

    tk_quality_check_ids = fields.One2many(
        "tk.quality.check", "picking_id", string="Quality Checks"
    )
    tk_quality_check_count = fields.Integer(compute="_compute_tk_quality")
    tk_quality_state = fields.Selection(
        QUALITY_STATES, string="Quality Status", compute="_compute_tk_quality"
    )

    @api.depends("tk_quality_check_ids.state")
    def _compute_tk_quality(self):
        for picking in self:
            checks = picking.sudo().tk_quality_check_ids
            picking.tk_quality_check_count = len(checks)
            picking.tk_quality_state = _quality_state(checks)

    def _tk_generate_quality_checks(self):
        Point = self.env["tk.quality.point"].sudo()
        vals_list = []
        for picking in self.filtered(lambda p: p.state not in ("done", "cancel")):
            points = Point._get_points(picking.picking_type_id, picking.company_id)
            if not points:
                continue
            existing = {
                (check.point_id.id, check.product_id.id)
                for check in picking.sudo().tk_quality_check_ids
            }
            for product in picking.move_ids.product_id:
                for point in points.filtered(lambda p: p._applies_to(product)):
                    if (point.id, product.id) in existing:
                        continue
                    existing.add((point.id, product.id))
                    vals_list.append({
                        "point_id": point.id,
                        "product_id": product.id,
                        "picking_id": picking.id,
                        "company_id": picking.company_id.id,
                    })
        return self.env["tk.quality.check"].sudo().create(vals_list)

    def button_validate(self):
        _check_quality_before_done(self, "tk_quality_check_ids")
        return super().button_validate()

    def _create_backorder(self, backorder_moves=None):
        """The moves of a backorder are already confirmed when they are moved
        to it, so its checks have to be generated here."""
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        backorders._tk_generate_quality_checks()
        return backorders

    def action_tk_view_quality_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_check"
        )
        action["domain"] = [("picking_id", "=", self.id)]
        action["context"] = {"create": False}
        return action
