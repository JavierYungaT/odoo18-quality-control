from odoo import fields, models, tools
from odoo.tools import SQL


class TkQualityReport(models.Model):
    """Read-only analysis backed by a PostgreSQL view over finished checks."""

    _name = "tk.quality.report"
    _description = "Quality Analysis"
    _auto = False
    _order = "date desc"
    _rec_name = "date"

    date = fields.Datetime(string="Inspection Date", readonly=True)
    point_id = fields.Many2one("tk.quality.point", string="Control Point", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    product_categ_id = fields.Many2one("product.category", string="Product Category", readonly=True)
    supplier_id = fields.Many2one("res.partner", string="Vendor", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    inspector_id = fields.Many2one("hr.employee", string="Inspector", readonly=True)
    picking_type_id = fields.Many2one("stock.picking.type", string="Operation Type", readonly=True)
    state = fields.Selection(
        [("pass", "Passed"), ("fail", "Failed")], string="Result", readonly=True
    )
    check_count = fields.Integer(string="# Checks", readonly=True)
    pass_count = fields.Integer(string="# Passed", readonly=True)
    fail_count = fields.Integer(string="# Failed", readonly=True)
    pass_rate = fields.Float(string="Pass Rate (%)", aggregator="avg", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    c.id AS id,
                    c.date_done AS date,
                    c.point_id,
                    c.product_id,
                    pt.categ_id AS product_categ_id,
                    c.supplier_id,
                    c.company_id,
                    c.inspector_id,
                    COALESCE(sp.picking_type_id, mp.picking_type_id) AS picking_type_id,
                    c.state,
                    1 AS check_count,
                    CASE WHEN c.state = 'pass' THEN 1 ELSE 0 END AS pass_count,
                    CASE WHEN c.state = 'fail' THEN 1 ELSE 0 END AS fail_count,
                    CASE WHEN c.state = 'pass' THEN 100.0 ELSE 0.0 END AS pass_rate
                FROM tk_quality_check c
                JOIN product_product pp ON pp.id = c.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                LEFT JOIN stock_picking sp ON sp.id = c.picking_id
                LEFT JOIN mrp_production mp ON mp.id = c.production_id
                WHERE c.state IN ('pass', 'fail')
            )
            """,
            SQL.identifier(self._table),
        ))
