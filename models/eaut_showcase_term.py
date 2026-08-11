# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ShowcaseTerm(models.Model):
    _name = 'eaut_showcase.term'
    _description = 'Kỳ đồ án — đợt đăng ký chọn giảng viên hướng dẫn'
    _order = 'date_start desc'

    name = fields.Char(string='Tên kỳ', required=True)
    date_start = fields.Date(string='Ngày mở đăng ký', required=True)
    date_end = fields.Date(string='Ngày đóng đăng ký', required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('open', 'Đang mở'),
        ('closed', 'Đã đóng'),
    ], string='Trạng thái', default='draft', required=True)

    sla_hours = fields.Integer(
        string='Hạn phản hồi của giảng viên (giờ)', default=48,
        help="Số giờ tối đa giảng viên có để duyệt/từ chối 1 nguyện vọng trước "
             "khi hệ thống tự động chuyển sang nguyện vọng kế tiếp của sinh viên.",
    )
    max_preferences = fields.Integer(string='Số nguyện vọng tối đa/sinh viên', default=5)

    capacity_ids = fields.One2many(
        'eaut_showcase.term.capacity', 'term_id', string='Giảng viên nhận hướng dẫn',
    )
    registration_ids = fields.One2many(
        'eaut_showcase.advisor.registration', 'term_id', string='Đăng ký của sinh viên',
    )
    unassigned_count = fields.Integer(
        string='Sinh viên chưa có GVHD', compute='_compute_unassigned_count',
    )
    eligible_student_ids = fields.Many2many(
        'res.partner', 'eaut_showcase_term_eligible_student_rel',
        'term_id', 'partner_id', string='Sinh viên đủ điều kiện',
        help="Chỉ sinh viên trong danh sách này mới thấy và đăng ký được ở "
             "kỳ này — dùng khi nhiều khoa mở kỳ song song, tránh sinh viên "
             "khoa khác lỡ đăng ký nhầm kỳ. Để trống = không giới hạn, mọi "
             "sinh viên Portal đều thấy được kỳ này.",
    )
    eligible_student_count = fields.Integer(
        string='Số sinh viên đủ điều kiện', compute='_compute_eligible_student_count',
    )

    @api.depends('registration_ids.state')
    def _compute_unassigned_count(self):
        for term in self:
            term.unassigned_count = len(term.registration_ids.filtered(
                lambda r: r.state == 'unassigned'))

    @api.depends('eligible_student_ids')
    def _compute_eligible_student_count(self):
        for term in self:
            term.eligible_student_count = len(term.eligible_student_ids)

    @api.model_create_multi
    def create(self, vals_list):
        terms = super().create(vals_list)
        terms._sync_eligible_student_registrations()
        return terms

    def write(self, vals):
        result = super().write(vals)
        if 'eligible_student_ids' in vals:
            self._sync_eligible_student_registrations()
        return result

    def _sync_eligible_student_registrations(self):
        """Thêm 1 SV vào 'Sinh viên đủ điều kiện' → tạo ngay 1 hồ sơ đăng ký
        ở trạng thái "Chưa có GVHD" cho họ (nếu chưa có) — để họ được tính
        vào số đếm và xuất hiện sẵn trên Kanban phân bổ, kể cả khi họ chưa
        từng tự đăng nhập nộp nguyện vọng. Nếu sau đó SV tự nộp thật, hệ
        thống dùng lại đúng bản ghi này (action_submit chỉ yêu cầu line_ids
        rỗng, không quan tâm state ban đầu)."""
        Registration = self.env['eaut_showcase.advisor.registration']
        for term in self:
            existing_student_ids = set(
                Registration.search([('term_id', '=', term.id)]).student_id.ids
            )
            missing = term.eligible_student_ids.filtered(
                lambda p: p.id not in existing_student_ids)
            for partner in missing:
                Registration.create({
                    'term_id': term.id,
                    'student_id': partner.id,
                    'state': 'unassigned',
                })

    def action_open(self):
        self.write({'state': 'open'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_close(self):
        self.ensure_one()
        unassigned = self.unassigned_count
        self.write({'state': 'closed'})
        if unassigned:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Đã đóng kỳ — vẫn còn sinh viên chưa có GVHD',
                    'message': (
                        '%s sinh viên chưa được gán giảng viên hướng dẫn. '
                        'Vào "Sinh viên chưa có GVHD" để gán tay.'
                    ) % unassigned,
                    'type': 'warning',
                    'sticky': True,
                },
            }
        return True

    def action_view_registrations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sinh viên chưa có GVHD',
            'res_model': 'eaut_showcase.advisor.registration',
            'view_mode': 'list,form',
            'domain': [('term_id', '=', self.id), ('state', '=', 'unassigned')],
        }

    def action_view_eligible_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sinh viên đủ điều kiện',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.eligible_student_ids.ids)],
        }

    def action_assign_creators_kanban(self):
        """Mở thẳng Kanban kéo-thả giảng viên vào kỳ, thay vì phải "Thêm một
        dòng" + tìm tên từng giảng viên trong tab capacity_ids."""
        self.ensure_one()
        return self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_eaut_showcase_creator_kanban'
        )
