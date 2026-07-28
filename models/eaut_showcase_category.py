# -*- coding: utf-8 -*-
from odoo import api, models, fields

# Bảng mã màu tương ứng với chỉ số của widget color_picker chuẩn của Odoo
# (0 = không chọn màu). Dùng để website (không load được CSS màu tag của
# backend Odoo) vẫn hiển thị đúng màu admin đã chọn.
COLOR_INDEX_TO_HEX = {
    1: '#F06050', 2: '#F4A460', 3: '#F7CD1F', 4: '#6CC1ED',
    5: '#814968', 6: '#EB7E7F', 7: '#2C8397', 8: '#475577',
    9: '#D6145F', 10: '#30C381', 11: '#9365B8',
}

class UikickCategory(models.Model):
    _name = 'eaut_showcase.category'
    _description = 'Danh mục dự án Showcase'
    _order = 'sequence, id'

    name = fields.Char(string='Tên danh mục', required=True)
    sequence = fields.Integer(string='Thứ tự', default=10)
    color = fields.Integer(string='Màu')
    color_hex = fields.Char(
        string='Mã màu (hex)', compute='_compute_color_hex',
        help="Mã màu hex tương ứng với Màu đã chọn, dùng để tô nền badge danh "
             "mục trên trang web. Trống nếu chưa chọn màu (color = 0).",
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên danh mục này đã tồn tại.'),
    ]

    @api.depends('color')
    def _compute_color_hex(self):
        for category in self:
            category.color_hex = COLOR_INDEX_TO_HEX.get(category.color)