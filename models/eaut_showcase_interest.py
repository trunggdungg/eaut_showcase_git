# -*- coding: utf-8 -*-
import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


class UikickInterest(models.Model):
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

    @api.constrains('email')
    def _check_email(self):
        for rec in self:
            if rec.email and not EMAIL_RE.match(rec.email):
                raise ValidationError('Email không hợp lệ: %s' % rec.email)