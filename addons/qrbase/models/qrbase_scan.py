from odoo import api, fields, models

from .qrbase_consent import qrbase_mobile_country_code_selection


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
    visitor_title = fields.Selection(
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
        help='The title selected on the landing page.',
    )
    visitor_first_name = fields.Char(tracking=True, help='The first name entered on the landing page.')
    visitor_surname = fields.Char(tracking=True, help='The surname entered on the landing page.')
    visitor_gender = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        tracking=True,
        help='The gender selected on the landing page.',
    )
    visitor_name = fields.Char(tracking=True, help='The visitor full name entered on the landing page.')
    visitor_email = fields.Char(tracking=True, help='The visitor email entered on the landing page.')
    visitor_email_confirmation = fields.Char(tracking=True, help='The email confirmation entered on the landing page.')
    visitor_mobile_country_code = fields.Selection(
        selection='_qrbase_mobile_country_code_selection',
        default='+254',
        tracking=True,
        help='The selected country dial code from the landing page.',
    )
    visitor_mobile_number = fields.Char(tracking=True, help='The phone number entered without the country code.')
    visitor_phone = fields.Char(tracking=True, help='The combined phone number including the country code.')
    notes = fields.Text(tracking=True, help='Optional notes recorded at the time of scanning.')
    consent_newsletter = fields.Boolean(help='True if the visitor opted in to newsletters from the scan form.')
    consent_share_data = fields.Boolean(help='True if the visitor accepted data sharing on the scan form.')
    otp_code = fields.Char(tracking=True, help='The QR landing page verification code shown to the visitor.')
    otp_status = fields.Selection(
        [('none', 'Not Requested'), ('pending', 'Pending'), ('verified', 'Verified')],
        default='none',
        tracking=True,
        help='Tracks whether the verification code has been generated and completed.',
    )
    otp_requested_at = fields.Datetime(tracking=True, help='When the verification code was first generated.')
    otp_verified_at = fields.Datetime(tracking=True, help='When the verification code was successfully confirmed.')
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
    consent_term_ids = fields.One2many(
        'qrbase.scan.consent.term',
        'scan_id',
        string='Consent Snapshot',
        help='The terms and consent choices captured for this scan.',
    )
    ip_address = fields.Char(help='The visitor IP address captured from the request.')
    user_agent = fields.Char(help='The browser user agent captured from the request.')
    referrer = fields.Char(help='The referring page, if the browser provided one.')

    @api.depends('code_id', 'scanned_at', 'state', 'outcome', 'visitor_name', 'visitor_title', 'visitor_first_name', 'visitor_surname')
    def _compute_name(self):
        for record in self:
            stamp = fields.Datetime.to_string(record.scanned_at) if record.scanned_at else ''
            code_name = record.code_id.name or 'QR'
            label = record.visitor_name or ' '.join(part for part in [record.visitor_first_name, record.visitor_surname] if part) or record.outcome or record.state or 'scan'
            record.name = f'{code_name} / {stamp[:19]} / {label}'

    @api.model
    def _qrbase_mobile_country_code_selection(self):
        return qrbase_mobile_country_code_selection(self.env)

    @api.model
    def _qrbase_title_selection(self):
        return [
            ('mr', 'Mr'),
            ('mrs', 'Mrs'),
            ('ms', 'Ms'),
            ('mx', 'Mx'),
            ('dr', 'Dr'),
            ('prof', 'Prof'),
            ('other', 'Other'),
        ]

    @api.model
    def _qrbase_gender_selection(self):
        return [('male', 'Male'), ('female', 'Female')]

    def _qrbase_sync_consent_terms(self, consent_terms, accepted_term_ids):
        self.ensure_one()
        accepted_term_ids = set(int(term_id) for term_id in (accepted_term_ids or []))
        commands = [(5, 0, 0)]
        for term in consent_terms:
            commands.append((0, 0, {
                'term_id': term.id,
                'sequence': term.sequence,
                'name': term.name,
                'description': term.description,
                'necessary': term.necessary,
                'accepted': term.id in accepted_term_ids,
            }))
        self.write({'consent_term_ids': commands})

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
