from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class QrbaseController(http.Controller):

    @http.route(['/qrbase/s/<string:token>'], type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=True)
    def qrbase_scan_landing(self, token, **post):
        code = request.env['qrbase.code'].sudo().search([('token', '=', token), ('active', '=', True)], limit=1)
        if not code:
            raise NotFound()

        submitted = request.httprequest.method == 'POST'
        contact_message = False
        contact_status = False
        contact_is_existing = False
        if request.httprequest.method == 'POST':
            scan_id = int(post.get('scan_id') or 0)
            scan = request.env['qrbase.scan'].sudo().browse(scan_id).exists() if scan_id else False
            if not scan or scan.code_id.id != code.id:
                scan = request.env['qrbase.scan'].sudo().create(code._qrbase_scan_vals_from_request(request.httprequest))
        else:
            scan = request.env['qrbase.scan'].sudo().create(code._qrbase_scan_vals_from_request(request.httprequest))

        values = code._qrbase_landing_values(scan=scan, submitted=False, form_values={}, csrf_token=request.csrf_token())
        values.update({
            'contact_message': contact_message,
            'contact_status': contact_status,
            'contact_is_existing': contact_is_existing,
            'partner': False,
            'lead': False,
        })

        if submitted:
            form_values = {
                'visitor_name': (post.get('visitor_name') or '').strip(),
                'visitor_email': (post.get('visitor_email') or '').strip(),
                'visitor_phone': (post.get('visitor_phone') or '').strip(),
                'notes': (post.get('notes') or '').strip(),
                'consent_newsletter': bool(post.get('consent_newsletter')),
                'consent_share_data': bool(post.get('consent_share_data')),
            }
            scan, partner, lead, match_method, is_existing = code._qrbase_register_scan(scan, form_values)
            contact_is_existing = bool(is_existing)
            if is_existing and partner:
                contact_message = f'We found an existing contact for {partner.display_name}. No duplicate was created.'
                contact_status = match_method
            elif partner:
                contact_message = f'New contact created for {partner.display_name}.'
            values = code._qrbase_landing_values(scan=scan, submitted=True, form_values=form_values, csrf_token=request.csrf_token())
            values.update({
                'contact_message': contact_message,
                'contact_status': contact_status,
                'contact_is_existing': contact_is_existing,
                'partner': partner,
                'lead': lead,
            })

        return request.render('qrbase.qrbase_scan_landing_page', values)
