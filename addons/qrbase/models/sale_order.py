from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered('partner_id'):
            order.partner_id.commercial_partner_id._qrbase_mark_customer(
                code=order.partner_id.commercial_partner_id.qrbase_code_id,
            )
        return res
