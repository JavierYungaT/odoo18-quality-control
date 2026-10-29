from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TkQualityPoint(models.Model):
    """What has to be inspected, and in which operations."""

    _name = "tk.quality.point"
    _description = "Quality Control Point"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    picking_type_ids = fields.Many2many(
        "stock.picking.type",
        string="Operation Types",
        required=True,
        check_company=True,
        help="Receipts, deliveries or manufacturing operations that trigger this check.",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Products",
        check_company=True,
        help="Leave products and categories empty to inspect every product.",
    )
    product_category_ids = fields.Many2many(
        "product.category",
        string="Product Categories",
        help="Products of these categories (and their subcategories) are inspected.",
    )
    test_type = fields.Selection(
        [("pass_fail", "Pass - Fail"), ("measure", "Measure")],
        required=True,
        default="pass_fail",
    )
    norm = fields.Float(help="Target value of the measure.")
    tolerance_min = fields.Float(string="Min. Tolerance")
    tolerance_max = fields.Float(string="Max. Tolerance")
    norm_unit = fields.Char(string="Unit", help="e.g. mm, kg, %")
    instructions = fields.Html(translate=True)
    check_ids = fields.One2many("tk.quality.check", "point_id", string="Checks")
    check_count = fields.Integer(compute="_compute_check_count")

    @api.depends("check_ids")
    def _compute_check_count(self):
        counts = dict(
            self.env["tk.quality.check"]._read_group(
                [("point_id", "in", self.ids)], ["point_id"], ["__count"]
            )
        )
        for point in self:
            point.check_count = counts.get(point, 0)

    @api.constrains("test_type", "norm", "tolerance_min", "tolerance_max")
    def _check_tolerances(self):
        for point in self.filtered(lambda p: p.test_type == "measure"):
            if point.tolerance_min > point.tolerance_max:
                raise ValidationError(
                    _("%(point)s: the minimum tolerance cannot be greater than the maximum.",
                      point=point.name)
                )
            if not point.tolerance_min <= point.norm <= point.tolerance_max:
                raise ValidationError(
                    _("%(point)s: the norm must be within the tolerance range.", point=point.name)
                )

    def _applies_to(self, product):
        """Return True if ``product`` must be inspected by this point."""
        self.ensure_one()
        if not self.product_ids and not self.product_category_ids:
            return True
        if product in self.product_ids:
            return True
        product_path = product.categ_id.parent_path or ""
        return any(product_path.startswith(categ.parent_path) for categ in self.product_category_ids)

    @api.model
    def _get_points(self, picking_type, company):
        return self.search([
            ("picking_type_ids", "in", picking_type.id),
            ("company_id", "=", company.id),
        ])

    def action_view_checks(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "tk_quality_control.action_tk_quality_check"
        )
        action["domain"] = [("point_id", "=", self.id)]
        action["context"] = {"default_point_id": self.id}
        return action
