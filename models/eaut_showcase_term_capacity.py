# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ShowcaseTermCapacity(models.Model):
    _name = 'eaut_showcase.term.capacity'
    _description = 'Sức chứa nhận hướng dẫn của giảng viên theo từng kỳ'
    _order = 'term_id, creator_id'
    _rec_name = 'creator_id'

    term_id = fields.Many2one(
        'eaut_showcase.term', string='Kỳ đồ án', required=True, ondelete='cascade',
    )
    creator_id = fields.Many2one(
        'eaut_showcase.creator', string='Giảng viên', required=True,
    )
    max_students = fields.Integer(string='Số sinh viên tối đa', default=1, required=True)
    withdrawn = fields.Boolean(string='Đã rút khỏi kỳ')

    approved_count = fields.Integer(string='Đã duyệt', compute='_compute_counts')
    pending_count = fields.Integer(string='Đang chờ duyệt', compute='_compute_counts')
    remaining_slots = fields.Integer(string='Còn trống', compute='_compute_counts')

    _sql_constraints = [
        ('term_creator_uniq', 'unique(term_id, creator_id)',
         'Giảng viên này đã có khai báo sức chứa trong kỳ này rồi.'),
    ]

    # Đếm chéo model advisor.registration.line — không có field liên kết trực
    # tiếp để dùng @api.depends chuẩn, nên chỉ khai depends trên field của
    # chính record này; giá trị luôn được tính lại mới mỗi lần đọc record
    # (mỗi request là 1 env/cache mới) nên vẫn đảm bảo đúng trong thực tế dùng.
    @api.depends('term_id', 'creator_id')
    def _compute_counts(self):
        Line = self.env['eaut_showcase.advisor.registration.line']
        for capacity in self:
            approved = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', '=', 'approved'),
            ])
            pending = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', '=', 'pending'),
            ])
            capacity.approved_count = approved
            capacity.pending_count = pending
            capacity.remaining_slots = capacity.max_students - approved - pending

    def unlink(self):
        Line = self.env['eaut_showcase.advisor.registration.line']
        for capacity in self:
            count = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', 'in', ('approved', 'pending')),
            ])
            if count:
                raise UserError(
                    'Không thể xoá — giảng viên "%s" đang có %s sinh viên đã duyệt/đang '
                    'chờ trong kỳ "%s". Dùng nút "Rút khỏi kỳ" để xử lý đúng quy trình '
                    '(sinh viên sẽ được reset để chọn lại) thay vì xoá trực tiếp, tránh '
                    'mất dấu vết dữ liệu.' % (capacity.creator_id.name, count, capacity.term_id.name)
                )
        return super().unlink()

    def action_withdraw(self):
        self.ensure_one()
        if self.term_id.state != 'open':
            raise UserError('Chỉ có thể rút khỏi kỳ trong lúc kỳ còn đang mở đăng ký.')
        self.withdrawn = True
        affected_lines = self.env['eaut_showcase.advisor.registration.line'].search([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
            ('state', 'in', ['pending', 'approved']),
        ])
        affected_lines.registration_id.action_reset_for_withdrawal()
