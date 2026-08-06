# -*- coding: utf-8 -*-
import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


class ShowcaseInterest(models.Model):
    _name = 'eaut_showcase.interest'
    _description = 'Người quan tâm đến dự án Showcase'
    _order = 'create_date desc'
    _rec_name = 'name'

    project_id = fields.Many2one(
        'eaut_showcase.project', string='Dự án',
        required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(string='Họ tên', required=True)
    email = fields.Char(string='Email', required=True)
    phone = fields.Char(string='Số điện thoại')
    message = fields.Text(string='Lời nhắn')

    state = fields.Selection([
        ('new', 'Mới'),
        ('contacted', 'Đã liên hệ'),
        ('closed', 'Đã đóng'),
    ], string='Trạng thái', default='new')

    public_display = fields.Boolean(
        string='Đồng ý hiển thị công khai', default=False,
        help="Người quan tâm tự tick khi gửi form — nếu bật, tên sẽ hiện công "
             "khai ở tab Cộng đồng trên trang chi tiết dự án.",
    )

    email_interest_count = fields.Integer(
        string='Số lần gửi form', compute='_compute_email_interest_count',
    )

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and not EMAIL_RE.match(rec.email):
                raise ValidationError('Email không hợp lệ: %s' % rec.email)

    def _compute_email_interest_count(self):
        for rec in self:
            rec.email_interest_count = (
                self.search_count([('email', '=', rec.email)]) if rec.email else 0
            )

    def action_view_interests_by_email(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Các lần quan tâm khác (theo email)',
            'res_model': 'eaut_showcase.interest',
            'view_mode': 'list,form',
            'domain': [('email', '=', self.email)],
        }