import base64
import csv
from datetime import date, datetime, time, timedelta
from io import StringIO

from odoo import api, fields, models


class QrbaseReportWizard(models.TransientModel):
    _name = 'qrbase.report.wizard'
    _description = 'QR Insights Report Wizard'

    date_from = fields.Date(
        string='From',
        help='Optional start date for the report window.',
    )
    date_to = fields.Date(
        string='To',
        help='Optional end date for the report window.',
    )
    campaign_id = fields.Many2one(
        'qrbase.campaign',
        string='Campaign',
        help='Restrict the report to a single QR campaign.',
    )
    code_id = fields.Many2one(
        'qrbase.code',
        string='QR Code',
        domain="[('campaign_id', '=', campaign_id)]",
        help='Restrict the report to a specific QR code.',
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
        string='Allocation',
        help='Filter the report to a specific campaign allocation type.',
    )
    outcome = fields.Selection(
        [
            ('all', 'All'),
            ('opened', 'Opened'),
            ('registered', 'Registered'),
            ('prospect', 'Prospect'),
            ('customer', 'Customer'),
            ('sample', 'Sample'),
        ],
        default='all',
        string='Lifecycle Outcome',
        help='Filter scans by the outcome classification you want to analyze.',
    )
    contact_match_method = fields.Selection(
        [
            ('all', 'All'),
            ('email', 'Email'),
            ('phone', 'Phone'),
            ('name', 'Name'),
        ],
        default='all',
        string='Match Method',
        help='Filter to the way matching contacts were found.',
    )
    existing_contact_filter = fields.Selection(
        [
            ('all', 'All'),
            ('existing', 'Existing'),
            ('new', 'New'),
        ],
        default='all',
        string='Contact Type',
        help='Show only existing contacts, only new contacts, or both.',
    )
    newsletter_filter = fields.Selection(
        [
            ('all', 'All'),
            ('opt_in', 'Opted In'),
            ('opt_out', 'Not Opted In'),
        ],
        default='all',
        string='Newsletter Consent',
        help='Filter by newsletter consent status.',
    )
    data_share_filter = fields.Selection(
        [
            ('all', 'All'),
            ('opt_in', 'Consented'),
            ('opt_out', 'Not Consented'),
        ],
        default='all',
        string='Data Sharing Consent',
        help='Filter by data-sharing consent status.',
    )
    report_title = fields.Char(compute='_compute_metrics', help='A human-readable title for the report summary.')
    scan_count = fields.Integer(compute='_compute_metrics', help='Total scans in the selected report window.')
    opened_count = fields.Integer(compute='_compute_metrics', help='How many scans only opened the landing page.')
    registered_count = fields.Integer(compute='_compute_metrics', help='How many scans submitted contact details.')
    unique_contact_count = fields.Integer(compute='_compute_metrics', help='How many unique contacts were involved.')
    customer_count = fields.Integer(compute='_compute_metrics', help='How many scans resolved to customers.')
    prospect_count = fields.Integer(compute='_compute_metrics', help='How many scans resolved to prospects.')
    sample_count = fields.Integer(compute='_compute_metrics', help='How many scans were marked as sample.')
    duplicate_count = fields.Integer(compute='_compute_metrics', help='How many scans matched an existing contact.')
    newsletter_count = fields.Integer(compute='_compute_metrics', help='How many scans had newsletter consent.')
    data_consent_count = fields.Integer(compute='_compute_metrics', help='How many scans had data sharing consent.')
    customer_rate = fields.Float(compute='_compute_metrics', help='Customer share as a percentage of scans.')
    duplicate_rate = fields.Float(compute='_compute_metrics', help='Duplicate share as a percentage of scans.')
    newsletter_rate = fields.Float(compute='_compute_metrics', help='Newsletter consent share as a percentage of scans.')
    data_consent_rate = fields.Float(compute='_compute_metrics', help='Data sharing consent share as a percentage of scans.')
    export_file = fields.Binary(readonly=True)
    export_filename = fields.Char(readonly=True)

    @api.depends(
        'date_from', 'date_to', 'campaign_id', 'code_id', 'allocation_kind',
        'outcome', 'contact_match_method', 'existing_contact_filter',
        'newsletter_filter', 'data_share_filter',
    )
    def _compute_metrics(self):
        Scan = self.env['qrbase.scan'].sudo()
        for wizard in self:
            scans = Scan.search(wizard._qrbase_domain(), order='scanned_at desc, id desc')
            summary = Scan._qrbase_summarize_scans(scans)
            title_bits = ['QR Insights']
            if wizard.campaign_id:
                title_bits.append(wizard.campaign_id.name)
            if wizard.code_id:
                title_bits.append(wizard.code_id.name)
            wizard.report_title = ' - '.join(title_bits)
            wizard.scan_count = summary['scan_count']
            wizard.opened_count = summary['opened_count']
            wizard.registered_count = summary['registered_count']
            wizard.unique_contact_count = summary['unique_contact_count']
            wizard.customer_count = summary['customer_count']
            wizard.prospect_count = summary['prospect_count']
            wizard.sample_count = summary['sample_count']
            wizard.duplicate_count = summary['duplicate_count']
            wizard.newsletter_count = summary['newsletter_count']
            wizard.data_consent_count = summary['data_consent_count']
            wizard.customer_rate = summary['customer_rate']
            wizard.duplicate_rate = summary['duplicate_rate']
            wizard.newsletter_rate = summary['newsletter_rate']
            wizard.data_consent_rate = summary['data_consent_rate']

    def _qrbase_domain(self):
        self.ensure_one()
        domain = []
        if self.date_from:
            domain.append(('scanned_at', '>=', datetime.combine(self.date_from, time.min)))
        if self.date_to:
            domain.append(('scanned_at', '<', datetime.combine(self.date_to + timedelta(days=1), time.min)))
        if self.campaign_id:
            domain.append(('campaign_id', '=', self.campaign_id.id))
        if self.code_id:
            domain.append(('code_id', '=', self.code_id.id))
        if self.allocation_kind:
            domain.append(('campaign_id.allocation_kind', '=', self.allocation_kind))
        if self.outcome == 'opened':
            domain.append(('state', '=', 'opened'))
        elif self.outcome == 'registered':
            domain.append(('state', '=', 'registered'))
        elif self.outcome == 'prospect':
            domain.append(('resolved_outcome', '=', 'prospect'))
        elif self.outcome == 'customer':
            domain.append(('resolved_outcome', '=', 'customer'))
        elif self.outcome == 'sample':
            domain.append(('outcome', '=', 'sample'))
        if self.contact_match_method != 'all':
            domain.append(('contact_match_method', '=', self.contact_match_method))
        if self.existing_contact_filter == 'existing':
            domain.append(('existing_contact_found', '=', True))
        elif self.existing_contact_filter == 'new':
            domain.append(('existing_contact_found', '=', False))
        if self.newsletter_filter == 'opt_in':
            domain.append(('consent_newsletter', '=', True))
        elif self.newsletter_filter == 'opt_out':
            domain.append(('consent_newsletter', '=', False))
        if self.data_share_filter == 'opt_in':
            domain.append(('consent_share_data', '=', True))
        elif self.data_share_filter == 'opt_out':
            domain.append(('consent_share_data', '=', False))
        return domain

    def _qrbase_get_scans(self):
        self.ensure_one()
        return self.env['qrbase.scan'].sudo().search(self._qrbase_domain(), order='scanned_at desc, id desc')

    def _qrbase_csv_content(self):
        self.ensure_one()
        scans = self._qrbase_get_scans()
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow([
            'Scanned At',
            'Campaign',
            'QR Code',
            'State',
            'Outcome',
            'Resolved Outcome',
            'Existing Contact',
            'Match Method',
            'Name',
            'Email',
            'Phone',
            'Newsletter Consent',
            'Data Share Consent',
            'Partner',
            'Lead',
            'Notes',
        ])
        for scan in scans:
            writer.writerow([
                fields.Datetime.to_string(scan.scanned_at) if scan.scanned_at else '',
                scan.campaign_id.name or '',
                scan.code_id.name or '',
                scan.state or '',
                scan.outcome or '',
                scan.resolved_outcome or '',
                'Yes' if scan.existing_contact_found else 'No',
                scan.contact_match_method or '',
                scan.visitor_name or '',
                scan.visitor_email or '',
                scan.visitor_phone or '',
                'Yes' if scan.consent_newsletter else 'No',
                'Yes' if scan.consent_share_data else 'No',
                scan.partner_id.display_name or '',
                scan.lead_id.display_name or '',
                scan.notes or '',
            ])
        content = stream.getvalue().encode('utf-8')
        stream.close()
        return content

    def action_view_analysis(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.report_title,
            'res_model': 'qrbase.scan',
            'view_mode': 'pivot,graph,tree,form',
            'domain': self._qrbase_domain(),
            'context': {
                'default_campaign_id': self.campaign_id.id,
                'default_code_id': self.code_id.id,
            },
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('qrbase.action_report_qrbase_insights').report_action(self)

    def action_export_csv(self):
        self.ensure_one()
        filename_bits = ['qrbase-insights']
        if self.campaign_id:
            filename_bits.append(self.campaign_id.name.replace(' ', '_'))
        if self.code_id:
            filename_bits.append(self.code_id.name.replace(' ', '_'))
        if self.date_from:
            filename_bits.append(self.date_from.isoformat())
        if self.date_to:
            filename_bits.append(self.date_to.isoformat())
        self.write({
            'export_filename': '%s.csv' % '-'.join(filename_bits),
            'export_file': base64.b64encode(self._qrbase_csv_content()),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=qrbase.report.wizard&id=%s&field=export_file&download=true&filename=%s' % (self.id, self.export_filename),
            'target': 'self',
        }
