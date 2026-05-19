from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    qrbase_code_id = fields.Many2one('qrbase.code', string='QR Code', ondelete='set null')
    qrbase_scan_id = fields.Many2one('qrbase.scan', string='QR Scan', ondelete='set null')
