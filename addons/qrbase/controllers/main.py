from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class QrbaseController(http.Controller):

    @http.route(['/qrbase/s/<string:token>'], type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=True)
    def qrbase_scan_landing(self, token, **post):
        code = request.env['qrbase.code'].sudo().search([('token', '=', token), ('active', '=', True)], limit=1)
        if not code:
            raise NotFound()

        submitted = False
        contact_message = False
        contact_status = False
        contact_is_existing = False
        form_error = False
        partner = False
        lead = False
        form_values = {}
        if request.httprequest.method == 'POST':
            scan_id = int(post.get('scan_id') or 0)
            scan = request.env['qrbase.scan'].sudo().browse(scan_id).exists() if scan_id else False
            if not scan or scan.code_id.id != code.id:
                scan = request.env['qrbase.scan'].sudo().create(code._qrbase_scan_vals_from_request(request.httprequest))
            form_values = code._qrbase_parse_landing_form(post)
            form_error = code._qrbase_validate_landing_form(form_values)
            if not form_error:
                otp_code = (form_values.get('otp_code') or '').strip()
                if scan.otp_status == 'pending' and scan.otp_code:
                    otp_pending = True
                    otp_display_code = scan.otp_code
                    if otp_code and otp_code == scan.otp_code:
                        scan, partner, lead, match_method, is_existing = code._qrbase_register_scan(scan, form_values)
                        submitted = True
                        contact_is_existing = bool(is_existing)
                        contact_status = match_method if is_existing else False
                        if is_existing and partner:
                            contact_message = f'We found your existing contact record for {partner.display_name}. No duplicate was created.'
                        elif partner:
                            contact_message = f'Your contact record was created for {partner.display_name}.'
                        otp_pending = False
                        otp_display_code = False
                    elif otp_code:
                        form_error = 'The verification code does not match. Please try again.'
                else:
                    otp_code = code._qrbase_pending_otp_code(scan)
                    code._qrbase_prepare_pending_registration(scan, form_values, otp_code)
                    otp_pending = True
                    otp_display_code = otp_code
            if not form_error and not submitted and not otp_pending:
                otp_pending = bool(scan.otp_status == 'pending' and scan.otp_code)
                otp_display_code = scan.otp_code if otp_pending else False
        else:
            scan = request.env['qrbase.scan'].sudo().create(code._qrbase_scan_vals_from_request(request.httprequest))

        otp_pending = bool(scan.otp_status == 'pending' and scan.otp_code)
        otp_display_code = scan.otp_code if otp_pending else False
        if submitted:
            otp_pending = False
            otp_display_code = False

        values = code._qrbase_landing_values(
            scan=scan,
            submitted=submitted,
            form_values=form_values,
            csrf_token=request.csrf_token(),
        )
        values.update({
            'contact_message': contact_message,
            'contact_status': contact_status,
            'contact_is_existing': contact_is_existing,
            'partner': partner,
            'lead': lead,
            'form_error': form_error,
            'otp_pending': otp_pending,
            'otp_display_code': otp_display_code,
            'otp_verified': bool(scan.otp_status == 'verified'),
        })

        return request.render('qrbase.qrbase_scan_landing_page', values)
