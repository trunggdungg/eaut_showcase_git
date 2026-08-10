# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ShowcaseTerm(models.Model):
    _name = 'eaut_showcase.term'
    _description = 'Kỳ đồ án — đợt đăng ký chọn giảng viên hướng dẫn'
    _order = 'date_start desc'

    name = fields.Char(string='Tên kỳ', required=True)
    date_start = fields.Date(string='Ngày mở đăng ký', required=True)
    date_end = fields.Date(string='Ngày đóng đăng ký', required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('open', 'Đang mở'),
        ('closed', 'Đã đóng'),
    ], string='Trạng thái', default='draft', required=True)

    sla_hours = fields.Integer(
        string='Hạn phản hồi của giảng viên (giờ)', default=48,
        help="Số giờ tối đa giảng viên có để duyệt/từ chối 1 nguyện vọng trước "
             "khi hệ thống tự động chuyển sang nguyện vọng kế tiếp của sinh viên.",
    )
    max_preferences = fields.Integer(string='Số nguyện vọng tối đa/sinh viên', default=5)

    capacity_ids = fields.One2many(
        'eaut_showcase.term.capacity', 'term_id', string='Giảng viên nhận hướng dẫn',
    )
    registration_ids = fields.One2many(
        'eaut_showcase.advisor.registration', 'term_id', string='Đăng ký của sinh viên',
    )
    unassigned_count = fields.Integer(
        string='Sinh viên chưa có GVHD', compute='_compute_unassigned_count',
    )

    @api.depends('registration_ids.state')
    def _compute_unassigned_count(self):
        for term in self:
            term.unassigned_count = len(term.registration_ids.filtered(
                lambda r: r.state == 'unassigned'))

    def action_open(self):
        self.write({'state': 'open'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_close(self):
        self.ensure_one()
        unassigned = self.unassigned_count
        self.write({'state': 'closed'})
        if unassigned:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Đã đóng kỳ — vẫn còn sinh viên chưa có GVHD',
                    'message': (
                        '%s sinh viên chưa được gán giảng viên hướng dẫn. '
                        'Vào "Sinh viên chưa có GVHD" để gán tay.'
                    ) % unassigned,
                    'type': 'warning',
                    'sticky': True,
                },
            }
        return True

    def action_view_registrations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sinh viên chưa có GVHD',
            'res_model': 'eaut_showcase.advisor.registration',
            'view_mode': 'list,form',
            'domain': [('term_id', '=', self.id), ('state', '=', 'unassigned')],
        }
