# -*- coding: utf-8 -*-
from odoo import models, fields


class UikickCategory(models.Model):
    _name = 'eaut_showcase.category'
    _description = 'Danh mục dự án Showcase'
    _order = 'sequence, id'

    name = fields.Char(string='Tên danh mục', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    color = fields.Integer(string='Màu')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên danh mục này đã tồn tại.'),
    ]