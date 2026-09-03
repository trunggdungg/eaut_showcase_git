# -*- coding: utf-8 -*-
from odoo import fields, models


class ShowcaseTermAddDepartmentWizard(models.TransientModel):
    """Popup 'Thêm giảng viên từ khoa' trên form Kỳ đồ án — thêm hàng loạt
    toàn bộ giảng viên của 1 khoa vào kỳ đang mở, dùng 'Sức chứa mặc định'
    (eaut_showcase.creator.default_max_students) của từng giảng viên làm
    giá trị khởi tạo cho dòng term.capacity mới, thay vì Admin phải thêm
    tay từng dòng + gõ lại số sinh viên tối đa mỗi lần mở kỳ mới. Không
    thay đổi gì logic sức chứa hiện có — chỉ là 1 cách tạo hàng loạt các
    dòng term.capacity bình thường, sửa/rút/duyệt sau đó vẫn y như thêm
    tay."""
    _name = 'eaut_showcase.term.add_department.wizard'
    _description = 'Thêm giảng viên từ khoa vào kỳ đồ án'

    term_id = fields.Many2one('eaut_showcase.term', string='Kỳ đồ án', required=True)
    department_id = fields.Many2one(
        'eaut_showcase.department', string='Khoa', required=True,
    )

    def action_add(self):
        self.ensure_one()
        Capacity = self.env['eaut_showcase.term.capacity']
        existing_creator_ids = set(self.term_id.capacity_ids.creator_id.ids)
        creators = self.department_id.creator_ids.filtered(
            lambda c: c.id not in existing_creator_ids)

        for creator in creators:
            Capacity.create({
                'term_id': self.term_id.id,
                'creator_id': creator.id,
                'max_students': creator.default_max_students or 1,
            })

        skipped = len(self.department_id.creator_ids) - len(creators)
        message = 'Đã thêm %s giảng viên từ khoa "%s" vào kỳ.' % (
            len(creators), self.department_id.name)
        if skipped:
            message += ' Bỏ qua %s giảng viên đã có sẵn trong kỳ này.' % skipped

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thêm giảng viên từ khoa',
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
