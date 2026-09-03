# -*- coding: utf-8 -*-
from odoo import fields, models


class ShowcaseDepartment(models.Model):
    _name = 'eaut_showcase.department'
    _description = 'Khoa quản lý giảng viên Showcase'
    _order = 'sequence, id'

    name = fields.Char(string='Tên khoa', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    creator_ids = fields.One2many(
        'eaut_showcase.creator', 'department_id', string='Giảng viên',
    )

    _name_uniq = models.Constraint('unique(name)', 'Tên khoa này đã tồn tại.')