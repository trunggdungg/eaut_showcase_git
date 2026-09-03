# -*- coding: utf-8 -*-
from odoo import fields, models


class ShowcaseDepartmentAddCreatorWizard(models.TransientModel):
    """Popup 'Thêm giảng viên có sẵn' trên form Khoa — gán department_id cho
    những giảng viên (Tác giả) ĐÃ TỒN TẠI vào khoa đang xem. Dùng widget
    Many2many (không phải One2many như creator_ids hiển thị trên form Khoa)
    vì "Thêm 1 dòng" của Many2many mở popup chọn từ các bản ghi có sẵn,
    trong khi One2many sẽ tạo nhầm 1 Tác giả mới — tách riêng thao tác này
    ra khỏi danh sách hiển thị (creator_ids) để tránh nhầm lẫn/xoá nhầm."""
    _name = 'eaut_showcase.department.add_creator.wizard'
    _description = 'Thêm giảng viên có sẵn vào khoa'

    department_id = fields.Many2one('eaut_showcase.department', string='Khoa', required=True)
    creator_ids = fields.Many2many(
        'eaut_showcase.creator', 'eaut_showcase_dept_add_creator_wiz_rel',
        'wizard_id', 'creator_id', string='Giảng viên',
    )

    def action_add(self):
        self.ensure_one()
        if self.creator_ids:
            self.creator_ids.write({'department_id': self.department_id.id})
        return {'type': 'ir.actions.act_window_close'}
