# -*- coding: utf-8 -*-
from odoo import fields, models


class ShowcaseTermCloseWarning(models.TransientModel):
    _name = 'eaut_showcase.term.close.warning'
    _description = 'Popup cảnh báo khi đóng kỳ còn sinh viên chưa có GVHD'

    message = fields.Text(string='Thông báo', readonly=True)
