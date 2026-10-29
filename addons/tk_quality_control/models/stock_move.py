from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_confirm(self, merge=True, merge_into=False):
        """Generate the quality checks of the transfers and manufacturing
        orders as soon as their moves are confirmed. Hooking the move (and not
        the picking) also covers receipts created by purchase orders."""
        moves = super()._action_confirm(merge=merge, merge_into=merge_into)
        moves.picking_id._tk_generate_quality_checks()
        moves.production_id._tk_generate_quality_checks()
        return moves
