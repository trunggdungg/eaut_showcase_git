# -*- coding: utf-8 -*-
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eaut_showcase_term import DEFAULT_SLA_HOURS

# ============ NỘI DUNG THÔNG BÁO (chatter + email) ============
# Tách riêng khỏi logic nghiệp vụ để dễ tìm/sửa chữ khi cần — chỗ nào có %s thì
# điền bằng % operator ngay tại nơi dùng. Các message "kết quả" (MSG_MOVED_TO_NEXT,
# MSG_ALL_FAILED_*) được ghép nối với 1 "lý do" (vì sao có kết quả này — bị từ chối
# hay hết hạn) thành 1 email duy nhất cho sinh viên, xem _activate_next_line().
MSG_LINE_REJECTED = 'Giảng viên <b>%s</b> đã từ chối nguyện vọng của bạn.%s'
MSG_LINE_REJECTED_REASON_SUFFIX = ' Lý do: %s'
MSG_LINE_EXPIRED = 'Giảng viên <b>%s</b> không phản hồi trong thời hạn.'
MSG_MOVED_TO_NEXT = (
    'Nguyện vọng của bạn đang được chuyển sang giảng viên <b>%s</b>, chờ phản hồi.'
)
MSG_ALL_FAILED_SINGLE = (
    'Nguyện vọng của bạn không thành công. Nhà trường sẽ liên hệ để phân '
    'giảng viên hướng dẫn cho bạn.'
)
MSG_ALL_FAILED_MULTI = (
    'Cả %s nguyện vọng đều không thành công. Nhà trường sẽ liên hệ để phân '
    'giảng viên hướng dẫn cho bạn.'
)
MSG_NEW_PENDING_REQUEST = (
    'Có sinh viên <b>%s</b> vừa đăng ký chọn bạn làm giảng viên hướng dẫn — '
    'vào /my/advisor-requests để duyệt.'
)
MSG_LINE_APPROVED = 'Chúc mừng! Giảng viên <b>%s</b> đã duyệt làm giảng viên hướng dẫn của bạn.'
MSG_CREATOR_WITHDRAWN_RESET = (
    'Giảng viên <b>%s</b> đã rút khỏi kỳ này. Nguyện vọng trước đó của '
    'bạn đã được reset — vui lòng vào /my/advisor để chọn lại giảng '
    'viên hướng dẫn.'
)
MSG_REMINDER_DEADLINE_SOON = (
    'Yêu cầu hướng dẫn của sinh viên <b>%s</b> sắp hết hạn phản hồi (còn dưới '
    '6 giờ) — vào /my/advisor-requests để duyệt/từ chối.'
)


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
        group_expand='_group_expand_assigned_creators',
        help="Đồng bộ tự động theo dòng nguyện vọng đang pending/approved — "
             "dùng để group-by và kéo-thả trên Kanban xử lý sinh viên chưa gán.",
    )

    _sql_constraints = [
        ('term_student_uniq', 'unique(term_id, student_id)',
         'Sinh viên này đã có hồ sơ đăng ký trong kỳ này rồi.'),
    ]

    @api.model
    def _group_expand_assigned_creators(self, creators, domain):
        # Luôn hiện cột cho mọi giảng viên đang có sức chứa, kể cả khi chưa có
        # SV nào — nếu không, Kanban chỉ hiện cột cho giảng viên đã có ít
        # nhất 1 SV rơi đúng field assigned_creator_id. Nếu người dùng đã lọc
        # theo 1 kỳ cụ thể (tìm kiếm "Kỳ đồ án"), chỉ hiện giảng viên của
        # đúng kỳ đó — tránh trộn giảng viên nhiều kỳ/khoa khác nhau vào
        # chung 1 board khi trường có nhiều kỳ mở song song.
        term_ids = self._term_ids_from_domain(domain)
        capacity_domain = [('term_id', 'in', term_ids)] if term_ids is not None \
            else [('term_id.state', 'in', ('draft', 'open'))]
        return self.env['eaut_showcase.term.capacity'].search(capacity_domain).creator_id

    @api.model
    def _term_ids_from_domain(self, domain):
        """Rút ra danh sách term_id đang bị lọc trong domain hiện tại của
        search view (nếu có) — chỉ xử lý dạng đơn giản ('term_id', '='/'in', ...),
        đủ dùng cho ô tìm kiếm 'Kỳ đồ án' trên Kanban này."""
        for condition in domain or []:
            if isinstance(condition, (list, tuple)) and len(condition) == 3 \
                    and condition[0] == 'term_id':
                value = condition[2]
                return list(value) if isinstance(value, (list, tuple)) else [value]
        return None

    def unlink(self):
        for reg in self:
            if reg.state not in ('draft', 'unassigned'):
                raise UserError(
                    'Không thể xoá — sinh viên "%s" đang ở trạng thái "%s". '
                    'Dùng nút "Bỏ gán" trên Kanban để đưa về "Chưa có GVHD" '
                    'trước, tránh mất dấu vết lịch sử đăng ký/duyệt.'
                    % (reg.student_id.name, dict(reg._fields['state'].selection).get(reg.state))
                )
        return super().unlink()

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

    def action_submit(self, creator_ids, notes=None, topics=None):
        """creator_ids: danh sách id giảng viên theo đúng thứ tự ưu tiên
        (tối đa term.max_preferences phần tử). notes/topics (nếu có): cùng
        độ dài với creator_ids, giới thiệu bản thân + đề tài dự kiến riêng
        cho từng nguyện vọng."""
        self.ensure_one()
        if self.line_ids:
            raise UserError('Hồ sơ này đã được nộp, không thể nộp lại.')
        if len(creator_ids) > self.term_id.max_preferences:
            raise UserError('Vượt quá số nguyện vọng tối đa cho phép.')
        notes = notes or [''] * len(creator_ids)
        topics = topics or [''] * len(creator_ids)
        Line = self.env['eaut_showcase.advisor.registration.line']
        for sequence, (creator_id, note, topic) in enumerate(
                zip(creator_ids, notes, topics), start=1):
            Line.create({
                'registration_id': self.id,
                'creator_id': creator_id,
                'sequence': sequence,
                'state': 'waiting',
                'note': note or False,
                'proposed_topic': topic or False,
            })
        self.state = 'in_progress'
        self._activate_next_line()

    def _activate_next_line(self, reason=None):
        """reason (nếu có): lý do dẫn tới lượt kích hoạt này (bị từ chối/hết hạn),
        được ghép vào chung 1 email với kết quả (chuyển sang GV kế tiếp/thất bại
        hết) — tránh gửi 2 email liên tiếp cho cùng 1 sinh viên trong 1 lượt xử
        lý. Khi tự dò qua các dòng bị auto-loại (GV đã rút/đầy chỗ) mà không có
        kết quả cuối ngay, reason được truyền tiếp xuống để không bị mất."""
        self.ensure_one()
        next_line = self.line_ids.filtered(lambda l: l.state == 'waiting').sorted('sequence')[:1]
        if not next_line:
            self.write({'state': 'unassigned'})
            self.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})
            submitted_count = len(self.line_ids)
            outcome = Markup(MSG_ALL_FAILED_SINGLE) if submitted_count == 1 \
                else Markup(MSG_ALL_FAILED_MULTI) % submitted_count
            body = Markup('%s %s') % (reason, outcome) if reason else outcome
            self.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=self.student_id.ids)
            return
        next_line._activate(reason=reason)
        if next_line.state == 'pending':
            self.with_context(advisor_internal_write=True).write({
                'assigned_creator_id': next_line.creator_id.id,
            })
            outcome = Markup(MSG_MOVED_TO_NEXT) % next_line.creator_id.name
            body = Markup('%s %s') % (reason, outcome) if reason else outcome
            self.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=self.student_id.ids)

    def action_reset_for_withdrawal(self, creator=None):
        """Giảng viên rút khỏi kỳ giữa lúc đang mở vote — reset toàn bộ hồ sơ
        để sinh viên vote lại từ đầu (ngoại lệ duy nhất cho quy tắc SV không
          được tự đổi nguyện vọng). creator (nếu có): GV vừa rút, để báo rõ
        cho SV biết vì sao hồ sơ của họ bị reset."""
        for reg in self:
            reg.line_ids.unlink()
            reg.write({'state': 'draft'})
            reg.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})
            if creator:
                reg.with_context(mail_notify_force_send=False).message_post(
                    body=Markup(MSG_CREATOR_WITHDRAWN_RESET) % creator.name,
                    partner_ids=reg.student_id.ids,
                )

    def action_unassign(self):
        """Nút "Bỏ gán" trên thẻ Kanban — đưa SV về "Chưa có GVHD" ngay lập
        tức, không phụ thuộc việc cột "Không" có đang hiện trên board hay
        không (cột đó tự ẩn khi không còn ai ở trạng thái đó)."""
        for reg in self:
            reg._admin_assign(False)
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
        if not capacity or capacity.max_students <= 0:
            # (có thể do họ chỉ có sức chứa ở 1 kỳ khác), hoặc đã khai nhưng
            # để 0 — cả 2 trường hợp đều coi như "chưa sẵn sàng nhận SV kỳ
            # này", chặn hẳn, không cho gán vô điều kiện.
            raise ValidationError(
                'Giảng viên này chưa được khai sức chứa ở kỳ "%s" — vào "Kỳ đồ án" > '
                '"Giảng viên nhận hướng dẫn" để thêm giảng viên vào đúng kỳ trước khi gán.'
                % self.term_id.name
            )

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
    note = fields.Text(string='Giới thiệu bản thân')
    proposed_topic = fields.Char(string='Đề tài dự kiến')

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
    reject_reason = fields.Text(string='Lý do từ chối')
    reminder_sent = fields.Boolean(string='Đã nhắc trước hạn', default=False)
    _sql_constraints = [
        ('registration_creator_uniq', 'unique(registration_id, creator_id)',
         'Không thể chọn trùng 1 giảng viên trong cùng hồ sơ đăng ký.'),
        ('registration_sequence_uniq', 'unique(registration_id, sequence)',
         'Không thể trùng thứ tự nguyện vọng trong cùng hồ sơ đăng ký.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._backfill_pending_deadline()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') == 'pending':
            self._backfill_pending_deadline()
        return result

    def _backfill_pending_deadline(self):
        """Đảm bảo mọi dòng ở trạng thái 'pending' luôn có deadline — tránh
        trường hợp tạo/sửa tay (demo data, sửa trực tiếp qua popup dòng
        nguyện vọng...) đưa 1 dòng vào 'pending' mà bỏ qua _activate(), làm
        cột 'Hạn phản hồi' trống trên portal giảng viên."""
        for line in self:
            if line.state == 'pending' and not line.deadline:
                line.write({
                    'activated_date': line.activated_date or fields.Datetime.now(),
                    'deadline': fields.Datetime.now() + timedelta(
                        hours=line.term_id.sla_hours or DEFAULT_SLA_HOURS),
                    'reminder_sent': False,
                })


    def _get_capacity(self):
        self.ensure_one()
        return self.env['eaut_showcase.term.capacity'].search([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
        ], limit=1)

    def _notify(self, partner, body):
        self.ensure_one()
        if partner:
            self.registration_id.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=partner.ids)

    def _activate(self, reason=None):
        """Kích hoạt 1 dòng đang chờ: gửi cho giảng viên, hoặc tự động bỏ qua
        luôn nếu giảng viên đã rút/đã đầy chỗ ngay từ đầu — reason (nếu có) được
        truyền tiếp cho _activate_next_line() khi phải dò tiếp, để không mất lý
        do gốc (bị từ chối/hết hạn) khi ghép vào email kết quả cuối cùng."""
        self.ensure_one()
        capacity = self._get_capacity()
        if not capacity or capacity.withdrawn or capacity.remaining_slots <= 0:
            self.write({'state': 'rejected', 'decided_date': fields.Datetime.now()})
            self.registration_id._activate_next_line(reason=reason)
            return
        now = fields.Datetime.now()
        self.write({
            'state': 'pending',
            'activated_date': now,
            'deadline': now + timedelta(hours=self.term_id.sla_hours or DEFAULT_SLA_HOURS),
            'reminder_sent': False,
        })
        self._notify(
            self.creator_id.user_id.partner_id,
            Markup(MSG_NEW_PENDING_REQUEST) % self.student_id.name,
        )

    def action_approve(self):
        self.ensure_one()
        if self.state == 'pending' and self.deadline and self.deadline < fields.Datetime.now():
            self._expire()
            raise UserError(
                'Yêu cầu này đã quá hạn phản hồi.')
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
            Markup(MSG_LINE_APPROVED) % self.creator_id.name,
        )

    def action_reject(self, reason=None):
        self.ensure_one()
        if self.state == 'pending' and self.deadline and self.deadline < fields.Datetime.now():
            self._expire()
            raise UserError(
                'Yêu cầu này đã quá hạn phản hồi.')
        if self.state != 'pending':
            raise UserError('Nguyện vọng này không ở trạng thái chờ duyệt.')
        reason = (reason or '').strip()
        self.write({
            'state': 'rejected', 'decided_date': fields.Datetime.now(),
            'reject_reason': reason or False,
        })
        # Không gửi email riêng ở đây nữa — ghép chung với email kết quả
        # (chuyển sang GV kế tiếp/thất bại hết) trong _activate_next_line(),
        # tránh sinh viên nhận 2 email liên tiếp cho cùng 1 lượt xử lý.
        reason_txt = (Markup(MSG_LINE_REJECTED_REASON_SUFFIX) % reason) if reason else ''
        notify_reason = Markup(MSG_LINE_REJECTED) % (self.creator_id.name, reason_txt)
        self.registration_id._activate_next_line(reason=notify_reason)

    def _expire(self):
        """Chuyển các dòng 'pending' này sang 'expired' ngay lập tức — dùng
        chung cho cron định kỳ và cho lúc phát hiện trễ hạn ngay tại thời
        điểm GV vào portal/bấm duyệt, không đợi tới lượt cron chạy tiếp theo
        (tối đa 1 giờ) mới cập nhật đúng trạng thái."""
        now = fields.Datetime.now()
        for line in self:
            line.write({'state': 'expired', 'decided_date': now})
            # Cùng cơ chế gộp email như action_reject() — không _notify() riêng ở
            # đây, để _activate_next_line() ghép chung với email kết quả.
            notify_reason = Markup(MSG_LINE_EXPIRED) % line.creator_id.name
            line.registration_id._activate_next_line(reason=notify_reason)

    @api.model
    def _cron_expire_pending_lines(self):
        now = fields.Datetime.now()
        self.search([
            ('state', '=', 'pending'),
            ('deadline', '<', now),
        ])._expire()

    @api.model
    def _cron_remind_pending_lines(self):
        """Nhắc giảng viên khi 1 yêu cầu đang chờ sắp hết hạn (<= 6 giờ) mà
        chưa nhắc lần nào — tránh spam email mỗi giờ chạy cron cho tới lúc
        hết hạn thật."""
        now = fields.Datetime.now()
        threshold = now + timedelta(hours=6)
        soon_due = self.search([
            ('state', '=', 'pending'),
            ('reminder_sent', '=', False),
            ('deadline', '<=', threshold),
            ('deadline', '>', now),
        ])
        for line in soon_due:
            line._notify(
                line.creator_id.user_id.partner_id,
                Markup(MSG_REMINDER_DEADLINE_SOON) % line.student_id.name,
            )
            line.reminder_sent = True