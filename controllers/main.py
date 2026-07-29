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

SORT_OPTIONS = ["Relevance", "Most viewed", "Newest"]
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

class UikickController(http.Controller):

    @http.route(['/uikick', '/uikick/category/<string:category>'],
                type='http', auth='public', website=True, sitemap=True)
    def home(self, category=None, **kw):
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

        location = (kw.get('location') or '').strip()
        if location:
            domain.append(('location_id.name', 'ilike', location))

        sort = kw.get('sort') or 'Relevance'
        order = ORDER_BY_SORT.get(sort, 'sequence asc, id asc')
        projects = Project.search(domain, order=order)

        if not selected_categories:
            header_label = 'All Projects'
        elif len(selected_categories) == 1:
            header_label = selected_categories[0]
        else:
            header_label = str(len(selected_categories)) + ' Categories'

        values = {
            'categories': all_categories,
            'all_statuses': all_statuses,
            'header_label': header_label,
            'projects': projects,
            'sort_options': SORT_OPTIONS,
            'filters': {
                'categories': selected_categories,
                'status': statuses,
                'location': location,
                'sort': sort,
            },
        }
        return request.render('eaut_showcase.home_page', values)

    @http.route(['/uikick/project/<string:project_id>'],
                type='http', auth='public', website=True, sitemap=False)
    def detail(self, project_id, submitted=None, error=None, **kw):
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

        values = {
            'project': project,
            'tabs': TABS,
            'tab_labels': TAB_LABELS,
            'community_members': community_members,
            'submitted': submitted,
            'error': error,
        }
        return request.render('eaut_showcase.detail_page', values)

    @http.route(['/uikick/project/<string:project_id>/thumbnail'],
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

    @http.route(['/uikick/creator/<int:creator_id>/avatar'],
                type='http', auth='public', website=True, sitemap=False)
    def creator_avatar(self, creator_id, **kw):
        creator = request.env['eaut_showcase.creator'].sudo().browse(creator_id).exists()
        if not creator:
            return request.not_found()
        return request.env['ir.binary']._get_image_stream_from(
            creator, field_name='avatar'
        ).get_response()

    @http.route(['/uikick/creator/<int:creator_id>'],
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
    @http.route(['/uikick/project/<string:project_id>/interest'],
                type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def submit_interest(self, project_id, **post_data):
        project = request.env['eaut_showcase.project'].sudo().search(
            [('project_code', '=', project_id)], limit=1)

        if not project:
            return request.redirect('/uikick')

        name = (post_data.get('lead_name') or '').strip()
        email = (post_data.get('lead_email') or '').strip()
        phone = (post_data.get('lead_phone') or '').strip()
        message = (post_data.get('lead_note') or '').strip()
        public_display = bool(post_data.get('public_display'))

        if not name or not email:
            error = urllib.parse.quote('Vui lòng nhập đầy đủ Họ tên và Email.')
            return request.redirect(f'/uikick/project/{project_id}?error={error}')

        try:
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
            return request.redirect(f'/uikick/project/{project_id}?error={error}')

        return request.redirect(f'/uikick/project/{project_id}?submitted=1')
