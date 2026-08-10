# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ShowcaseAdvisorRegistration(models.Model):
    _name = 'eaut_showcase.advisor.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Hồ sơ đăng ký chọn giảng viên hướng dẫn đồ án của sinh viên'
    _order = 'create_date desc'
    _rec_name = 'student_id'

    term_id = fields.Many2one(
        'eaut_showcase.term', string='Kỳ đồ án', required=True, ondelete='cascade',
    )
    student_id = fields.Many2one('res.partner', string='Sinh viên', required=True)
    line_ids = fields.One2many(
        'eaut_showcase.advisor.registration.line', 'registration_id', string='Nguyện vọng',
    )
    state = fields.Selection([
        ('draft', 'Chưa nộp'),
        ('in_progress', 'Đang xét'),
        ('approved', 'Đã có GVHD'),
        ('unassigned', 'Chưa có GVHD'),
    ], string='Trạng thái', default='draft', required=True)
    approved_creator_id = fields.Many2one(
        'eaut_showcase.creator', string='Giảng viên hướng dẫn',
        compute='_compute_approved_creator', store=True,
    )

    assigned_creator_id = fields.Many2one(
        'eaut_showcase.creator', string='Đang thuộc giảng viên',
        help="Đồng bộ tự động theo dòng nguyện vọng đang pending/approved — "
             "dùng để group-by và kéo-thả trên Kanban xử lý sinh viên chưa gán.",
    )

    _sql_constraints = [
        ('term_student_uniq', 'unique(term_id, student_id)',
         'Sinh viên này đã có hồ sơ đăng ký trong kỳ này rồi.'),
    ]

    def write(self, vals):
        if 'assigned_creator_id' in vals and not self.env.context.get('advisor_internal_write'):
            # Admin vừa kéo-thả thẻ trên Kanban sang cột 1 giảng viên khác —
            # chạy đúng nghiệp vụ gán (kiểm tra sức chứa, huỷ các dòng cũ)
            # thay vì chỉ ghi thẳng giá trị field như kanban mặc định làm.
            creator_id = vals.pop('assigned_creator_id')
            for reg in self:
                reg._admin_assign(creator_id)
            if not vals:
                return True
        return super().write(vals)

    @api.depends('line_ids.state')
    def _compute_approved_creator(self):
        for reg in self:
            approved_line = reg.line_ids.filtered(lambda l: l.state == 'approved')
            reg.approved_creator_id = approved_line.creator_id if approved_line else False

    def action_submit(self, creator_ids):
        """creator_ids: danh sách id giảng viên theo đúng thứ tự ưu tiên
        (tối đa term.max_preferences phần tử)."""
        self.ensure_one()
        if self.line_ids:
            raise UserError('Hồ sơ này đã được nộp, không thể nộp lại.')
        if len(creator_ids) > self.term_id.max_preferences:
            raise UserError('Vượt quá số nguyện vọng tối đa cho phép.')
        Line = self.env['eaut_showcase.advisor.registration.line']
        for sequence, creator_id in enumerate(creator_ids, start=1):
            Line.create({
                'registration_id': self.id,
                'creator_id': creator_id,
                'sequence': sequence,
                'state': 'waiting',
            })
        self.state = 'in_progress'
        self._activate_next_line()

    def _activate_next_line(self):
        self.ensure_one()
        next_line = self.line_ids.filtered(lambda l: l.state == 'waiting').sorted('sequence')[:1]
        if not next_line:
            self.write({'state': 'unassigned'})
            self.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})
            self.message_post(
                body='Cả %s nguyện vọng đều không thành công. Nhà trường sẽ liên hệ '
                     'để phân giảng viên hướng dẫn cho bạn.' % self.term_id.max_preferences,
                partner_ids=self.student_id.ids,
            )
            return
        next_line._activate()
        if next_line.state == 'pending':
            self.with_context(advisor_internal_write=True).write({
                'assigned_creator_id': next_line.creator_id.id,
            })
            self.message_post(
                body='Nguyện vọng của bạn đang được chuyển sang giảng viên <b>%s</b>, '
                     'chờ phản hồi.' % next_line.creator_id.name,
                partner_ids=self.student_id.ids,
            )

    def action_reset_for_withdrawal(self):
        """Giảng viên rút khỏi kỳ giữa lúc đang mở vote — reset toàn bộ hồ sơ
        để sinh viên vote lại từ đầu (ngoại lệ duy nhất cho quy tắc SV không
        được tự đổi nguyện vọng)."""
        for reg in self:
            reg.line_ids.unlink()
            reg.write({'state': 'draft'})
            reg.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})

    def _admin_assign(self, creator_id):
        """Admin kéo-thả 1 SV (thường đang 'unassigned') vào cột giảng viên
        trên Kanban — gán tay, bỏ qua luồng nguyện vọng nối tiếp bình thường."""
        self.ensure_one()
        if not creator_id:
            # Kéo về cột "Chưa gán" — chỉ huỷ gán hiện tại, không cần logic thêm.
            self.line_ids.filtered(lambda l: l.state in ('waiting', 'pending', 'approved')).write({
                'state': 'cancelled', 'decided_date': fields.Datetime.now(),
            })
            self.write({'state': 'unassigned'})
            self.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})
            return

        capacity = self.env['eaut_showcase.term.capacity'].search([
            ('term_id', '=', self.term_id.id), ('creator_id', '=', creator_id),
        ], limit=1)
        if capacity:
            self.env.cr.execute(
                'SELECT id FROM eaut_showcase_term_capacity WHERE id = %s FOR UPDATE',
                (capacity.id,),
            )
            approved_count = self.env['eaut_showcase.advisor.registration.line'].search_count([
                ('term_id', '=', self.term_id.id),
                ('creator_id', '=', creator_id),
                ('state', '=', 'approved'),
            ])
            if approved_count >= capacity.max_students:
                raise ValidationError('Giảng viên đã đủ số lượng sinh viên nhận hướng dẫn.')

        now = fields.Datetime.now()
        self.line_ids.filtered(lambda l: l.state in ('waiting', 'pending', 'approved')).write({
            'state': 'cancelled', 'decided_date': now,
        })
        existing_line = self.line_ids.filtered(lambda l: l.creator_id.id == creator_id)
        if existing_line:
            existing_line.write({'state': 'approved', 'decided_date': now})
        else:
            next_sequence = max(self.line_ids.mapped('sequence') or [0]) + 1
            self.env['eaut_showcase.advisor.registration.line'].create({
                'registration_id': self.id,
                'creator_id': creator_id,
                'sequence': next_sequence,
                'state': 'approved',
                'decided_date': now,
            })
        self.write({'state': 'approved'})
        self.with_context(advisor_internal_write=True).write({'assigned_creator_id': creator_id})


