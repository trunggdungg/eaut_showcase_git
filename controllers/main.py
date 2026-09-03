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

ADVISOR_SORT_OPTIONS = ["Relevance", "Most slots", "Newest"]

ADVISOR_SORT_LABELS = {
    "Relevance": "Liên quan",
    "Most slots": "Còn nhiều chỗ nhất",
    "Newest": "Mới thêm gần đây",
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
    def home(self, category=None,   **kw):
        section = kw.get('section') if kw.get('section') in ('projects', 'advisors') else 'projects'
        if section == 'advisors':
            return self._render_advisors_section(category, kw)
        return self._render_projects_section(category, kw)

    def _get_selected_categories(self, category, all_categories, kw):
        category_names = all_categories.mapped('name')

        query_categories = [c for c in request.httprequest.args.getlist('category') if c in category_names]
        categories_submitted = 'categories_submitted' in request.httprequest.args

        if categories_submitted:
            # the sidebar's checkbox form was submitted — trust it as-is,
            # including an empty selection meaning "show every category"
            return query_categories
        if category and category in category_names:
            return [category]
        return []

    def _render_projects_section(self, category, kw):
        Project = request.env['eaut_showcase.project'].sudo()

        all_categories = request.env['eaut_showcase.category'].sudo().search([], order='sequence, id')
        selected_categories = self._get_selected_categories(category, all_categories, kw)

        domain = [('category_id.name', 'in', selected_categories)] if selected_categories else []
        if domain and not Project.search_count(domain):
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

        page = int(kw.get('page') or 1)
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
            'section': 'projects',
            'categories': all_categories,
            'all_statuses': all_statuses,
            'all_locations': all_locations,
            'header_label': header_label,
            'projects': projects,
            'items_count': total,
            'items_label': 'dự án',
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

    def _render_advisors_section(self, category, kw):
        all_categories = request.env['eaut_showcase.category'].sudo().search([], order='sequence, id')
        selected_categories = self._get_selected_categories(category, all_categories, kw)

        slot_filters = [s for s in request.httprequest.args.getlist('status') if s in ('open', 'full')]

        sort = kw.get('sort') if kw.get('sort') in ADVISOR_SORT_OPTIONS else 'Relevance'

        open_terms = request.env['eaut_showcase.term'].sudo().search(
            [('state', 'in', ('open', 'locked'))], order='date_start desc')
        selected_term_ids = [int(t) for t in request.httprequest.args.getlist('term') if t.isdigit()]
        selected_term_ids = [t for t in selected_term_ids if t in open_terms.ids]
        wanted_term_ids = selected_term_ids or open_terms.ids

        all_departments = request.env['eaut_showcase.department'].sudo().search([], order='sequence, id')
        selected_department_ids = [
            int(d) for d in request.httprequest.args.getlist('department') if d.isdigit()]

        capacities = request.env['eaut_showcase.term.capacity'].sudo().search([
            ('term_id', 'in', wanted_term_ids), ('withdrawn', '=', False),
        ])

        if selected_categories:
            wanted = set(selected_categories)
            capacities = capacities.filtered(
                lambda c: set(c.creator_id.category_ids.mapped('name')) & wanted)

        if selected_department_ids:
            capacities = capacities.filtered(
                lambda c: c.creator_id.department_id.id in selected_department_ids)

        if slot_filters:
            want_open = 'open' in slot_filters
            want_full = 'full' in slot_filters
            capacities = capacities.filtered(
                lambda c: (want_open and c.remaining_slots > 0) or (want_full and c.remaining_slots <= 0))

        if sort == 'Most slots':
            capacities = capacities.sorted(key=lambda c: c.remaining_slots, reverse=True)
        elif sort == 'Newest':
            capacities = capacities.sorted(key=lambda c: c.creator_id.id, reverse=True)

        # Một giảng viên có thể có nhiều capacity (1 bản ghi / kỳ) nếu đang
        # active ở nhiều kỳ đồ án cùng lúc; trang công khai chỉ hiển thị mỗi
        # giảng viên 1 lần nên khử trùng theo creator_id, giữ bản ghi đầu
        # tiên theo thứ tự đã sort ở trên.
        seen_creator_ids = set()
        deduped_capacities = request.env['eaut_showcase.term.capacity']
        for capacity in capacities:
            if capacity.creator_id.id in seen_creator_ids:
                continue
            seen_creator_ids.add(capacity.creator_id.id)
            deduped_capacities |= capacity
        capacities = deduped_capacities

        items = [{'creator': c.creator_id, 'capacity': c} for c in capacities]

        # Khi SV lọc theo khoa, hiện luôn cả GV thuộc khoa đó nhưng CHƯA có
        # sức chứa ở kỳ nào đang mở (VD: khoa vừa mở kỳ mới, chưa kịp thêm
        # hết GV) — thẻ của họ không có nút "Chọn làm GVHD" (xem
        # advisor_card), chỉ để SV biết GV này thuộc khoa nhưng chưa nhận
        # đăng ký. Bộ lọc "Còn nhận"/"Đã đầy" không áp dụng được cho nhóm
        # này (không có sức chứa nào để so sánh) nên chỉ thêm khi SV không
        # chọn bộ lọc trạng thái nhận SV.
        if selected_department_ids and not slot_filters:
            no_capacity_creators = request.env['eaut_showcase.creator'].sudo().search([
                ('department_id', 'in', selected_department_ids),
                ('id', 'not in', list(seen_creator_ids)),
            ], order='name')
            if selected_categories:
                wanted = set(selected_categories)
                no_capacity_creators = no_capacity_creators.filtered(
                    lambda c: set(c.category_ids.mapped('name')) & wanted)
            items += [{'creator': c, 'capacity': False} for c in no_capacity_creators]

        url_args = {'categories_submitted': 1, 'sort': sort, 'section': 'advisors'}
        if selected_categories:
            url_args['category'] = selected_categories
        if slot_filters:
            url_args['status'] = slot_filters

        if selected_term_ids:
            url_args['term'] = selected_term_ids
        if selected_department_ids:
            url_args['department'] = selected_department_ids

        page = int(kw.get('page') or 1)
        total = len(items)
        pager = request.website.pager(
            url='/showcase', total=total, page=page, step=PAGE_SIZE, scope=7, url_args=url_args,
        )
        capacities_page = items[pager['offset']:pager['offset'] + PAGE_SIZE]

        if not selected_categories:
            header_label = 'Tất cả giảng viên'
        elif len(selected_categories) == 1:
            header_label = selected_categories[0]
        else:
            header_label = str(len(selected_categories)) + ' lĩnh vực'

        values = {
            'section': 'advisors',
            'open_terms': open_terms,
            'categories': all_categories,
            'departments': all_departments,

            'header_label': header_label,
            'capacities': capacities_page,
            'items_count': total,
            'items_label': 'giảng viên',
            'pager': pager,
            'sort_options': ADVISOR_SORT_OPTIONS,
            'sort_labels': ADVISOR_SORT_LABELS,
            'filters': {
                'categories': selected_categories,
                'status': slot_filters,

                'sort': sort,
                'term': selected_term_ids,
                'department': selected_department_ids,
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
        advisor_capacity = creator.get_open_capacity_for_partner(request.env.user.partner_id)

        # Đề tài đã hướng dẫn — chỉ lấy tên đề tài, KHÔNG kèm tên sinh viên
        # (trang này công khai, không đăng nhập cũng xem được).
        supervised_lines = request.env['eaut_showcase.advisor.registration.line'].sudo().search([
            ('creator_id', '=', creator.id), ('state', '=', 'approved'),
            ('proposed_topic', '!=', False),
        ])
        supervised_topics = sorted(set(supervised_lines.mapped('proposed_topic')) - {''})

        values = {
            'creator': creator,
            'projects': creator.project_ids,
            'advisor_capacity': advisor_capacity,
            'supervised_topics': supervised_topics,
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
        # try:
        #     request.env['eaut.career.center.employer'].sudo().create({
        #         'name': name,
        #         'email': email,
        #         'phone': phone,
        #         'note': message,
        #         # 'source_project_id': project.id,
        #     })
        # except Exception as e:
        #     _logger.error('Error pushing interest to eaut.career.center.employer: %s', str(e), exc_info=True)

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