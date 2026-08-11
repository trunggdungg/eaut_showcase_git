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

    @api.depends('project_ids')
    def _compute_project_count(self):
        for creator in self:
            creator.project_count = len(creator.project_ids)

    def action_view_projects(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_uikick_project'
        )
        action['domain'] = [('creator_ids', 'in', self.id)]
        return action

    def action_create_portal_user(self):
        """Tạo tài khoản Portal thẳng từ hồ sơ Tác giả — tránh phải tự tay
        tạo Contact/User riêng rồi nối lại field user_id (dễ tạo nhầm loại
        Người/Công ty, tạo dư contact, hoặc nối sai người)."""
        self.ensure_one()
        if self.user_id:
            raise UserError('Tác giả này đã có tài khoản Portal (%s) rồi.' % self.user_id.login)
        if not self.email:
            raise UserError('Vui lòng nhập Email liên hệ trước khi tạo tài khoản Portal.')

        existing_user = self.env['res.users'].sudo().search([('login', '=', self.email)], limit=1)
        if existing_user:
            raise UserError(
                'Đã có tài khoản đăng nhập dùng email này (%s). Vào field "Tài khoản '
                'Portal" để chọn thủ công tài khoản đó thay vì tạo mới.' % self.email
            )

        portal_group = self.env.ref('base.group_portal')
        user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': self.name,
            'login': self.email,
            'email': self.email,
            'groups_id': [(6, 0, [portal_group.id])],
        })
        user.sudo().action_reset_password()
        self.user_id = user.id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã tạo tài khoản Portal',
                'message': 'Email mời đặt mật khẩu đã được gửi tới %s.' % self.email,
                'type': 'success',
                'sticky': False,
            },
        }