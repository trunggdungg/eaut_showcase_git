# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import UserError


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

    def unlink(self):
        """creator.department_id không bắt buộc (required=False) và không
        khai ondelete, nên Odoo mặc định dùng ondelete='set null' — xoá Khoa
        sẽ ÂM THẦM gỡ Khoa khỏi mọi Giảng viên đang gán vào đó, không báo
        lỗi/cảnh báo gì. Khoa hiện được dùng cho khá nhiều tính năng (hiển
        thị mặc định trên trang công khai, wizard "Thêm giảng viên từ
        khoa", lọc theo khoa...) nên chặn xoá khi còn GV, thay vì để mất
        dữ liệu không kiểm soát được."""
        for department in self:
            if department.creator_ids:
                names = ', '.join(department.creator_ids.mapped('name'))
                raise UserError(
                    'Không thể xoá Khoa "%s" — vẫn còn %s giảng viên đang gán vào khoa này '
                    '(%s). Vui lòng đổi Khoa của các giảng viên đó sang khoa khác trước khi '
                    'xoá.' % (department.name, len(department.creator_ids), names)
                )
        return super().unlink()