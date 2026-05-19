from odoo import api, fields, models


class QrbaseScan(models.Model):
    _name = 'qrbase.scan'
    _description = 'QR Scan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scanned_at desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, help='A generated summary of the QR scan event.')
    code_id = fields.Many2one('qrbase.code', required=True, ondelete='cascade', tracking=True, help='The QR code that was scanned.')
    campaign_id = fields.Many2one('qrbase.campaign', related='code_id.campaign_id', store=True, readonly=True, help='The campaign attached to the scanned QR code.')
    source_id = fields.Many2one('utm.source', related='code_id.utm_source_id', store=True, readonly=True, help='The UTM source assigned by this QR code.')
    scanned_at = fields.Datetime(default=fields.Datetime.now, tracking=True, index=True, help='The time when the scan was first recorded.')
    state = fields.Selection(
        [('opened', 'Opened'), ('registered', 'Registered')],
        default='opened',
        tracking=True,
        help='Opened means the link was visited; registered means the visitor submitted their details.',
    )
    outcome = fields.Selection(
        [('sample', 'Sample / Prospect'), ('prospect', 'Prospect'), ('customer', 'Customer')],
        default='prospect',
        tracking=True,
        help='The system-determined lifecycle result for this scan based on the linked contact and sales history.',
    )
    landing_url = fields.Char(help='The landing page URL that was opened for this scan.')
    visitor_name = fields.Char(tracking=True, help='The visitor name entered on the landing page.')
    visitor_email = fields.Char(tracking=True, help='The visitor email entered on the landing page.')
    visitor_phone = fields.Char(tracking=True, help='The visitor phone number entered on the landing page.')
    notes = fields.Text(tracking=True, help='Optional notes recorded at the time of scanning.')
    consent_newsletter = fields.Boolean(help='True if the visitor opted in to newsletters from the scan form.')
    consent_share_data = fields.Boolean(help='True if the visitor accepted data sharing on the scan form.')
    existing_contact_found = fields.Boolean(help='True if the scan matched an existing contact instead of creating a duplicate.')
    contact_match_method = fields.Selection(
        [('email', 'Email'), ('phone', 'Phone'), ('name', 'Name')],
        help='How the contact was matched when an existing contact was found.',
    )
    resolved_outcome = fields.Selection(
        [('prospect', 'Prospect'), ('customer', 'Customer')],
        help='The final lifecycle outcome after evaluating the contact’s sales and POS history.',
    )
    partner_id = fields.Many2one('res.partner', tracking=True, help='The contact linked to this scan.')
    lead_id = fields.Many2one('crm.lead', tracking=True, help='The CRM lead created or updated for this scan.')
    ip_address = fields.Char(help='The visitor IP address captured from the request.')
    user_agent = fields.Char(help='The browser user agent captured from the request.')
    referrer = fields.Char(help='The referring page, if the browser provided one.')

    @api.depends('code_id', 'scanned_at', 'state', 'outcome', 'visitor_name')
    def _compute_name(self):
        for record in self:
            stamp = fields.Datetime.to_string(record.scanned_at) if record.scanned_at else ''
            code_name = record.code_id.name or 'QR'
            label = record.visitor_name or record.outcome or record.state or 'scan'
            record.name = f'{code_name} / {stamp[:19]} / {label}'

    @api.model
    def _qrbase_summarize_scans(self, scans):
        scans = scans.sudo()
        registered_scans = scans.filtered(lambda scan: scan.state == 'registered')
        customer_scans = scans.filtered(lambda scan: scan.resolved_outcome == 'customer' or scan.outcome == 'customer')
        prospect_scans = scans.filtered(lambda scan: scan.resolved_outcome == 'prospect' or scan.outcome == 'prospect')
        sample_scans = scans.filtered(lambda scan: scan.outcome == 'sample')
        duplicate_scans = scans.filtered('existing_contact_found')
        newsletter_scans = scans.filtered('consent_newsletter')
        data_consent_scans = scans.filtered('consent_share_data')
        new_contact_scans = registered_scans.filtered(lambda scan: not scan.existing_contact_found)
        unique_partner_ids = {
            scan.partner_id.commercial_partner_id.id
            for scan in scans
            if scan.partner_id and scan.partner_id.commercial_partner_id
        }
        scan_count = len(scans)
        registered_count = len(registered_scans)
        customer_count = len(customer_scans)
        prospect_count = len(prospect_scans)
        sample_count = len(sample_scans)
        duplicate_count = len(duplicate_scans)
        newsletter_count = len(newsletter_scans)
        data_consent_count = len(data_consent_scans)
        new_contact_count = len(new_contact_scans)
        unique_contact_count = len(unique_partner_ids)
        return {
            'scan_count': scan_count,
            'opened_count': scan_count - registered_count,
            'registered_count': registered_count,
            'customer_count': customer_count,
            'prospect_count': prospect_count,
            'sample_count': sample_count,
            'duplicate_count': duplicate_count,
            'newsletter_count': newsletter_count,
            'data_consent_count': data_consent_count,
            'new_contact_count': new_contact_count,
            'unique_contact_count': unique_contact_count,
            'customer_rate': (customer_count / scan_count * 100.0) if scan_count else 0.0,
            'prospect_rate': (prospect_count / scan_count * 100.0) if scan_count else 0.0,
            'duplicate_rate': (duplicate_count / scan_count * 100.0) if scan_count else 0.0,
            'newsletter_rate': (newsletter_count / scan_count * 100.0) if scan_count else 0.0,
            'data_consent_rate': (data_consent_count / scan_count * 100.0) if scan_count else 0.0,
        }
