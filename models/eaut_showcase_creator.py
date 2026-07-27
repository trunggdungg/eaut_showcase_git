# -*- coding: utf-8 -*-
from odoo import api, fields, models


class UikickCreator(models.Model):
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
