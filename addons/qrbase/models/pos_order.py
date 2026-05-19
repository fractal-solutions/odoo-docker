from odoo import models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        for order in self.filtered('partner_id'):
            order.partner_id.commercial_partner_id._qrbase_mark_customer(
                code=order.partner_id.commercial_partner_id.qrbase_code_id,
            )
        return res
