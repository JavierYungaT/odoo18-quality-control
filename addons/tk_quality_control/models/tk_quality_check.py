from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_amount


class TkQualityCheck(models.Model):
    """One inspection of one product, generated from a quality point."""

    _name = "tk.quality.check"
    _description = "Quality Check"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New")
    )
    point_id = fields.Many2one(
        "tk.quality.point",
        string="Control Point",
        required=True,
        index=True,
        ondelete="restrict",
        check_company=True,
    )
    # Copied from the point when the check is created, so that changing the
    # point later does not rewrite the result of past inspections.
    test_type = fields.Selection(
        [("pass_fail", "Pass - Fail"), ("measure", "Measure")],
        compute="_compute_point_values", store=True,
    )
    norm = fields.Float(compute="_compute_point_values", store=True)
    tolerance_min = fields.Float(compute="_compute_point_values", store=True)
    tolerance_max = fields.Float(compute="_compute_point_values", store=True)
    norm_unit = fields.Char(compute="_compute_point_values", store=True)
    instructions = fields.Html(related="point_id.instructions")
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    product_id = fields.Many2one(
        "product.product", required=True, index=True, check_company=True
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('product_id', '=', product_id)]",
        check_company=True,
    )
    picking_id = fields.Many2one(
        "stock.picking", string="Transfer", index="btree_not_null", ondelete="cascade",
        check_company=True,
    )
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", index="btree_not_null",
        ondelete="cascade", check_company=True,
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        compute="_compute_supplier_id",
        store=True,
        readonly=False,
        index="btree_not_null",
        help="Vendor rated by this check. Filled from the receipt.",
    )
    state = fields.Selection(
        [("pending", "To Do"), ("pass", "Passed"), ("fail", "Failed")],
        required=True,
        default="pending",
        index=True,
        tracking=True,
    )
    measure = fields.Float(tracking=True)
    is_within_tolerance = fields.Boolean(compute="_compute_is_within_tolerance")
    # No default: checks are created when the transfer is confirmed, by a user
    # who is not the inspector. It is filled when the result is recorded.
    inspector_id = fields.Many2one("hr.employee", string="Inspector", check_company=True)
    date_done = fields.Datetime(string="Inspection Date", readonly=True, copy=False)
    note = fields.Html()
    alert_ids = fields.One2many("tk.quality.alert", "check_id", string="Alerts")
    alert_count = fields.Integer(compute="_compute_alert_count")

    _sql_constraints = [
        (
            "point_product_picking_uniq",
            "unique(point_id, product_id, picking_id)",
            "A product can only be inspected once per control point in the same transfer.",
        ),
    ]

    @api.depends("point_id")
    def _compute_point_values(self):
        for check in self:
            point = check.point_id
            check.test_type = point.test_type
            check.norm = point.norm
            check.tolerance_min = point.tolerance_min
            check.tolerance_max = point.tolerance_max
            check.norm_unit = point.norm_unit

    @api.depends("picking_id.partner_id", "picking_id.picking_type_code")
    def _compute_supplier_id(self):
        for check in self:
            picking = check.picking_id
            if picking.picking_type_code == "incoming" and picking.partner_id:
                check.supplier_id = picking.partner_id.commercial_partner_id
            else:
                check.supplier_id = check.supplier_id

    @api.depends("measure", "tolerance_min", "tolerance_max")
    def _compute_is_within_tolerance(self):
        for check in self:
            check.is_within_tolerance = check.tolerance_min <= check.measure <= check.tolerance_max

    @api.depends("alert_ids")
    def _compute_alert_count(self):
        for check in self:
            check.alert_count = len(check.alert_ids)

    @api.constrains("state", "measure")
    def _check_measure_result(self):
        for check in self.filtered(lambda c: c.test_type == "measure" and c.state != "pending"):
            expected = "pass" if check.is_within_tolerance else "fail"
            if check.state != expected:
                raise ValidationError(
                    _("%(check)s: the result does not match the measure %(measure)s "
                      "(tolerance %(min)s - %(max)s).",
                      check=check.name, measure=check.measure,
                      min=check.tolerance_min, max=check.tolerance_max)
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tk.quality.check") or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _ensure_pending(self):
        done = self.filtered(lambda c: c.state != "pending")
        if done:
            raise UserError(
                _("These checks are already done: %s", ", ".join(done.mapped("name")))
            )

    def _set_result(self, state):
        now = fields.Datetime.now()
        current_employee = self.env.user.employee_id
        for check in self:
            check.write({
                "state": state,
                "date_done": now,
                "inspector_id": check.inspector_id.id or current_employee.id,
            })

    def action_pass(self):
        self._ensure_pending()
        if any(check.test_type == "measure" for check in self):
            raise UserError(_("Measure checks are validated with the measured value."))
        self._set_result("pass")

    def action_fail(self):
        self._ensure_pending()
        if any(check.test_type == "measure" for check in self):
            raise UserError(_("Measure checks are validated with the measured value."))
        self._set_result("fail")

    def action_validate_measure(self):
        self._ensure_pending()
        for check in self:
            if check.test_type != "measure":
                raise UserError(_("%s is not a measure check.", check.name))
            check._set_result("pass" if check.is_within_tolerance else "fail")

    def action_reset(self):
        if not self.env.user.has_group("tk_quality_control.group_quality_manager"):
            raise AccessError(_("Only quality administrators can reset inspections."))
        closed = self.filtered(
            lambda c: c.picking_id.state == "done" or c.production_id.state == "done"
        )
        if closed:
            raise UserError(
                _("These checks belong to a validated operation and cannot be reset: %s",
                  ", ".join(closed.mapped("name")))
            )
        self.write({"state": "pending", "date_done": False})

    def action_create_alert(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quality Alert"),
            "res_model": "tk.quality.alert",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_check_id": self.id,
                "default_origin": "inspection",
                "default_title": _("%(point)s failed on %(product)s",
                                   point=self.point_id.name,
                                   product=self.product_id.display_name),
            },
        }

    def action_view_alerts(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_alert"
        )
        action["domain"] = [("check_id", "=", self.id)]
        action["context"] = {"default_check_id": self.id, "default_origin": "inspection"}
        return action

    # ------------------------------------------------------------------
    # Dashboard (OWL client action)
    # ------------------------------------------------------------------

    @api.model
    def get_dashboard_data(self):
        Alert = self.env["tk.quality.alert"]
        since = fields.Datetime.now() - relativedelta(days=30)
        results = dict(self._read_group(
            [("state", "in", ("pass", "fail")), ("date_done", ">=", since)],
            ["state"],
            ["__count"],
        ))
        done = sum(results.values())
        open_domain = [("is_closed", "=", False)]
        [(open_cost,)] = Alert._read_group(open_domain, [], ["cost:sum"])
        stages = Alert._read_group([], ["stage_id"], ["__count"], order="stage_id")
        suppliers = self.env["res.partner"].search(
            [("supplier_quality_check_count", ">", 0)],
            order="supplier_quality_score asc, supplier_quality_check_count desc",
            limit=5,
        )
        return {
            "pending": self.search_count([("state", "=", "pending")]),
            "done_30d": done,
            "failed_30d": results.get("fail", 0),
            "pass_rate_30d": round(100.0 * results.get("pass", 0) / done, 1) if done else None,
            "open_alerts": Alert.search_count(open_domain),
            "open_cost": format_amount(self.env, open_cost or 0.0, self.env.company.currency_id),
            "stages": [
                {"id": stage.id, "name": stage.name, "count": count, "closed": stage.is_closed}
                for stage, count in stages
                if stage
            ],
            "suppliers": [
                {
                    "id": partner.id,
                    "name": partner.display_name,
                    "score": round(partner.supplier_quality_score, 1),
                    "checks": partner.supplier_quality_check_count,
                }
                for partner in suppliers
            ],
        }
