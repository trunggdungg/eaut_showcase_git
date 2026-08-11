# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

class ShowcaseCreator(models.Model):
    _name = 'eaut_showcase.creator'
    _description = 'Tác giả / nhóm thực hiện sản phẩm'
    _order = 'name'

    name = fields.Char(string='Tên tác giả', required=True)
    avatar = fields.Image(string='Ảnh đại diện', max_width=512, max_height=512)
    role = fields.Char(string='Vai trò', default='Tác giả sản phẩm')
    bio = fields.Text(string='Giới thiệu')
    location_id = fields.Many2one(
        'res.country.state', string='Địa điểm',
        domain="[('country_id.code', '=', 'VN')]",
    )
    email = fields.Char(string='Email liên hệ')
    website_url = fields.Char(string='Website / mạng xã hội')
    user_id = fields.Many2one(
        'res.users', string='Tài khoản Portal',
        help="Tài khoản Portal giảng viên dùng để đăng nhập và duyệt yêu cầu "
             "hướng dẫn đồ án ở trang /my/advisor-requests.",
    )
    category_ids = fields.Many2many(
        'eaut_showcase.category', string='Lĩnh vực',
        help="Dùng để lọc giảng viên theo lĩnh vực ở trang chọn giảng viên "
             "hướng dẫn đồ án — dùng chung danh mục với dự án Showcase.",
    )
    project_ids = fields.Many2many(
        'eaut_showcase.project', 'eaut_showcase_project_creator_rel',
        'creator_id', 'project_id', string='Dự án đã đăng',
    )
    project_count = fields.Integer(
        string='Số dự án đã đăng', compute='_compute_project_count', store=True,
    )

    capacity_ids = fields.One2many(
        'eaut_showcase.term.capacity', 'creator_id', string='Sức chứa theo kỳ',
    )

    kanban_term_id = fields.Many2one(
        'eaut_showcase.term', string='Kỳ đồ án',
        group_expand='_group_expand_kanban_terms',
        help="Suy ra từ sức chứa (term.capacity) thật của giảng viên — kỳ còn "
             "hiệu lực (chưa rút) có ngày mở gần nhất. Kéo-thả trên Kanban "
             "'Phân bổ giảng viên theo kỳ' sẽ tự tạo sức chứa nếu chưa có; "
             "field này luôn phản ánh đúng dữ liệu dù thêm/sửa từ đâu (Kanban "
             "hay tab 'Giảng viên nhận hướng dẫn' trong form Kỳ).",
    )

    @api.depends('project_ids')
    def _compute_project_count(self):
        for creator in self:
            creator.project_count = len(creator.project_ids)

    @api.depends('capacity_ids.term_id', 'capacity_ids.withdrawn')
    def _compute_kanban_term_id(self):
        for creator in self:
            active = creator.capacity_ids.filtered(lambda c: not c.withdrawn)
            active = active.sorted(key=lambda c: c.term_id.date_start, reverse=True)
            creator.kanban_term_id = active[:1].term_id if active else False

    def _inverse_kanban_term_id(self):
        for creator in self:
            creator._assign_to_term(creator.kanban_term_id.id)


    @api.model
    def _group_expand_kanban_terms(self, terms, domain):
        # Luôn hiện đủ các kỳ draft/open làm cột, kể cả kỳ chưa có giảng
        # viên nào — nếu không, Kanban mặc định chỉ hiện cột cho giá trị đã
        # tồn tại, không có chỗ để kéo giảng viên vào 1 kỳ mới toanh.
        return self.env['eaut_showcase.term'].search(
            [('state', 'in', ('draft', 'open'))], order='date_start desc')


    def _assign_to_term(self, term_id):
        self.ensure_one()
        if not term_id:
            # self.with_context(creator_internal_write=True).write({'kanban_term_id': False})
            return
        Capacity = self.env['eaut_showcase.term.capacity']
        existing = Capacity.search([
            ('term_id', '=', term_id), ('creator_id', '=', self.id),
        ], limit=1)
        if not existing:
            Capacity.create({'term_id': term_id, 'creator_id': self.id, 'max_students': 1})
        # self.with_context(creator_internal_write=True).write({'kanban_term_id': term_id})
        elif existing.withdrawn:
            existing.withdrawn = False
            
    def action_view_projects(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_uikick_project'
        )
        action['domain'] = [('creator_ids', 'in', self.id)]
        return action

    def action_create_portal_user(self):
        """Tạo Liên hệ (nếu chưa có) và cấp quyền truy cập Portal cho đúng
           Liên hệ đó — đi qua đúng cơ chế "Grant Portal Access" chuẩn của Odoo
           (portal.wizard) thay vì tự tạo res.users tay, để dùng đúng mẫu email
           mời + luồng bảo mật (signup token) mà Odoo tự quản lý."""
        self.ensure_one()
        if self.user_id:
            raise UserError('Tác giả này đã có tài khoản Portal (%s) rồi.' % self.user_id.login)
        if not self.email:
            raise UserError('Vui lòng nhập Email liên hệ trước khi tạo tài khoản Portal.')

        email = self.email.strip()

        # Email đã là login của 1 tài khoản khác (Portal hay Internal) chưa?
        existing_user = self.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing_user:
            raise UserError(
                'Email này đã được dùng làm tài khoản đăng nhập (%s) — vào field "Tài '
                'khoản Portal" để chọn thủ công tài khoản đó thay vì tạo mới.' % existing_user.login
            )

        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', email)], limit=1)
        # Email đã được cấp quyền Portal cho 1 liên hệ khác chưa?
        if partner and partner.user_ids:
            raise UserError(
                'Email này đã được cấp quyền Portal cho liên hệ "%s" (đăng nhập: %s) rồi — '
                'không thể cấp trùng.' % (partner.name, partner.user_ids[0].login)
            )
        if not partner:
            partner = Partner.create({
                'name': self.name,
                'email': email,
                'company_type': 'person',
            })

        wizard = self.env['portal.wizard'].sudo().with_context(
            active_model='res.partner', active_ids=partner.ids,
        ).create({})
        wizard_user = wizard.user_ids.filtered(lambda u: u.partner_id == partner)
        if not wizard_user:
            raise UserError('Không thể khởi tạo yêu cầu cấp quyền Portal cho liên hệ này.')
        wizard_user.email = email
        wizard_user.action_grant_access()

        self.user_id = partner.user_ids[:1].id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã cấp quyền Portal',
                'message': 'Email mời đăng nhập Portal đã được gửi tới %s.' % email,
                'type': 'success',
                'sticky': False,
            },
        }