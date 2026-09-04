# -*- coding: utf-8 -*-
import base64
import logging
import urllib.parse

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class AdvisorPortalController(http.Controller):

    def _get_open_term(self):
        """Chọn đúng kỳ đang mở cho sinh viên hiện tại — BẮT BUỘC sinh viên
        phải có tên trong 'Sinh viên đủ điều kiện' của kỳ đó, không có ngoại
        lệ. Để trống danh sách KHÔNG còn nghĩa là "mở cho mọi sinh viên" nữa
        — kỳ đó chỉ đơn giản là chưa ai đăng ký được cho tới khi Admin khai
        danh sách. Lấy kỳ mới nhất (date_start desc) trong số các kỳ sinh
        viên này có tên, phòng trường hợp SV được khai ở nhiều kỳ mở song
        song (nhiều khoa)."""
        partner = request.env.user.partner_id
        terms = request.env['eaut_showcase.term'].sudo().search(
            [('state', '=', 'open')], order='date_start desc')
        for term in terms:
            if partner in term.eligible_student_ids:
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

        partner = request.env.user.partner_id
        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        if not registration:
            # Kỳ của SV đã Chốt danh sách/Đã đóng (không còn 'open') nhưng
            # hồ sơ đăng ký thật sự đã nộp/được xử lý (in_progress/approved/
            # unassigned) — vẫn cho SV xem lại trạng thái, không để "biến
            # mất" khỏi portal chỉ vì kỳ đổi trạng thái trong lúc GV chưa xử
            # lý xong (GV vẫn duyệt/từ chối được tới khi kỳ thật sự "Đã
            # đóng" — xem action_approve/action_reject). Loại 'draft' vì đó
            # là hồ sơ chưa từng nộp gì, không có ý nghĩa để xem lại.
            fallback_registration = request.env['eaut_showcase.advisor.registration'].sudo().search([
                ('student_id', '=', partner.id), ('state', '!=', 'draft'),
            ], order='create_date desc', limit=1)
            if fallback_registration:
                term = fallback_registration.term_id
                registration = fallback_registration
        # Phân biệt 2 trường hợp trả về rỗng — không thì SV không đủ điều
        # kiện dễ tưởng nhầm là "chưa tới đợt đăng ký" (xem template).
        not_eligible = not term and bool(
            request.env['eaut_showcase.term'].sudo().search_count([('state', '=', 'open')]))

        capacities = request.env['eaut_showcase.term.capacity']
        if term:
            capacities = request.env['eaut_showcase.term.capacity'].sudo().search([
                ('term_id', '=', term.id), ('withdrawn', '=', False),
            ])
        max_preferences = term.max_preferences if term else 5
        all_lines = registration.line_ids if registration else request.env['eaut_showcase.advisor.registration.line']
        # Giỏ nguyện vọng (chưa nộp) hiển thị riêng khỏi các dòng đã nộp
        # (waiting/pending/approved/rejected/expired/cancelled) — SV tự do
        # thêm/xoá/đổi thứ tự trong giỏ, chỉ khoá lại sau khi bấm "Nộp".
        cart_lines = all_lines.filtered(lambda l: l.state == 'cart').sorted('sequence')
        submitted_lines = (all_lines - cart_lines).sorted('sequence')
        has_submitted = bool(registration) and not registration._can_edit_cart()
        tried_creator_ids = cart_lines.mapped('creator_id').ids
        available_capacities = capacities.filtered(
            lambda c: c.creator_id.id not in tried_creator_ids)
        values = {
            'lecturer_profile': False,
            'term': term,
            'not_eligible': not_eligible,
            'registration': registration,
            'capacities': available_capacities,
            'max_preferences': max_preferences,
            'cart_lines': cart_lines,
            'submitted_lines': submitted_lines,
            'cart_full': len(cart_lines) >= max_preferences,
            'has_submitted': has_submitted,
            'partner': partner,
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
        student_phone = (post.get('student_phone') or '').strip()
        if not (student_code and student_class and student_major and student_phone):
            error = urllib.parse.quote('Vui lòng điền đầy đủ MSV, lớp, ngành học và số điện thoại.')
            return request.redirect(f'/my/advisor?error={error}')
        request.env.user.partner_id.write({
            'showcase_student_code': student_code,
            'showcase_student_class': student_class,
            'showcase_student_major': student_major,
            'phone': student_phone,
        })
        return request.redirect('/my/advisor')

    @http.route(['/my/advisor/cart/add'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def my_advisor_cart_add(self, **post):
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
            error = urllib.parse.quote('Vui lòng hoàn thiện hồ sơ (MSV, lớp, ngành) trước.')
            return request.redirect(f'/my/advisor?error={error}')
        Registration = request.env['eaut_showcase.advisor.registration'].sudo()
        registration = self._get_registration(term) or Registration.create({
            'term_id': term.id, 'student_id': partner.id,
        })

        raw_creator_id = (post.get('creator_id') or '').strip()
        if not raw_creator_id:
            error = urllib.parse.quote('Vui lòng chọn 1 giảng viên.')
            return request.redirect(f'/my/advisor?error={error}')

        note = (post.get('note') or '').strip()
        topic = (post.get('topic') or '').strip()

        try:
            registration.action_cart_add(int(raw_creator_id), note=note, topic=topic)
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor?error={urllib.parse.quote(str(e))}')
        except Exception as e:
            _logger.error('Lỗi khi sinh viên thêm vào hàng chờ nguyện vọng: %s', e, exc_info=True)
            error = urllib.parse.quote('Có lỗi xảy ra, vui lòng thử lại.')
            return request.redirect(f'/my/advisor?error={error}')

        return request.redirect('/my/advisor')

    @http.route(['/my/advisor/cart/<int:line_id>/remove'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_cart_remove(self, line_id, **post):
        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        if not registration:
            return request.redirect('/my/advisor?error=1')
        try:
            registration.action_cart_remove(line_id)
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor')

    @http.route(['/my/advisor/cart/<int:line_id>/move'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_cart_move(self, line_id, **post):
        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        if not registration:
            return request.redirect('/my/advisor?error=1')
        direction = (post.get('direction') or '').strip()
        try:
            registration.action_cart_move(line_id, direction)
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor?error={urllib.parse.quote(str(e))}')
        return request.redirect('/my/advisor')

    @http.route(['/my/advisor/cart/submit'], type='http', auth='user', website=True,
                methods=['POST'], csrf=True)
    def my_advisor_cart_submit(self, **post):
        term = self._get_open_term()
        registration = self._get_registration(term) if term else None
        if not registration:
            return request.redirect('/my/advisor?error=1')
        try:
            notice = registration.action_submit_cart()
        except (UserError, ValidationError) as e:
            return request.redirect(f'/my/advisor?error={urllib.parse.quote(str(e))}')
        except Exception as e:
            _logger.error('Lỗi khi sinh viên nộp hàng chờ nguyện vọng: %s', e, exc_info=True)
            error = urllib.parse.quote('Có lỗi xảy ra, vui lòng thử lại.')
            return request.redirect(f'/my/advisor?error={error}')
        if notice:
            # Chưa nộp thật (giỏ vẫn ở trạng thái sửa được, chỉ bị dọn bớt
            # giảng viên đã hết chỗ) — KHÔNG kèm submitted=1, tránh hiện nhầm
            # banner "Đã nộp thành công".
            return request.redirect(f'/my/advisor?notice={urllib.parse.quote(notice)}')
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
            # Chốt hết hạn ngay lúc GV mở trang, không đợi cron (tối đa 1 giờ
            # mới quét 1 lần) — tránh dòng đã hết hạn vẫn còn nút Duyệt/Từ
            # chối do state trong DB chưa kịp cập nhật.
            Line.sudo().search([
                ('creator_id', '=', creator.id), ('state', '=', 'pending'),
                ('deadline', '<', fields.Datetime.now()),
            ])._expire()
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
            history_terms = history_lines.mapped('term_id').sorted(
                key=lambda t: t.date_start, reverse=True)
            if (kw.get('history_term_id') or '').isdigit():
                selected_history_term_id = int(kw['history_term_id'])
                history_lines = history_lines.filtered(
                    lambda l: l.term_id.id == selected_history_term_id)
            else:
                selected_history_term_id = None
            open_terms = request.env['eaut_showcase.term'].sudo().search(
                [('state', '=', 'open')], order='date_start desc')
            for term in open_terms:
                capacities_by_term[term.id] = self._get_capacity_for_term(creator, term)
        else:
            history_terms = request.env['eaut_showcase.term']
            selected_history_term_id = None
        values = {
            'creator': creator,
            'pending_lines': pending_lines,
            'approved_lines': approved_lines,
            'history_lines': history_lines,
            'history_terms': history_terms,
            'selected_history_term_id': selected_history_term_id,
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
            return request.redirect('/my/advisor-requests?error=1&tab=capacity')
        try:
            term_id = int(post.get('term_id') or 0)
        except ValueError:
            term_id = 0
        term = request.env['eaut_showcase.term'].sudo().browse(term_id).exists()
        if not term or term.state != 'open':
            error = urllib.parse.quote('Kỳ này hiện không mở đăng ký.')
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        try:
            max_students = int(post.get('max_students') or 0)
        except ValueError:
            max_students = 0
        if max_students < 1:
            error = urllib.parse.quote('Số sinh viên tối đa phải lớn hơn 0.')
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')

        capacity = self._get_capacity_for_term(creator, term)
        if capacity and capacity.pending_action != 'none':
            error = urllib.parse.quote('Bạn đang có 1 yêu cầu chờ Admin duyệt cho kỳ này rồi.')
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        try:
            if capacity:
                # Đang 'đã rút' (withdrawn=True) — chỉ tạo yêu cầu tham gia
                # lại, chưa active ngay, chờ Admin duyệt.
                capacity.action_gv_request_join(max_students)
            else:
                request.env['eaut_showcase.term.capacity'].sudo().create_join_request(
                    term, creator, max_students)
        except (UserError, ValidationError) as e:
            error = urllib.parse.quote(str(e))
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        return request.redirect('/my/advisor-requests?done=1&tab=capacity')

    @http.route(['/my/advisor-requests/capacity/<int:capacity_id>/update'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_update(self, capacity_id, **post):
        creator = self._get_creator_for_current_user()
        capacity = request.env['eaut_showcase.term.capacity'].sudo().browse(capacity_id).exists()
        if not creator or not capacity or capacity.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1&tab=capacity')
        try:
            max_students = int(post.get('max_students') or 0)
        except ValueError:
            max_students = 0
        if max_students < 1:
            error = urllib.parse.quote('Số sinh viên tối đa phải lớn hơn 0.')
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        try:
            capacity.action_gv_request_update(max_students)
        except (UserError, ValidationError) as e:
            error = urllib.parse.quote(str(e))
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        return request.redirect('/my/advisor-requests?done=1&tab=capacity')

    @http.route(['/my/advisor-requests/capacity/<int:capacity_id>/withdraw'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_withdraw(self, capacity_id, **post):
        creator = self._get_creator_for_current_user()
        capacity = request.env['eaut_showcase.term.capacity'].sudo().browse(capacity_id).exists()
        if not creator or not capacity or capacity.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1&tab=capacity')
        try:
            capacity.action_gv_request_withdraw()
        except (UserError, ValidationError) as e:
            error = urllib.parse.quote(str(e))
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        return request.redirect('/my/advisor-requests?done=1&tab=capacity')

    @http.route(['/my/advisor-requests/capacity/<int:capacity_id>/cancel-request'], type='http', auth='user',
                website=True, methods=['POST'], csrf=True)
    def my_advisor_capacity_cancel_request(self, capacity_id, **post):
        creator = self._get_creator_for_current_user()
        capacity = request.env['eaut_showcase.term.capacity'].sudo().browse(capacity_id).exists()
        if not creator or not capacity or capacity.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1&tab=capacity')
        try:
            capacity.action_gv_cancel_request()
        except (UserError, ValidationError) as e:
            error = urllib.parse.quote(str(e))
            return request.redirect(f'/my/advisor-requests?error={error}&tab=capacity')
        return request.redirect('/my/advisor-requests?done=1&tab=capacity')

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

        try:
            category_ids = [
                int(v) for v in request.httprequest.form.getlist('category_ids') if v]
        except ValueError:
            category_ids = []
        try:
            location_id = int(post.get('location_id')) if post.get('location_id') else False
        except ValueError:
            location_id = False
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        if not name:
            error = urllib.parse.quote('Vui lòng nhập tên hiển thị.')
            return request.redirect(f'/my/advisor-requests/profile?error={error}')
        if not email or '@' not in email:
            error = urllib.parse.quote('Vui lòng nhập email liên hệ hợp lệ.')
            return request.redirect(f'/my/advisor-requests/profile?error={error}')
        vals = {
            'name': name,
            'email': email,
            'role': (post.get('role') or '').strip(),
            'bio': (post.get('bio') or '').strip(),
            'suggested_topics': (post.get('suggested_topics') or '').strip(),
            'website_url': (post.get('website_url') or '').strip(),
            'location_id': location_id,
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

    @http.route(['/my/advisor-requests/<int:line_id>'], type='http', auth='user',
                website=True, sitemap=False)
    def my_advisor_request_detail(self, line_id, **kw):
        creator = self._get_creator_for_current_user()
        line = request.env['eaut_showcase.advisor.registration.line'].sudo().browse(line_id).exists()
        if not creator or not line or line.creator_id.id != creator.id:
            return request.redirect('/my/advisor-requests?error=1')
        if line.state == 'pending' and line.deadline and line.deadline < fields.Datetime.now():
            line._expire()
        values = {
            'creator': creator,
            'line': line,
            'error': kw.get('error'),
        }
        return request.render('eaut_showcase.portal_my_advisor_request_detail', values)

    @http.route(['/my/advisor-requests/<int:line_id>/student-avatar'], type='http', auth='user',
                website=True, sitemap=False)
    def my_advisor_request_student_avatar(self, line_id, **kw):
        creator = self._get_creator_for_current_user()
        line = request.env['eaut_showcase.advisor.registration.line'].sudo().browse(line_id).exists()
        if not creator or not line or line.creator_id.id != creator.id:
            return request.not_found()
        return request.env['ir.binary']._get_image_stream_from(
            line.student_id, field_name='image_1920'
        ).get_response()

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
