# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

import logging
import urllib.parse
import werkzeug
from datetime import datetime
_logger = logging.getLogger(__name__)
# Internal ids used for data-tab matching/JS — the visible label is translated
# separately via TAB_LABELS so the tab-switching logic doesn't have to compare
# against Vietnamese strings.
TABS = ["Campaign", "FAQ", "Comments", "Community"]
TAB_LABELS = {
    "Campaign": "Giới thiệu",
    "FAQ": "FAQ",
    "Comments": "Bình luận",
    "Community": "Cộng đồng",
}

PAGE_SIZE = 12

SORT_OPTIONS = ["Relevance", "Most viewed", "Newest"]

SORT_LABELS = {
    "Relevance": "Liên quan",
    "Most viewed": "Xem nhiều nhất",
    "Newest": "Mới nhất",
}
ORDER_BY_SORT = {
    "Most viewed": "views desc",
    "Newest": "create_date desc",
}




def _relative_time_vi(dt):
    """Định dạng thời gian dạng "x ngày trước" cho tab Cộng đồng."""
    if not dt:
        return ''
    seconds = (datetime.now() - dt).total_seconds()
    if seconds < 60:
        return 'Vừa xong'
    minutes = int(seconds // 60)
    if minutes < 60:
        return '%d phút trước' % minutes
    hours = int(minutes // 60)
    if hours < 24:
        return '%d giờ trước' % hours
    days = int(hours // 24)
    if days < 30:
        return '%d ngày trước' % days
    months = int(days // 30)
    if months < 12:
        return '%d tháng trước' % months
    return '%d năm trước' % int(months // 12)

class ShowcaseController(http.Controller):

    @http.route(['/showcase', '/showcase/page/<int:page>', '/showcase/category/<string:category>'],
                type='http', auth='public', website=True, sitemap=True)
    def home(self, category=None, page=1,  **kw):
        Project = request.env['eaut_showcase.project'].sudo()

        all_categories = request.env['eaut_showcase.category'].sudo().search([], order='sequence, id')
        category_names = all_categories.mapped('name')

        query_categories = [c for c in request.httprequest.args.getlist('category') if c in category_names]
        categories_submitted = 'categories_submitted' in request.httprequest.args

        if categories_submitted:
            # the sidebar's checkbox form was submitted — trust it as-is,
            # including an empty selection meaning "show every category"
            selected_categories = query_categories
        elif category and category in category_names:
            selected_categories = [category]
        else:
            selected_categories = []

        domain = [('category_id.name', 'in', selected_categories)] if selected_categories else []
        if domain and not Project.search_count(domain):
            # none of the selected categories have any projects – show everything instead
            domain = []

        all_statuses = request.env['eaut_showcase.status'].sudo().search([], order='sequence, id')
        status_names = all_statuses.mapped('name')
        statuses = [s for s in request.httprequest.args.getlist('status') if s in status_names]
        if statuses:
            domain.append(('status_id.name', 'in', statuses))

        all_locations = Project.search([]).mapped('location_id').sorted(key=lambda l: l.name)

        location = (kw.get('location') or '').strip()
        if location:
            domain.append(('location_id.name', 'ilike', location))

        sort = kw.get('sort') or 'Relevance'
        order = ORDER_BY_SORT.get(sort, 'sequence asc, id asc')

        url_args = {'categories_submitted': 1, 'sort': sort}
        if selected_categories:
            url_args['category'] = selected_categories
        if statuses:
            url_args['status'] = statuses
        if location:
            url_args['location'] = location

        page = page or 1
        total = Project.search_count(domain)
        pager = request.website.pager(
            url='/showcase', total=total, page=page, step=PAGE_SIZE, scope=7, url_args=url_args,
        )
        projects = Project.search(domain, order=order, limit=PAGE_SIZE, offset=pager['offset'])

        if not selected_categories:
            header_label = 'Tất cả dự án'
        elif len(selected_categories) == 1:
            header_label = selected_categories[0]
        else:
            header_label = str(len(selected_categories)) + ' Categories'

        values = {
            'categories': all_categories,
            'all_statuses': all_statuses,
            'all_locations': all_locations,
            'header_label': header_label,
            'projects': projects,
            'projects_count': total,
            'pager': pager,
            'sort_options': SORT_OPTIONS,
            'sort_labels': SORT_LABELS,
            'filters': {
                'categories': selected_categories,
                'status': statuses,
                'location': location,
                'sort': sort,
            },
        }
        return request.render('eaut_showcase.home_page', values)

    @http.route(['/showcase/project/<string:project_id>'],
                type='http', auth='public', website=True, sitemap=False)
    def detail(self, project_id, submitted=None, error=None,already_interested=None, **kw):
        Project = request.env['eaut_showcase.project'].sudo()
        project = Project.search([('project_code', '=', project_id)], limit=1)
        if not project:
            project = Project.search([('project_code', '=', '5')], limit=1) or Project.search([], limit=1)

        if project:
            project.views += 1
        # reward_tiers = request.env['eaut_showcase.reward.tier'].sudo().search([], order='sequence, id')

            # Chỉ những người đã tick "Đồng ý hiển thị công khai" khi gửi form Quan
            # tâm mới xuất hiện ở tab Cộng đồng — tránh lộ tên khi họ chưa đồng ý.
        community_members = [
            {'name': interest.name, 'time_ago': _relative_time_vi(interest.create_date)}
            for interest in project.interest_ids.filtered('public_display').sorted(
                    key=lambda i: i.create_date, reverse=True
            )
        ] if project else []

        anonymous_interest_count = (project.interest_count - len(community_members)) if project else 0
        # Chỉ hiện bình luận đã được admin duyệt — comment_ids đã sắp mới nhất
        # lên đầu theo _order của model.
        approved_comments = [
            {'name': c.name, 'content': c.content, 'time_ago': _relative_time_vi(c.create_date)}
            for c in project.comment_ids.filtered(lambda c: c.state == 'approved')
        ] if project else []

        values = {
            'project': project,
            'tabs': TABS,
            'tab_labels': TAB_LABELS,
            'community_members': community_members,
            'anonymous_interest_count': anonymous_interest_count,
            'approved_comments': approved_comments,
            'submitted': submitted,
            'error': error,
            'already_interested': already_interested,
            'comment_submitted': kw.get('comment_submitted'),
            'comment_error': kw.get('comment_error'),
        }
        return request.render('eaut_showcase.detail_page', values)

    @http.route(['/showcase/project/<string:project_id>/thumbnail'],
                type='http', auth='public', website=True, sitemap=False)
    def project_thumbnail(self, project_id, **kw):
        project = request.env['eaut_showcase.project'].sudo().search(
            [('project_code', '=', project_id)], limit=1)
        if not project:
            return request.not_found()
        if not project.image and project.video_thumbnail_url:
            return werkzeug.utils.redirect(project.video_thumbnail_url, code=302)

        return request.env['ir.binary']._get_image_stream_from(
            project, field_name='image'
        ).get_response()

    @http.route(['/showcase/creator/<int:creator_id>/avatar'],
                type='http', auth='public', website=True, sitemap=False)
    def creator_avatar(self, creator_id, **kw):
        creator = request.env['eaut_showcase.creator'].sudo().browse(creator_id).exists()
        if not creator:
            return request.not_found()
        return request.env['ir.binary']._get_image_stream_from(
            creator, field_name='avatar'
        ).get_response()

    @http.route(['/showcase/creator/<int:creator_id>'],
                type='http', auth='public', website=True, sitemap=True)
    def creator_detail(self, creator_id, **kw):
        creator = request.env['eaut_showcase.creator'].sudo().browse(creator_id).exists()
        if not creator:
            return request.not_found()
        values = {
            'creator': creator,
            'projects': creator.project_ids,
        }
        return request.render('eaut_showcase.creator_detail_page', values)

    # ============ SUBMIT FORM "QUAN TÂM" ============
    @http.route(['/showcase/project/<string:project_id>/interest'],
                type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def submit_interest(self, project_id, **post_data):
        project = request.env['eaut_showcase.project'].sudo().search(
            [('project_code', '=', project_id)], limit=1)

        if not project:
            return request.redirect('/showcase')

        name = (post_data.get('lead_name') or '').strip()
        email = (post_data.get('lead_email') or '').strip()
        phone = (post_data.get('lead_phone') or '').strip()
        message = (post_data.get('lead_note') or '').strip()
        public_display = bool(post_data.get('public_display'))

        if not name or not email:
            error = urllib.parse.quote('Vui lòng nhập đầy đủ Họ tên và Email.')
            return request.redirect(f'/showcase/project/{project_id}?error={error}')

        try:

            existing = request.env['eaut_showcase.interest'].sudo().search([
                ('project_id', '=', project.id),
                ('email', '=', email),
            ], limit=1)

            if existing:
                existing.write({
                    'name': name,
                    'phone': phone,
                    'message': message,
                    'public_display': public_display,
                })
                _logger.info('Updated existing interest for project %s: %s <%s>', project.id, name, email)
                return request.redirect(f'/showcase/project/{project_id}?submitted=1&already_interested=1')

            request.env['eaut_showcase.interest'].sudo().create({
                'project_id': project.id,
                'name': name,
                'email': email,
                'phone': phone,
                'message': message,
                'public_display': public_display,
            })
            _logger.info('New interest for project %s: %s <%s>', project.id, name, email)
        except Exception as e:
            _logger.error('Error creating eaut_showcase.interest: %s', str(e), exc_info=True)
            error = urllib.parse.quote('Có lỗi xảy ra, vui lòng thử lại.')
            return request.redirect(f'/showcase/project/{project_id}?error={error}')

        # Đẩy dữ liệu sang app custom — lỗi ở đây KHÔNG được làm hỏng luồng chính
        try:
            request.env['eaut.career.center.employer'].sudo().create({
                'name': name,
                'email': email,
                'phone': phone,
                'note': message,
                # 'source_project_id': project.id,
            })
        except Exception as e:
            _logger.error('Error pushing interest to eaut.career.center.employer: %s', str(e), exc_info=True)

        return request.redirect(f'/showcase/project/{project_id}?submitted=1')

# ============ SUBMIT FORM "BÌNH LUẬN" ============
    @http.route(['/showcase/project/<string:project_id>/comment'],
                type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def submit_comment(self, project_id, **post_data):
        project = request.env['eaut_showcase.project'].sudo().search(
            [('project_code', '=', project_id)], limit=1)

        if not project:
            return request.redirect('/showcase')

        name = (post_data.get('comment_name') or '').strip()
        content = (post_data.get('comment_content') or '').strip()

        if not name or not content:
            error = urllib.parse.quote('Vui lòng nhập đầy đủ tên và nội dung bình luận.')
            return request.redirect(f'/showcase/project/{project_id}?comment_error={error}')

        try:
            request.env['eaut_showcase.comment'].sudo().create({
                'project_id': project.id,
                'name': name,
                'content': content,
            })
            _logger.info('New comment for project %s from %s', project.id, name)
        except Exception as e:
            _logger.error('Error creating eaut_showcase.comment: %s', str(e), exc_info=True)
            error = urllib.parse.quote('Có lỗi xảy ra, vui lòng thử lại.')
            return request.redirect(f'/showcase/project/{project_id}?comment_error={error}')

        return request.redirect(f'/showcase/project/{project_id}?comment_submitted=1')