class ShowcaseAdvisorRegistrationLine(models.Model):
    _name = 'eaut_showcase.advisor.registration.line'
    _description = 'Nguyện vọng chọn giảng viên hướng dẫn'
    _order = 'registration_id, sequence'

    registration_id = fields.Many2one(
        'eaut_showcase.advisor.registration', string='Hồ sơ đăng ký',
        required=True, ondelete='cascade',
    )
    term_id = fields.Many2one(
        related='registration_id.term_id', string='Kỳ đồ án', store=True,
    )
    student_id = fields.Many2one(
        related='registration_id.student_id', string='Sinh viên', store=True,
    )
    creator_id = fields.Many2one('eaut_showcase.creator', string='Giảng viên', required=True)
    sequence = fields.Integer(string='Nguyện vọng số')
    note = fields.Text(string='Lời giới thiệu')

    state = fields.Selection([
        ('waiting', 'Chờ kích hoạt'),
        ('pending', 'Đang chờ giảng viên duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Bị từ chối'),
        ('expired', 'Hết hạn phản hồi'),
        ('cancelled', 'Đã huỷ'),
    ], string='Trạng thái', default='waiting', required=True)

    activated_date = fields.Datetime(string='Ngày kích hoạt')
    deadline = fields.Datetime(string='Hạn phản hồi')
    decided_date = fields.Datetime(string='Ngày quyết định')

    _sql_constraints = [
        ('registration_creator_uniq', 'unique(registration_id, creator_id)',
         'Không thể chọn trùng 1 giảng viên trong cùng hồ sơ đăng ký.'),
        ('registration_sequence_uniq', 'unique(registration_id, sequence)',
         'Không thể trùng thứ tự nguyện vọng trong cùng hồ sơ đăng ký.'),
    ]

    def _get_capacity(self):
        self.ensure_one()
        return self.env['eaut_showcase.term.capacity'].search([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
        ], limit=1)

    def _notify(self, partner, body):
        self.ensure_one()
        if partner:
            self.registration_id.message_post(body=body, partner_ids=partner.ids)

    def _activate(self):
        """Kích hoạt 1 dòng đang chờ: gửi cho giảng viên, hoặc tự động bỏ qua
        luôn nếu giảng viên đã rút/đã đầy chỗ ngay từ đầu."""
        self.ensure_one()
        capacity = self._get_capacity()
        if not capacity or capacity.withdrawn or capacity.remaining_slots <= 0:
            self.write({'state': 'rejected', 'decided_date': fields.Datetime.now()})
            self.registration_id._activate_next_line()
            return
        now = fields.Datetime.now()
        self.write({
            'state': 'pending',
            'activated_date': now,
            'deadline': now + timedelta(hours=self.term_id.sla_hours or 48),
        })
        self._notify(
            self.creator_id.user_id.partner_id,
            'Có sinh viên <b>%s</b> vừa đăng ký chọn bạn làm giảng viên hướng dẫn — '
            'vào /my/advisor-requests để duyệt.' % self.student_id.name,
        )

    def action_approve(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError('Nguyện vọng này không ở trạng thái chờ duyệt.')
        capacity = self._get_capacity()
        if capacity:
            # Khoá row sức chứa để tránh 2 giảng viên/2 request duyệt cùng lúc
            # vượt quá max_students (race condition khi nhiều nguyện vọng dồn
            # vào đúng slot cuối cùng).
            self.env.cr.execute(
                'SELECT id FROM eaut_showcase_term_capacity WHERE id = %s FOR UPDATE',
                (capacity.id,),
            )
            approved_count = self.env['eaut_showcase.advisor.registration.line'].search_count([
                ('term_id', '=', self.term_id.id),
                ('creator_id', '=', self.creator_id.id),
                ('state', '=', 'approved'),
            ])
            if approved_count >= capacity.max_students:
                raise ValidationError('Giảng viên đã đủ số lượng sinh viên nhận hướng dẫn.')
        self.write({'state': 'approved', 'decided_date': fields.Datetime.now()})
        other_lines = (self.registration_id.line_ids - self).filtered(
            lambda l: l.state in ('waiting', 'pending'))
        other_lines.write({'state': 'cancelled', 'decided_date': fields.Datetime.now()})
        self.registration_id.write({'state': 'approved'})
        self.registration_id.with_context(advisor_internal_write=True).write({
            'assigned_creator_id': self.creator_id.id,
        })
        self._notify(
            self.student_id,
            'Chúc mừng! Giảng viên <b>%s</b> đã duyệt làm giảng viên hướng dẫn của bạn.'
            % self.creator_id.name,
        )

    def action_reject(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError('Nguyện vọng này không ở trạng thái chờ duyệt.')
        self.write({'state': 'rejected', 'decided_date': fields.Datetime.now()})
        self._notify(
            self.student_id,
            'Giảng viên <b>%s</b> đã từ chối nguyện vọng của bạn. Hệ thống sẽ tự '
            'động chuyển sang nguyện vọng kế tiếp (nếu có).' % self.creator_id.name,
        )
        self.registration_id._activate_next_line()

    @api.model
    def _cron_expire_pending_lines(self):
        now = fields.Datetime.now()
        expired_lines = self.search([
            ('state', '=', 'pending'),
            ('deadline', '<', now),
        ])
        for line in expired_lines:
            line.write({'state': 'expired', 'decided_date': now})
            line._notify(
                line.student_id,
                'Giảng viên <b>%s</b> không phản hồi trong thời hạn. Hệ thống sẽ tự '
                'động chuyển sang nguyện vọng kế tiếp (nếu có).' % line.creator_id.name,
            )
            line.registration_id._activate_next_line()
