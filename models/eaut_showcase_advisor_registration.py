# -*- coding: utf-8 -*-
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eaut_showcase_term import DEFAULT_SLA_HOURS

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

    def action_cart_add(self, creator_id, note=None, topic=None):
        """SV thêm 1 giảng viên vào hàng chờ nguyện vọng — giống thêm vào hàng chờ
        hàng, chưa gửi cho giảng viên nào cả. Có thể thêm/xoá/đổi thứ tự
        tự do trong hàng chờ, miễn hồ sơ chưa nộp (state == 'draft')."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Bạn đã nộp nguyện vọng rồi, không thể thêm vào hàng chờ nữa.')
        cart_lines = self.line_ids.filtered(lambda l: l.state == 'cart')
        if len(cart_lines) >= self.term_id.max_preferences:
            raise UserError(
                'Giỏ nguyện vọng đã đầy (tối đa %s giảng viên).' % self.term_id.max_preferences)
        if creator_id in cart_lines.mapped('creator_id').ids:
            raise UserError('Giảng viên này đã có trong hàng chờ nguyện vọng của bạn rồi.')
        self.env['eaut_showcase.advisor.registration.line'].create({
            'registration_id': self.id,
            'creator_id': creator_id,
            'sequence': len(cart_lines) + 1,
            'state': 'cart',
            'note': (note or '').strip() or False,
            'proposed_topic': (topic or '').strip() or False,
        })

    def action_cart_remove(self, line_id):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Bạn đã nộp nguyện vọng rồi, không thể sửa hàng chờ nữa.')
        line = self.line_ids.filtered(lambda l: l.id == line_id and l.state == 'cart')
        if not line:
            raise UserError('Không tìm thấy giảng viên này trong giỏ nguyện vọng.')
        line.unlink()
        self._resequence_cart()

    def _resequence_cart(self):
        self.ensure_one()
        cart_lines = self.line_ids.filtered(lambda l: l.state == 'cart').sorted('sequence')
        for index, line in enumerate(cart_lines, start=1):
            if line.sequence != index:
                line.write({'sequence': index})

    def action_cart_move(self, line_id, direction):
        """Đổi thứ tự 1 dòng trong giỏ lên/xuống 1 bậc — dùng nút bấm thay
        vì kéo-thả, đủ dùng cho danh sách ngắn (tối đa vài giảng viên).
        Đi qua sequence tạm -1 để tránh vi phạm unique constraint tạm thời
        khi hoán đổi 2 dòng liền kề."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Bạn đã nộp nguyện vọng rồi, không thể sửa giỏ nữa.')
        if direction not in ('up', 'down'):
            raise UserError('Hướng di chuyển không hợp lệ.')
        cart_lines = self.line_ids.filtered(lambda l: l.state == 'cart').sorted('sequence')
        line = cart_lines.filtered(lambda l: l.id == line_id)
        if not line:
            raise UserError('Không tìm thấy giảng viên này trong hàng chờ nguyện vọng.')
        index = list(cart_lines).index(line)
        target_index = index - 1 if direction == 'up' else index + 1
        if target_index < 0 or target_index >= len(cart_lines):
            return
        other = cart_lines[target_index]
        line_seq, other_seq = line.sequence, other.sequence
        line.write({'sequence': -1})
        other.write({'sequence': line_seq})
        line.write({'sequence': other_seq})

    def action_submit_cart(self):
        """Nộp cả giỏ nguyện vọng 1 lần theo đúng thứ tự đã sắp — sau đó
        khoá lại, không sửa được nữa. Nguyện vọng số 1 (sequence nhỏ nhất)
        được kích hoạt gửi giảng viên trước; các nguyện vọng sau chỉ được
        kích hoạt tự động khi nguyện vọng trước bị từ chối/hết hạn."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError('Bạn đã nộp nguyện vọng rồi, không thể nộp lại.')
        cart_lines = self.line_ids.filtered(lambda l: l.state == 'cart').sorted('sequence')
        if not cart_lines:
            raise UserError(
                'Hàng chờ nguyện vọng đang trống — hãy thêm ít nhất 1 giảng viên trước khi nộp.')
        cart_lines.write({'state': 'waiting'})
        self.state = 'in_progress'
        self._activate_next_line()

    def _activate_next_line(self):
        self.ensure_one()
        next_line = self.line_ids.filtered(lambda l: l.state == 'waiting').sorted('sequence')[:1]
        if not next_line:
            self.write({'state': 'unassigned'})
            self.with_context(advisor_internal_write=True).write({'assigned_creator_id': False})
            submitted_count = len(self.line_ids)
            body = (
                'Nguyện vọng của bạn không thành công. Nhà trường sẽ liên hệ để phân '
                'giảng viên hướng dẫn cho bạn.' if submitted_count == 1 else
                'Cả %s nguyện vọng đều không thành công. Nhà trường sẽ liên hệ '
                'để phân giảng viên hướng dẫn cho bạn.' % submitted_count
            )
            self.message_post(body=body, partner_ids=self.student_id.ids)
            return
        next_line._activate()
        if next_line.state == 'pending':
            self.with_context(advisor_internal_write=True).write({
                'assigned_creator_id': next_line.creator_id.id,
            })
            self.message_post(
                body=Markup(
                    'Nguyện vọng của bạn đang được chuyển sang giảng viên <b>%s</b>, '
                    'chờ phản hồi.'
                ) % next_line.creator_id.name,
                partner_ids=self.student_id.ids,
            )

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
                reg.message_post(
                    body=Markup(
                        'Giảng viên <b>%s</b> đã rút khỏi kỳ này. Nguyện vọng trước đó của '
                        'bạn đã được reset — vui lòng vào /my/advisor để chọn lại giảng '
                        'viên hướng dẫn.'
                    ) % creator.name,
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
        ('cart', 'Trong hàng chờ'),
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
            'deadline': now + timedelta(hours=self.term_id.sla_hours or DEFAULT_SLA_HOURS),
            'reminder_sent': False,
        })
        self._notify(
            self.creator_id.user_id.partner_id,
            Markup(
                'Có sinh viên <b>%s</b> vừa đăng ký chọn bạn làm giảng viên hướng dẫn — '
                'vào /my/advisor-requests để duyệt.'
            ) % self.student_id.name,
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
            Markup(
                'Chúc mừng! Giảng viên <b>%s</b> đã duyệt làm giảng viên hướng dẫn của bạn.'
            ) % self.creator_id.name,
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
        reason_txt = (Markup(' Lý do: %s') % reason) if reason else ''
        self._notify(
            self.student_id,
            Markup(
                'Giảng viên <b>%s</b> đã từ chối nguyện vọng của bạn.%s Hệ thống sẽ tự '
                'động chuyển sang nguyện vọng kế tiếp (nếu có).'
            ) % (self.creator_id.name, reason_txt),
        )
        self.registration_id._activate_next_line()

    def _expire(self):
        """Chuyển các dòng 'pending' này sang 'expired' ngay lập tức — dùng
        chung cho cron định kỳ và cho lúc phát hiện trễ hạn ngay tại thời
        điểm GV vào portal/bấm duyệt, không đợi tới lượt cron chạy tiếp theo
        (tối đa 1 giờ) mới cập nhật đúng trạng thái."""
        now = fields.Datetime.now()
        for line in self:
            line.write({'state': 'expired', 'decided_date': now})
            line._notify(
                line.student_id,
                Markup(
                    'Giảng viên <b>%s</b> không phản hồi trong thời hạn. Hệ thống sẽ tự '
                    'động chuyển sang nguyện vọng kế tiếp (nếu có).'
                ) % line.creator_id.name,
            )
            line.registration_id._activate_next_line()

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
                Markup(
                    'Yêu cầu hướng dẫn của sinh viên <b>%s</b> sắp hết hạn phản hồi (còn dưới '
                    '6 giờ) — vào /my/advisor-requests để duyệt/từ chối.'
                ) % line.student_id.name,
            )
            line.reminder_sent = True