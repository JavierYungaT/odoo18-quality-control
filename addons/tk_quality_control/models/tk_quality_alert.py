from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import is_html_empty


class TkQualityAlert(models.Model):
    """A non-conformity: failed inspection, customer complaint or internal finding."""

    _name = "tk.quality.alert"
    _description = "Quality Alert"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Reference", required=True, readonly=True, copy=False, default=lambda self: _("New")
    )
    title = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company
    )
    origin = fields.Selection(
        [
            ("inspection", "Failed Inspection"),
            ("customer", "Customer Complaint"),
            ("internal", "Internal Finding"),
        ],
        required=True,
        default="internal",
        tracking=True,
    )
    stage_id = fields.Many2one(
        "tk.quality.alert.stage",
        string="Stage",
        index=True,
        tracking=True,
        copy=False,
        default=lambda self: self._default_stage_id(),
        group_expand="_read_group_stage_ids",
    )
    is_closed = fields.Boolean(related="stage_id.is_closed", store=True)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "High"), ("2", "Urgent")], default="0", index=True
    )
    check_id = fields.Many2one(
        "tk.quality.check", string="Quality Check", index="btree_not_null", check_company=True
    )
    product_id = fields.Many2one("product.product", required=True, check_company=True)
    lot_id = fields.Many2one(
        "stock.lot", string="Lot/Serial", domain="[('product_id', '=', product_id)]",
        check_company=True,
    )
    picking_id = fields.Many2one("stock.picking", string="Transfer", check_company=True)
    production_id = fields.Many2one(
        "mrp.production", string="Manufacturing Order", check_company=True
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Sales Order", index="btree_not_null", check_company=True
    )
    partner_id = fields.Many2one("res.partner", string="Partner", help="Vendor or customer involved.")
    employee_id = fields.Many2one(
        "hr.employee", string="Responsible", tracking=True, check_company=True
    )
    date_deadline = fields.Date(string="Deadline", tracking=True)
    date_closed = fields.Datetime(compute="_compute_date_closed", store=True)
    cause_category = fields.Selection(
        [
            ("material", "Material"),
            ("method", "Method"),
            ("machine", "Machine"),
            ("manpower", "Manpower"),
            ("measurement", "Measurement"),
            ("environment", "Environment"),
        ],
        string="Cause Category",
        help="Ishikawa (6M) category of the root cause.",
    )
    root_cause = fields.Text()
    corrective_action = fields.Html()
    quantity = fields.Float(string="Affected Quantity", default=1.0, digits="Product Unit of Measure")
    product_uom_id = fields.Many2one(related="product_id.uom_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    unit_cost = fields.Monetary(compute="_compute_cost", store=True)
    cost = fields.Monetary(
        string="Non-Conformity Cost",
        compute="_compute_cost",
        store=True,
        help="Affected quantity valued at the product cost.",
    )

    def _default_stage_id(self):
        return self.env["tk.quality.alert.stage"].search([], limit=1)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return stages.search([])

    @api.depends("product_id", "quantity", "company_id")
    def _compute_cost(self):
        for alert in self:
            unit_cost = alert.product_id.with_company(alert.company_id).standard_price
            alert.unit_cost = unit_cost
            alert.cost = unit_cost * alert.quantity

    @api.depends("stage_id.is_closed")
    def _compute_date_closed(self):
        for alert in self:
            if alert.stage_id.is_closed:
                alert.date_closed = alert.date_closed or fields.Datetime.now()
            else:
                alert.date_closed = False

    @api.constrains("stage_id", "root_cause", "corrective_action")
    def _check_close_requirements(self):
        for alert in self.filtered("is_closed"):
            if not alert.root_cause or is_html_empty(alert.corrective_action):
                raise ValidationError(
                    _("%(alert)s cannot be closed without a root cause and a corrective action.",
                      alert=alert.name)
                )

    @api.onchange("check_id")
    def _onchange_check_id(self):
        check = self.check_id
        if check:
            self.product_id = check.product_id
            self.lot_id = check.lot_id
            self.picking_id = check.picking_id
            self.production_id = check.production_id
            self.partner_id = check.supplier_id or check.picking_id.partner_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("check_id") and not vals.get("product_id"):
                check = self.env["tk.quality.check"].browse(vals["check_id"])
                vals.update({
                    "product_id": check.product_id.id,
                    "lot_id": vals.get("lot_id") or check.lot_id.id,
                    "picking_id": vals.get("picking_id") or check.picking_id.id,
                    "production_id": vals.get("production_id") or check.production_id.id,
                    "partner_id": vals.get("partner_id") or check.supplier_id.id,
                })
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tk.quality.alert") or _("New")
        return super().create(vals_list)

    @api.model
    def _cron_schedule_overdue_activities(self):
        """Remind the responsible of every open alert past its deadline."""
        overdue = self.search([
            ("is_closed", "=", False),
            ("date_deadline", "<", fields.Date.context_today(self)),
            ("employee_id.user_id", "!=", False),
        ])
        todo = self.env.ref("mail.mail_activity_data_todo")
        for alert in overdue:
            if alert.activity_ids.filtered(lambda a: a.activity_type_id == todo):
                continue
            alert.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=alert.employee_id.user_id.id,
                summary=_("Overdue quality alert"),
                note=_("The deadline of %s has passed.", alert.name),
            )
