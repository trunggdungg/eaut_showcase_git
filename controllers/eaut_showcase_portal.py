# -*- coding: utf-8 -*-
import logging
import urllib.parse

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class AdvisorPortalController(http.Controller):

    def _get_open_term(self):
        return request.env['eaut_showcase.term'].sudo().search(
            [('state', '=', 'open')], order='date_start desc', limit=1)

    def _get_registration(self, term):
        partner = request.env.user.partner_id
        return request.env['eaut_showcase.advisor.registration'].sudo().search([
            ('term_id', '=', term.id), ('student_id', '=', partner.id),
        ], limit=1)

    # ============ SINH VIÊN: CHỌN GIẢNG VIÊN HƯỚNG DẪN ============
    @http.route(['/my/advisor'], type='http', auth='user', website=True, sitemap=False)
    def my_advisor(self, **kw):
        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        capacities = request.env['eaut_showcase.term.capacity']
        if term:
            capacities = request.env['eaut_showcase.term.capacity'].sudo().search([
                ('term_id', '=', term.id), ('withdrawn', '=', False),
            ])
        values = {
            'term': term,
            'registration': registration,
            'capacities': capacities,
            'max_preferences': term.max_preferences if term else 5,
            'partner': request.env.user.partner_id,
            'submitted': kw.get('submitted'),
            'error': kw.get('error'),
        }
        return request.render('eaut_showcase.portal_my_advisor', values)

    @http.route(['/my/advisor/profile'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def my_advisor_profile(self, **post):
        student_code = (post.get('student_code') or '').strip()
        student_class = (post.get('student_class') or '').strip()
        student_major = (post.get('student_major') or '').strip()
        if not (student_code and student_class and student_major):
            error = urllib.parse.quote('Vui lòng điền đầy đủ MSSV, lớp và ngành học.')
            return request.redirect(f'/my/advisor?error={error}')
        request.env.user.partner_id.write({
            'showcase_student_code': student_code,
            'showcase_student_class': student_class,
            'showcase_student_major': student_major,
        })
        return request.redirect('/my/advisor')

    @http.route(['/my/advisor/submit'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def my_advisor_submit(self, **post):
        term = self._get_open_term()
        if not term:
            return request.redirect('/my/advisor')

        partner = request.env.user.partner_id
        if not partner.showcase_student_code:
            error = urllib.parse.quote('Vui lòng hoàn thiện hồ sơ (MSSV, lớp, ngành) trước.')
            return request.redirect(f'/my/advisor?error={error}')
        Registration = request.env['eaut_showcase.advisor.registration'].sudo()
        registration = Registration.search([
            ('term_id', '=', term.id), ('student_id', '=', partner.id),
        ], limit=1)
        if not registration:
            registration = Registration.create({
                'term_id': term.id, 'student_id': partner.id,
            })
        if registration.line_ids:
            error = urllib.parse.quote('Bạn đã nộp nguyện vọng cho kỳ này rồi.')
            return request.redirect(f'/my/advisor?error={error}')

        creator_ids = [int(v) for v in request.httprequest.form.getlist('creator_ids') if v]
        if not creator_ids:
            error = urllib.parse.quote('Vui lòng chọn ít nhất 1 giảng viên.')
            return request.redirect(f'/my/advisor?error={error}')
        if len(creator_ids) != len(set(creator_ids)):
            error = urllib.parse.quote('Không được chọn trùng 1 giảng viên ở nhiều nguyện vọng.')
            return request.redirect(f'/my/advisor?error={error}')

        try:
            registration.action_submit(creator_ids)
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor?error={urllib.parse.quote(str(e))}')
        except Exception as e:
            _logger.error('Lỗi khi sinh viên nộp nguyện vọng chọn giảng viên: %s', e, exc_info=True)
            error = urllib.parse.quote('Có lỗi xảy ra, vui lòng thử lại.')
            return request.redirect(f'/my/advisor?error={error}')

        return request.redirect('/my/advisor?submitted=1')

    # ============ GIẢNG VIÊN: DUYỆT YÊU CẦU HƯỚNG DẪN ============
    def _get_creator_for_current_user(self):
        return request.env['eaut_showcase.creator'].sudo().search(
            [('user_id', '=', request.env.user.id)], limit=1)

    @http.route(['/my/advisor-requests'], type='http', auth='user', website=True, sitemap=False)
    def my_advisor_requests(self, **kw):
        creator = self._get_creator_for_current_user()
        lines = request.env['eaut_showcase.advisor.registration.line']
        if creator:
            lines = lines.sudo().search([
                ('creator_id', '=', creator.id),
                ('state', '=', 'pending'),
            ], order='activated_date asc')
        values = {
            'creator': creator,
            'lines': lines,
            'done': kw.get('done'),
            'error': kw.get('error'),
        }
        return request.render('eaut_showcase.portal_my_advisor_requests', values)

    def _decide_request(self, line_id, approve):
        creator = self._get_creator_for_current_user()
        line = request.env['eaut_showcase.advisor.registration.line'].sudo().browse(line_id)
        if not creator or not line.exists() or line.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1')
        try:
            line.action_approve() if approve else line.action_reject()
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor-requests?error={urllib.parse.quote(str(e))}')
        except Exception as e:
            _logger.error('Lỗi khi giảng viên xử lý yêu cầu hướng dẫn: %s', e, exc_info=True)
            return request.redirect('/my/advisor-requests?error=1')
        return request.redirect('/my/advisor-requests?done=1')

    @http.route(['/my/advisor-requests/<int:line_id>/approve'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_request_approve(self, line_id, **post):
        return self._decide_request(line_id, approve=True)

    @http.route(['/my/advisor-requests/<int:line_id>/reject'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_request_reject(self, line_id, **post):
        return self._decide_request(line_id, approve=False)