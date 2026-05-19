from datetime import timedelta

from odoo import api, fields, models
from .qrbase_consent import qrbase_mobile_country_code_selection


class ResPartner(models.Model):
    _inherit = 'res.partner'

    qrbase_status = fields.Selection(
        [
            ('prospect', 'Prospect'),
            ('customer', 'Customer'),
            ('lapsed', 'Lapsed'),
        ],
        tracking=True,
    )
    qrbase_code_id = fields.Many2one('qrbase.code', string='Last QR Code', ondelete='set null', tracking=True)
    qrbase_last_campaign_id = fields.Many2one('qrbase.campaign', string='Last Campaign', ondelete='set null', tracking=True)
    qrbase_last_source_id = fields.Many2one('utm.source', string='Last Source', ondelete='set null', tracking=True)
    qrbase_customer_since = fields.Datetime(tracking=True)
    qrbase_last_purchase_at = fields.Datetime(tracking=True)
    qrbase_lapsed_at = fields.Datetime(tracking=True)
    qrbase_title = fields.Selection(
        [
            ('mr', 'Mr'),
            ('mrs', 'Mrs'),
            ('ms', 'Ms'),
            ('mx', 'Mx'),
            ('dr', 'Dr'),
            ('prof', 'Prof'),
            ('other', 'Other'),
        ],
        tracking=True,
        help='The preferred title captured from the QR landing page.',
    )
    qrbase_first_name = fields.Char(
        tracking=True,
        help='The first name captured from the QR landing page.',
    )
    qrbase_surname = fields.Char(
        tracking=True,
        help='The surname captured from the QR landing page.',
    )
    qrbase_gender = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        tracking=True,
        help='The gender chosen on the QR landing page.',
    )
    qrbase_mobile_country_code = fields.Selection(
        selection='_qrbase_mobile_country_code_selection',
        tracking=True,
        default='+254',
        help='The country dial code captured from the QR landing page.',
    )
    qrbase_mobile_number = fields.Char(
        tracking=True,
        help='The phone number without the country code captured from the QR landing page.',
    )
    qrbase_attribution_label = fields.Char(
        string='QR Attribution',
        tracking=True,
        help='Human-readable label that identifies the campaign and QR code that created or updated this contact.',
    )
    qrbase_attribution_kind = fields.Selection(
        [
            ('partner', 'Partner'),
            ('event', 'Event'),
            ('website', 'Website'),
            ('pos', 'Point of Sale'),
            ('crm', 'CRM Pipeline'),
            ('custom', 'Custom'),
        ],
        tracking=True,
        help='The campaign allocation type attached to the latest QR source for this contact.',
    )
    qrbase_newsletter_opt_in = fields.Boolean(
        string='Newsletter Opt-In',
        tracking=True,
        help='Checked when the person explicitly opts in to receive newsletters from a QR scan.',
    )
    qrbase_data_share_consent = fields.Boolean(
        string='Data Share Consent',
        tracking=True,
        help='Checked when the person explicitly agrees to share their data through the QR scan form.',
    )
    qrbase_scan_count = fields.Integer(compute='_compute_qrbase_stats', help='How many QR scans are linked to this contact.')
    qrbase_first_scan_at = fields.Datetime(compute='_compute_qrbase_stats', help='The date and time of the first QR scan linked to this contact.')
    qrbase_last_scan_at = fields.Datetime(compute='_compute_qrbase_stats', help='The date and time of the last QR scan linked to this contact.')

    @api.depends('child_ids', 'child_ids.qrbase_status')
    def _compute_qrbase_stats(self):
        Scan = self.env['qrbase.scan'].sudo()
        for partner in self:
            root = partner.commercial_partner_id or partner
            scans = Scan.search([('partner_id', 'child_of', root.id)], order='scanned_at asc, id asc')
            partner.qrbase_scan_count = len(scans)
            partner.qrbase_first_scan_at = scans[0].scanned_at if scans else False
            partner.qrbase_last_scan_at = scans[-1].scanned_at if scans else False

    @api.model
    def _qrbase_mobile_country_code_selection(self):
        return qrbase_mobile_country_code_selection(self.env)

    def _qrbase_mark_prospect(self, code=None, scan=None):
        for partner in self:
            root = partner.commercial_partner_id or partner
            values = {}
            if code:
                values.update({
                    'qrbase_code_id': code.id,
                    'qrbase_last_campaign_id': code.campaign_id.id,
                    'qrbase_last_source_id': code.utm_source_id.id,
                })
                values.update(root._qrbase_attribution_values(code))
            if root.qrbase_status != 'customer':
                values['qrbase_status'] = 'prospect'
            if values:
                root.write(values)

    def _qrbase_mark_customer(self, code=None, scan=None):
        now = fields.Datetime.now()
        for partner in self:
            root = partner.commercial_partner_id or partner
            values = {
                'qrbase_status': 'customer',
                'qrbase_customer_since': root.qrbase_customer_since or now,
                'qrbase_last_purchase_at': now,
                'qrbase_lapsed_at': False,
            }
            if code:
                values.update({
                    'qrbase_code_id': code.id,
                    'qrbase_last_campaign_id': code.campaign_id.id,
                    'qrbase_last_source_id': code.utm_source_id.id,
                })
                values.update(root._qrbase_attribution_values(code))
            root.write(values)

    def _qrbase_determine_outcome_from_sales(self):
        self.ensure_one()
        partner = self.commercial_partner_id or self
        SaleOrder = self.env['sale.order'].sudo()
        PosOrder = self.env['pos.order'].sudo()
        has_sale_order = bool(SaleOrder.search_count([
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ('sale', 'done')),
        ]))
        has_pos_order = bool(PosOrder.search_count([
            ('partner_id', 'child_of', partner.id),
            ('state', 'in', ('paid', 'done', 'invoiced')),
        ]))
        return 'customer' if has_sale_order or has_pos_order else 'prospect'

    def _qrbase_apply_scan_preferences(self, code=None, scan=None, consent_newsletter=False, consent_share_data=False, outcome=False):
        for partner in self:
            root = partner.commercial_partner_id or partner
            values = {
                'qrbase_newsletter_opt_in': bool(consent_newsletter),
                'qrbase_data_share_consent': bool(consent_share_data),
            }
            if scan and scan.scanned_at:
                values['qrbase_last_scan_at'] = scan.scanned_at
            if outcome == 'customer':
                values['qrbase_status'] = 'customer'
            elif root.qrbase_status != 'customer':
                values['qrbase_status'] = 'prospect'
            if code:
                values.update({
                    'qrbase_code_id': code.id,
                    'qrbase_last_campaign_id': code.campaign_id.id,
                    'qrbase_last_source_id': code.utm_source_id.id,
                })
                values.update(root._qrbase_attribution_values(code))
            root.write(values)

    def _qrbase_mark_lapsed(self, code=None, scan=None):
        now = fields.Datetime.now()
        for partner in self:
            root = partner.commercial_partner_id or partner
            values = {
                'qrbase_status': 'lapsed',
                'qrbase_lapsed_at': now,
            }
            if code:
                values.update({
                    'qrbase_code_id': code.id,
                    'qrbase_last_campaign_id': code.campaign_id.id,
                    'qrbase_last_source_id': code.utm_source_id.id,
                })
                values.update(root._qrbase_attribution_values(code))
            root.write(values)

    @api.model
    def _cron_qrbase_mark_lapsed_customers(self):
        days = int(self.env['ir.config_parameter'].sudo().get_param('qrbase.lapse_days', default='90'))
        cutoff = fields.Datetime.now() - timedelta(days=days)
        customers = self.search([
            ('qrbase_status', '=', 'customer'),
            '|',
            ('qrbase_last_purchase_at', '=', False),
            ('qrbase_last_purchase_at', '<', cutoff),
        ])
        customers._qrbase_mark_lapsed()

    def _qrbase_attribution_values(self, code=None):
        self.ensure_one()
        code = code or self.qrbase_code_id
        if not code:
            return {}
        return {
            'qrbase_attribution_label': f'{code.campaign_id.name} / {code.name}',
            'qrbase_attribution_kind': code.campaign_id.allocation_kind,
        }
