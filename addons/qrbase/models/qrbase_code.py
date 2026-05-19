import base64
import uuid
from io import BytesIO
from urllib.parse import quote_plus

from PIL import Image, ImageDraw, ImageOps
from odoo import _, api, fields, models


class QrbaseCode(models.Model):
    _name = 'qrbase.code'
    _description = 'QR Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        required=True,
        tracking=True,
        help='A friendly internal name for this specific QR code.',
    )
    campaign_id = fields.Many2one(
        'qrbase.campaign',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='The campaign this QR code belongs to.',
    )
    token = fields.Char(
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: uuid.uuid4().hex[:16],
        help='Unique public token used to build the scan URL for this QR code.',
    )
    purpose = fields.Char(
        tracking=True,
        help='What this QR code is meant to do, such as drive event sign-ups, partner referrals, or POS captures.',
    )
    target_url = fields.Char(
        string='Target URL',
        tracking=True,
        help='Optional destination URL the user can continue to after the scan form is saved.',
    )
    qr_logo = fields.Image(
        string='QR Logo',
        max_width=256,
        max_height=256,
        help='Optional logo embedded inside the QR code itself to make the code match your brand.',
    )
    active = fields.Boolean(default=True, tracking=True, help='Deactivate a QR code without losing its scan history.')
    utm_source_id = fields.Many2one(
        'utm.source',
        string='UTM Source',
        ondelete='restrict',
        copy=False,
        tracking=True,
        help='The UTM source automatically attached to contacts created from this QR code.',
    )
    qr_public_url = fields.Char(compute='_compute_qr_public_url', help='The public scan URL generated for this code.')
    qr_image = fields.Binary(compute='_compute_qr_image', help='Rendered QR image used in backend and print layouts.')
    qr_image_url = fields.Char(compute='_compute_qr_image_url', help='Direct image URL for the QR code.')
    scan_ids = fields.One2many('qrbase.scan', 'code_id', string='Scans', help='Every scan recorded for this QR code.')
    scan_count = fields.Integer(compute='_compute_stats', help='The total number of scans for this code.')
    last_scan_at = fields.Datetime(compute='_compute_stats', help='The date and time of the latest scan.')
    opened_scan_count = fields.Integer(compute='_compute_stats', help='How many scans only opened the landing page.')
    registered_scan_count = fields.Integer(compute='_compute_stats', help='How many scans include submitted contact details.')
    unique_contact_count = fields.Integer(compute='_compute_stats', help='How many unique contacts were linked to this QR code.')
    customer_count = fields.Integer(compute='_compute_stats', help='How many scans resolved to customers.')
    prospect_count = fields.Integer(compute='_compute_stats', help='How many scans resolved to prospects.')
    sample_count = fields.Integer(compute='_compute_stats', help='How many scans were marked as sample or sample/prospect.')
    duplicate_contact_count = fields.Integer(compute='_compute_stats', help='How many scans matched an existing contact instead of creating a duplicate.')
    newsletter_opt_in_count = fields.Integer(compute='_compute_stats', help='How many scans included newsletter consent.')
    data_share_consent_count = fields.Integer(compute='_compute_stats', help='How many scans included data sharing consent.')
    new_contact_count = fields.Integer(compute='_compute_stats', help='How many scans created a new contact record.')
    customer_rate = fields.Float(compute='_compute_stats', help='Customer scans as a percentage of all scans.')
    duplicate_rate = fields.Float(compute='_compute_stats', help='Duplicate-matched scans as a percentage of all scans.')
    newsletter_rate = fields.Float(compute='_compute_stats', help='Newsletter opt-ins as a percentage of all scans.')
    data_consent_rate = fields.Float(compute='_compute_stats', help='Data sharing consents as a percentage of all scans.')
    notes = fields.Html(help='Internal notes for this QR code.')

    @api.model_create_multi
    def create(self, vals_list):
        campaign_model = self.env['qrbase.campaign']
        source_model = self.env['utm.source']
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = uuid.uuid4().hex[:16]
            if not vals.get('name'):
                campaign = campaign_model.browse(vals.get('campaign_id')) if vals.get('campaign_id') else False
                vals['name'] = campaign.name if campaign and campaign.exists() else vals['token'][:8].upper()
        records = super().create(vals_list)
        for record in records.filtered(lambda code: not code.utm_source_id):
            source_name = f'{record.name} / {record.token[:6]}'
            record.utm_source_id = source_model.create({'name': source_name})
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals:
            for record in self.filtered('utm_source_id'):
                source_name = f'{record.name} / {record.token[:6]}'
                if record.utm_source_id.name != source_name:
                    record.utm_source_id.write({'name': source_name})
        return res

    @api.depends('token')
    def _compute_qr_public_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', default='').rstrip('/')
        for record in self:
            record.qr_public_url = f'{base_url}/qrbase/s/{record.token}' if base_url else f'/qrbase/s/{record.token}'

    @api.depends('qr_public_url')
    def _compute_qr_image(self):
        report = self.env['ir.actions.report']
        for record in self:
            if not record.qr_public_url:
                record.qr_image = False
                continue
            barcode = report.barcode('QR', record.qr_public_url, width=512, height=512, barLevel='M')
            if not record.qr_logo:
                record.qr_image = base64.b64encode(barcode)
                continue
            record.qr_image = base64.b64encode(record._qrbase_embed_logo(barcode, record.qr_logo))

    @api.depends('qr_public_url')
    def _compute_qr_image_url(self):
        for record in self:
            record.qr_image_url = (
                f'/report/barcode/?barcode_type=QR&value={quote_plus(record.qr_public_url)}'
                '&width=320&height=320&barLevel=M'
                if record.qr_public_url
                else False
            )

    @api.depends(
        'scan_ids',
        'scan_ids.scanned_at',
        'scan_ids.state',
        'scan_ids.outcome',
        'scan_ids.resolved_outcome',
        'scan_ids.existing_contact_found',
        'scan_ids.consent_newsletter',
        'scan_ids.consent_share_data',
        'scan_ids.partner_id',
    )
    def _compute_stats(self):
        Scan = self.env['qrbase.scan']
        for record in self:
            scans = record.scan_ids.sorted(lambda scan: (scan.scanned_at or fields.Datetime.now(), scan.id))
            summary = Scan._qrbase_summarize_scans(scans)
            record.scan_count = summary['scan_count']
            record.last_scan_at = scans[-1].scanned_at if scans else False
            record.opened_scan_count = summary['opened_count']
            record.registered_scan_count = summary['registered_count']
            record.unique_contact_count = summary['unique_contact_count']
            record.customer_count = summary['customer_count']
            record.prospect_count = summary['prospect_count']
            record.sample_count = summary['sample_count']
            record.duplicate_contact_count = summary['duplicate_count']
            record.newsletter_opt_in_count = summary['newsletter_count']
            record.data_share_consent_count = summary['data_consent_count']
            record.new_contact_count = summary['new_contact_count']
            record.customer_rate = summary['customer_rate']
            record.duplicate_rate = summary['duplicate_rate']
            record.newsletter_rate = summary['newsletter_rate']
            record.data_consent_rate = summary['data_consent_rate']

    def action_open_landing_page(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.qr_public_url,
            'target': 'new',
        }

    def action_print_qr_code(self):
        self.ensure_one()
        return self.env.ref('qrbase.action_report_qrbase_code').report_action(self)

    def action_open_code_analytics(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} Analytics',
            'res_model': 'qrbase.scan',
            'view_mode': 'pivot,graph,tree,form',
            'domain': [('code_id', '=', self.id)],
            'context': {
                'default_code_id': self.id,
                'group_by': 'resolved_outcome',
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
                'default_campaign_id': self.campaign_id.id,
                'default_code_id': self.id,
                'default_allocation_kind': self.campaign_id.allocation_kind,
            },
        }

    def _qrbase_scan_vals_from_request(self, httprequest):
        self.ensure_one()
        ip_address = httprequest.headers.get('X-Forwarded-For', httprequest.remote_addr or '')
        user_agent = httprequest.headers.get('User-Agent', '')
        referrer = httprequest.headers.get('Referer', '')
        return {
            'code_id': self.id,
            'landing_url': self.qr_public_url,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'referrer': referrer,
            'state': 'opened',
            'outcome': 'prospect',
        }

    def _qrbase_register_scan(self, scan, form_values):
        self.ensure_one()
        partner, lead, match_method, is_existing = self._qrbase_upsert_contact_and_lead(scan, form_values)
        outcome = partner._qrbase_determine_outcome_from_sales() if partner else 'prospect'
        scan.write({
            'state': 'registered',
            'outcome': outcome,
            'visitor_name': form_values.get('visitor_name'),
            'visitor_email': form_values.get('visitor_email'),
            'visitor_phone': form_values.get('visitor_phone'),
            'notes': form_values.get('notes'),
            'consent_newsletter': bool(form_values.get('consent_newsletter')),
            'consent_share_data': bool(form_values.get('consent_share_data')),
            'partner_id': partner.id if partner else False,
            'lead_id': lead.id if lead else False,
            'contact_match_method': match_method,
            'existing_contact_found': is_existing,
            'resolved_outcome': outcome,
        })
        if partner:
            partner._qrbase_apply_scan_preferences(
                code=self,
                scan=scan,
                consent_newsletter=bool(form_values.get('consent_newsletter')),
                consent_share_data=bool(form_values.get('consent_share_data')),
                outcome=outcome,
            )
            if outcome == 'customer':
                partner._qrbase_mark_customer(self, scan)
            else:
                partner._qrbase_mark_prospect(self, scan)
        return scan, partner, lead, match_method, is_existing

    def _qrbase_upsert_contact_and_lead(self, scan, form_values):
        self.ensure_one()
        partner, match_method, is_existing = self._qrbase_find_or_create_partner(form_values)
        lead = self._qrbase_find_or_create_lead(partner, scan, form_values)
        return partner, lead, match_method, is_existing

    def _qrbase_find_existing_partner(self, form_values):
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        email = (form_values.get('visitor_email') or '').strip().lower()
        phone = (form_values.get('visitor_phone') or '').strip()
        name = (form_values.get('visitor_name') or '').strip()
        if email:
            partner = Partner.search([('email', '=ilike', email)], limit=1)
            if partner:
                return partner, 'email'
        if phone:
            partner = Partner.search(['|', ('mobile', '=', phone), ('phone', '=', phone)], limit=1)
            if partner:
                return partner, 'phone'
        if name:
            partner = Partner.search([('name', '=ilike', name)], limit=1)
            if partner:
                return partner, 'name'
        return Partner.browse(), False

    def _qrbase_find_or_create_partner(self, form_values):
        self.ensure_one()
        Partner = self.env['res.partner'].sudo()
        email = (form_values.get('visitor_email') or '').strip().lower()
        phone = (form_values.get('visitor_phone') or '').strip()
        name = (form_values.get('visitor_name') or '').strip()
        partner, match_method = self._qrbase_find_existing_partner(form_values)
        is_existing = bool(partner)

        partner_vals = {
            'name': name or self.name,
            'email': email or False,
            'phone': phone or False,
        }
        if partner:
            updates = {key: value for key, value in partner_vals.items() if value and not partner[key]}
            if updates:
                partner.write(updates)
        else:
            partner = Partner.create(partner_vals)
            match_method = False
            is_existing = False

        return partner.commercial_partner_id or partner, match_method, is_existing

    def _qrbase_find_or_create_lead(self, partner, scan, form_values):
        self.ensure_one()
        Lead = self.env['crm.lead'].sudo()
        lead_name = form_values.get('visitor_name') or form_values.get('visitor_email') or self.name
        lead = Lead.search([
            ('qrbase_code_id', '=', self.id),
            ('partner_id', '=', partner.id if partner else False),
        ], limit=1)

        lead_vals = {
            'name': lead_name,
            'partner_id': partner.id if partner else False,
            'source_id': self.utm_source_id.id,
            'email_from': form_values.get('visitor_email') or False,
            'phone': form_values.get('visitor_phone') or False,
            'description': form_values.get('notes') or False,
            'qrbase_code_id': self.id,
            'qrbase_scan_id': scan.id,
        }
        if lead:
            lead.write(lead_vals)
        else:
            lead = Lead.create(lead_vals)
        return lead

    def _qrbase_landing_values(self, scan, submitted, form_values, csrf_token):
        self.ensure_one()
        return {
            'code': self,
            'campaign': self.campaign_id,
            'scan': scan,
            'submitted': submitted,
            'form_values': form_values,
            'target_url': self.target_url or self.campaign_id.target_url,
            'csrf_token': csrf_token,
            'theme_class': 'o_qrbase_theme_light' if self.campaign_id.landing_theme == 'light' else 'o_qrbase_theme_dark',
            'landing_logo_url': self.campaign_id.landing_logo_url,
        }

    def _qrbase_embed_logo(self, barcode, logo_b64):
        barcode_image = Image.open(BytesIO(barcode)).convert('RGBA')
        logo_image = Image.open(BytesIO(base64.b64decode(logo_b64))).convert('RGBA')

        qr_width, qr_height = barcode_image.size
        target_size = max(int(min(qr_width, qr_height) * 0.24), 72)
        logo_image = ImageOps.contain(logo_image, (target_size, target_size), method=Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)

        logo_box = Image.new('RGBA', (logo_image.width + 28, logo_image.height + 28), (255, 255, 255, 255))
        mask = Image.new('L', logo_box.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, logo_box.width - 1, logo_box.height - 1), radius=24, fill=255)
        logo_box = Image.composite(logo_box, Image.new('RGBA', logo_box.size, (255, 255, 255, 255)), mask)
        paste_x = (barcode_image.width - logo_box.width) // 2
        paste_y = (barcode_image.height - logo_box.height) // 2
        barcode_image.alpha_composite(logo_box, (paste_x, paste_y))
        logo_x = paste_x + (logo_box.width - logo_image.width) // 2
        logo_y = paste_y + (logo_box.height - logo_image.height) // 2
        barcode_image.alpha_composite(logo_image, (logo_x, logo_y))

        output = BytesIO()
        barcode_image.convert('RGB').save(output, format='PNG')
        return output.getvalue()
