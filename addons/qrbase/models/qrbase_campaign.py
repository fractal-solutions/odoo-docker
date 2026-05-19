from odoo import api, fields, models


class QrbaseCampaign(models.Model):
    _name = 'qrbase.campaign'
    _description = 'QR Campaign'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id'

    name = fields.Char(
        required=True,
        tracking=True,
        help='The public name of this QR campaign. This is what your team will recognize in reporting and menus.',
    )
    allocation_kind = fields.Selection(
        [
            ('partner', 'Partner'),
            ('event', 'Event'),
            ('website', 'Website'),
            ('pos', 'Point of Sale'),
            ('crm', 'CRM Pipeline'),
            ('custom', 'Custom'),
        ],
        required=True,
        default='custom',
        tracking=True,
        help='Defines where this QR code allocation is used, such as a partner referral, event, website, POS shop, or CRM campaign.',
    )
    allocation_ref = fields.Reference(
        selection='_selection_allocation_ref',
        string='Allocation Reference',
        tracking=True,
        help='Optional link to the actual record that owns this QR allocation, for example a partner, event, POS config, or CRM team.',
    )
    purpose = fields.Text(
        tracking=True,
        help='Explain why this QR campaign exists and what you want people to do after scanning it.',
    )
    target_url = fields.Char(
        string='Target URL',
        tracking=True,
        help='Where the user should go after scanning the QR code. This can be a website, landing page, or any public URL.',
    )
    website_id = fields.Many2one(
        'website',
        tracking=True,
        help='Optional website used for this campaign when you want the landing page tied to a specific site.',
    )
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
        help='The user responsible for managing this campaign and its QR codes.',
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        tracking=True,
        help='The company that owns this campaign record.',
    )
    landing_theme = fields.Selection(
        [('dark', 'Dark Mode'), ('light', 'Light Mode')],
        default='dark',
        tracking=True,
        help='Controls how the public QR landing page is rendered when users open the scan link.',
    )
    landing_logo = fields.Image(
        string='Landing Page Logo',
        max_width=512,
        max_height=512,
        help='Optional logo shown on the public scan page. Use this to brand the landing experience for the campaign.',
    )
    landing_logo_url = fields.Char(compute='_compute_landing_logo_url')
    consent_term_ids = fields.One2many(
        'qrbase.consent.term',
        'campaign_id',
        string='Landing Consents',
        help='Editable consent items and terms displayed on the public QR landing page.',
    )
    active = fields.Boolean(default=True, tracking=True, help='Archive inactive campaigns without deleting their QR code history.')
    code_ids = fields.One2many('qrbase.code', 'campaign_id', string='QR Codes', help='The QR codes that belong to this campaign.')
    code_count = fields.Integer(compute='_compute_stats', help='How many QR codes belong to this campaign.')
    scan_count = fields.Integer(compute='_compute_stats', help='Total scan events recorded for this campaign.')
    prospect_count = fields.Integer(compute='_compute_stats', help='How many scans currently resolve to prospects.')
    customer_count = fields.Integer(compute='_compute_stats', help='How many scans currently resolve to customers.')
    sample_count = fields.Integer(compute='_compute_stats', help='How many scans were marked as sample or sample/prospect.')
    registered_scan_count = fields.Integer(compute='_compute_stats', help='How many scans include submitted contact details.')
    opened_scan_count = fields.Integer(compute='_compute_stats', help='How many scans only opened the landing page.')
    unique_contact_count = fields.Integer(compute='_compute_stats', help='How many unique contacts were linked to this campaign.')
    duplicate_contact_count = fields.Integer(compute='_compute_stats', help='How many scans matched an existing contact instead of creating a duplicate.')
    newsletter_opt_in_count = fields.Integer(compute='_compute_stats', help='How many scans included newsletter consent.')
    data_share_consent_count = fields.Integer(compute='_compute_stats', help='How many scans included data sharing consent.')
    new_contact_count = fields.Integer(compute='_compute_stats', help='How many scans created a new contact record.')
    customer_rate = fields.Float(compute='_compute_stats', help='Customer scans as a percentage of all scans.')
    duplicate_rate = fields.Float(compute='_compute_stats', help='Duplicate-matched scans as a percentage of all scans.')
    newsletter_rate = fields.Float(compute='_compute_stats', help='Newsletter opt-ins as a percentage of all scans.')
    data_consent_rate = fields.Float(compute='_compute_stats', help='Data sharing consents as a percentage of all scans.')

    @api.model
    def _selection_allocation_ref(self):
        options = [
            ('res.partner', 'Partner'),
            ('website', 'Website'),
            ('pos.config', 'POS Shop'),
            ('crm.team', 'CRM Team'),
            ('utm.source', 'UTM Source'),
        ]
        if 'event.event' in self.env:
            options.append(('event.event', 'Event'))
        return options

    @api.depends(
        'code_ids',
        'code_ids.scan_ids',
        'code_ids.scan_ids.scanned_at',
        'code_ids.scan_ids.state',
        'code_ids.scan_ids.outcome',
        'code_ids.scan_ids.resolved_outcome',
        'code_ids.scan_ids.existing_contact_found',
        'code_ids.scan_ids.consent_newsletter',
        'code_ids.scan_ids.consent_share_data',
        'code_ids.scan_ids.partner_id',
    )
    def _compute_stats(self):
        Scan = self.env['qrbase.scan']
        for campaign in self:
            scans = campaign.code_ids.mapped('scan_ids')
            summary = Scan._qrbase_summarize_scans(scans)
            campaign.code_count = len(campaign.code_ids)
            campaign.scan_count = summary['scan_count']
            campaign.prospect_count = summary['prospect_count']
            campaign.customer_count = summary['customer_count']
            campaign.sample_count = summary['sample_count']
            campaign.registered_scan_count = summary['registered_count']
            campaign.opened_scan_count = summary['opened_count']
            campaign.unique_contact_count = summary['unique_contact_count']
            campaign.duplicate_contact_count = summary['duplicate_count']
            campaign.newsletter_opt_in_count = summary['newsletter_count']
            campaign.data_share_consent_count = summary['data_consent_count']
            campaign.new_contact_count = summary['new_contact_count']
            campaign.customer_rate = summary['customer_rate']
            campaign.duplicate_rate = summary['duplicate_rate']
            campaign.newsletter_rate = summary['newsletter_rate']
            campaign.data_consent_rate = summary['data_consent_rate']

    @api.depends('landing_logo')
    def _compute_landing_logo_url(self):
        for campaign in self:
            campaign.landing_logo_url = f'/web/image/qrbase.campaign/{campaign.id}/landing_logo' if campaign.id and campaign.landing_logo else False

    def _qrbase_active_consent_terms(self):
        self.ensure_one()
        return self.consent_term_ids.filtered('active').sorted(lambda term: (term.sequence, term.id))

    def action_open_campaign_analytics(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} Analytics',
            'res_model': 'qrbase.scan',
            'view_mode': 'pivot,graph,tree,form',
            'domain': [('campaign_id', '=', self.id)],
            'context': {
                'search_default_group_by_campaign': 1,
                'search_default_group_by_code': 1,
                'default_campaign_id': self.id,
                'group_by': 'code_id',
            },
        }

    def action_open_report_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'QR Reports',
            'res_model': 'qrbase.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_campaign_id': self.id,
                'default_allocation_kind': self.allocation_kind,
            },
        }
