# -*- coding: utf-8 -*-
import base64
import logging
import urllib.parse

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class AdvisorPortalController(http.Controller):

    def _get_open_term(self):
        """Chọn đúng kỳ đang mở cho sinh viên hiện tại — nếu 1 kỳ có khai
                danh sách 'Sinh viên đủ điều kiện' thì chỉ những SV trong danh sách
                đó mới thấy kỳ này (dùng khi nhiều khoa mở kỳ song song); kỳ không
                khai danh sách thì mở cho mọi sinh viên."""
        partner = request.env.user.partner_id
        terms = request.env['eaut_showcase.term'].sudo().search(
            [('state', '=', 'open')], order='date_start desc')
        for term in terms:
            if not term.eligible_student_ids or partner in term.eligible_student_ids:
                return term
        return request.env['eaut_showcase.term']

    def _get_registration(self, term):
        partner = request.env.user.partner_id
        return request.env['eaut_showcase.advisor.registration'].sudo().search([
            ('term_id', '=', term.id), ('student_id', '=', partner.id),
        ], limit=1)

    # ============ SINH VIÊN: CHỌN GIẢNG VIÊN HƯỚNG DẪN ============
    @http.route(['/my/advisor'], type='http', auth='user', website=True, sitemap=False)
    def my_advisor(self, **kw):
        lecturer_profile = self._get_creator_for_current_user()
        if lecturer_profile:
            return request.render('eaut_showcase.portal_my_advisor', {
                'lecturer_profile': lecturer_profile,
            })

        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        capacities = request.env['eaut_showcase.term.capacity']
        if term:
            capacities = request.env['eaut_showcase.term.capacity'].sudo().search([
                ('term_id', '=', term.id), ('withdrawn', '=', False),
            ])
        values = {
            'lecturer_profile': False,
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
        if self._get_creator_for_current_user():
            error = urllib.parse.quote(
                'Tài khoản này đã đăng ký làm giảng viên hướng dẫn, không thể dùng để '
                'đăng ký chọn giảng viên hướng dẫn.')
            return request.redirect(f'/my/advisor?error={error}')

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
        if self._get_creator_for_current_user():
            error = urllib.parse.quote(
                'Tài khoản này đã đăng ký làm giảng viên hướng dẫn, không thể dùng để '
                'đăng ký chọn giảng viên hướng dẫn.')
            return request.redirect(f'/my/advisor?error={error}')
        term = self._get_open_term()
        if not term:
            return request.redirect('/my/advisor')

        partner = request.env.user.partner_id
        if not partner.showcase_student_code:
            error = urllib.parse.quote('Vui lòng hoàn thiện hồ sơ (MSSV, lớp, ngành) trước.')
            return request.redirect(f'/my/advisor?error={error}')
        Registration = request.env['eaut_showcase.advisor.registration'].sudo()
        existing = Registration.search([
            ('term_id', '=', term.id), ('student_id', '=', partner.id),
        ], limit=1)
        if existing and existing.line_ids:
            error = urllib.parse.quote('Bạn đã nộp nguyện vọng cho kỳ này rồi.')
            return request.redirect(f'/my/advisor?error={error}')

        creator_ids = [int(v) for v in request.httprequest.form.getlist('creator_ids') if v]
        if not creator_ids:
            error = urllib.parse.quote('Vui lòng chọn ít nhất 1 giảng viên.')
            return request.redirect(f'/my/advisor?error={error}')
        if len(creator_ids) != len(set(creator_ids)):
            error = urllib.parse.quote('Không được chọn trùng 1 giảng viên ở nhiều nguyện vọng.')
            return request.redirect(f'/my/advisor?error={error}')

        registration = existing or Registration.create({
            'term_id': term.id, 'student_id': partner.id,
        })

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
        Line = request.env['eaut_showcase.advisor.registration.line']
        pending_lines = approved_lines = history_lines = Line
        open_terms = request.env['eaut_showcase.term']
        capacities_by_term = {}
        if creator:
            pending_lines = Line.sudo().search([
                ('creator_id', '=', creator.id), ('state', '=', 'pending'),
            ], order='activated_date asc')
            approved_lines = Line.sudo().search([
                ('creator_id', '=', creator.id), ('state', '=', 'approved'),
            ], order='decided_date desc')
            history_lines = Line.sudo().search([
                ('creator_id', '=', creator.id),
                ('state', 'in', ('rejected', 'expired', 'cancelled')),
            ], order='decided_date desc')
            open_terms = request.env['eaut_showcase.term'].sudo().search(
                [('state', '=', 'open')], order='date_start desc')
            for term in open_terms:
                capacities_by_term[term.id] = self._get_capacity_for_term(creator, term)
        values = {
            'creator': creator,
            'pending_lines': pending_lines,
            'approved_lines': approved_lines,
            'history_lines': history_lines,
            'open_terms': open_terms,
            'capacities_by_term': capacities_by_term,
            'done': kw.get('done'),
            'error': kw.get('error'),
        }
        return request.render('eaut_showcase.portal_my_advisor_requests', values)

    def _get_capacity_for_term(self, creator, term):
        return request.env['eaut_showcase.term.capacity'].sudo().search([
            ('term_id', '=', term.id), ('creator_id', '=', creator.id),
        ], limit=1)

        # ============ GIẢNG VIÊN: TỰ QUẢN LÝ SỨC CHỨA ============

    @http.route(['/my/advisor-requests/capacity/register'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_register(self, **post):
        creator = self._get_creator_for_current_user()
        if not creator:
            return request.redirect('/my/advisor-requests?error=1')
        term = request.env['eaut_showcase.term'].sudo().browse(
            int(post.get('term_id') or 0)).exists()
        if not term or term.state != 'open':
            error = urllib.parse.quote('Kỳ này hiện không mở đăng ký.')
            return request.redirect(f'/my/advisor-requests?error={error}')
        try:
            max_students = int(post.get('max_students') or 0)
        except ValueError:
            max_students = 0
        if max_students < 1:
            error = urllib.parse.quote('Số sinh viên tối đa phải lớn hơn 0.')
            return request.redirect(f'/my/advisor-requests?error={error}')

        capacity = self._get_capacity_for_term(creator, term)
        try:
            if capacity:
                capacity.write({'max_students': max_students, 'withdrawn': False})
            else:
                request.env['eaut_showcase.term.capacity'].sudo().create({
                    'term_id': term.id, 'creator_id': creator.id, 'max_students': max_students,
                })
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor-requests?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor-requests?done=1')

    @http.route(['/my/advisor-requests/capacity/<int:capacity_id>/update'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_update(self, capacity_id, **post):
        creator = self._get_creator_for_current_user()
        capacity = request.env['eaut_showcase.term.capacity'].sudo().browse(capacity_id).exists()
        if not creator or not capacity or capacity.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1')
        try:
            max_students = int(post.get('max_students') or 0)
        except ValueError:
            max_students = 0
        if max_students < 1:
            error = urllib.parse.quote('Số sinh viên tối đa phải lớn hơn 0.')
            return request.redirect(f'/my/advisor-requests?error={error}')
        try:
            capacity.write({'max_students': max_students})
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor-requests?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor-requests?done=1')

    @http.route(['/my/advisor-requests/capacity/<int:capacity_id>/withdraw'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_withdraw(self, capacity_id, **post):
        creator = self._get_creator_for_current_user()
        capacity = request.env['eaut_showcase.term.capacity'].sudo().browse(capacity_id).exists()
        if not creator or not capacity or capacity.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1')
        try:
            capacity.action_withdraw()
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor-requests/capacity?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor-requests/capacity?done=1')

        # ============ GIẢNG VIÊN: QUẢN LÝ HỒ SƠ ============

    @http.route(['/my/advisor-requests/profile'], type='http', auth='user', website=True,
                methods=['GET'], sitemap=False)
    def my_advisor_lecturer_profile(self, **kw):
        creator = self._get_creator_for_current_user()
        if not creator:
            return request.redirect('/my/advisor-requests?error=1')
        values = {
            'creator': creator,
            'all_categories': request.env['eaut_showcase.category'].sudo().search(
                [], order='sequence, id'),
            'all_locations': request.env['res.country.state'].sudo().search(
                [('country_id.code', '=', 'VN')], order='name'),
            'done': kw.get('done'),
            'error': kw.get('error'),
        }
        return request.render('eaut_showcase.portal_my_advisor_lecturer_profile', values)

    @http.route(['/my/advisor-requests/profile'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def my_advisor_lecturer_profile_save(self, **post):
        creator = self._get_creator_for_current_user()
        if not creator:
            return request.redirect('/my/advisor-requests?error=1')

        name = (post.get('name') or '').strip()
        if not name:
            error = urllib.parse.quote('Vui lòng nhập tên hiển thị.')
            return request.redirect(f'/my/advisor-requests/profile?error={error}')

        category_ids = [int(v) for v in request.httprequest.form.getlist('category_ids') if v]
        vals = {
            'name': name,
            'role': (post.get('role') or '').strip(),
            'bio': (post.get('bio') or '').strip(),
            'email': (post.get('email') or '').strip(),
            'website_url': (post.get('website_url') or '').strip(),
            'location_id': int(post.get('location_id')) if post.get('location_id') else False,
            'category_ids': [(6, 0, category_ids)],
        }
        avatar_file = request.httprequest.files.get('avatar')
        if avatar_file and avatar_file.filename:
            vals['avatar'] = base64.b64encode(avatar_file.read())

        try:
            creator.write(vals)
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor-requests/profile?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor-requests/profile?done=1')

    def _decide_request(self, line_id, approve, reason=None):
        creator = self._get_creator_for_current_user()
        line = request.env['eaut_showcase.advisor.registration.line'].sudo().browse(line_id)
        if not creator or not line.exists() or line.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1')
        try:
            line.action_approve() if approve else line.action_reject(reason)
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
        return self._decide_request(line_id, approve=False, reason=post.get('reason'))
