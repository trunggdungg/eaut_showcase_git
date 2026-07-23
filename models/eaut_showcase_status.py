# -*- coding: utf-8 -*-
from odoo import models, fields


class UikickStatus(models.Model):
    _name = 'eaut_showcase.status'
    _description = 'Trạng thái bài đăng Showcase'
    _order = 'sequence, id'

    name = fields.Char(string='Tên trạng thái', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    color = fields.Integer(string='Màu')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên trạng thái này đã tồn tại.'),
    ]