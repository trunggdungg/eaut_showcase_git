# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eaut_showcase_term import DEFAULT_SLA_HOURS

_logger = logging.getLogger(__name__)

# ============ NỘI DUNG THÔNG BÁO (chatter + email) ============
# Tách riêng khỏi logic nghiệp vụ để dễ tìm/sửa chữ khi cần — chỗ nào có %s thì
# điền bằng % operator ngay tại nơi dùng. Các message "kết quả" (MSG_MOVED_TO_NEXT,
# MSG_ALL_FAILED_*) được ghép nối với 1 "lý do" (vì sao có kết quả này — bị từ chối
# hay hết hạn) thành 1 email duy nhất cho sinh viên, xem _activate_next_line().
# Chỉ chứa CÂU CHỮ thuần — phần khung/badge/nút CTA nằm ở khối EMAIL_* + _email_*()
# ngay dưới, ghép lại tại nơi gọi message_post().
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
MSG_NEW_PENDING_REQUEST = 'Sinh viên <b>%s</b> vừa đăng ký chọn bạn làm giảng viên hướng dẫn.'
MSG_LINE_APPROVED = (
    'Giảng viên <b>%s</b> đã duyệt làm giảng viên hướng dẫn của bạn. Chúc mừng bạn!'
)

MSG_CREATOR_WITHDRAWN_RESET = (
    'Giảng viên <b>%s</b> đã rút khỏi kỳ này. Nguyện vọng trước đó của bạn đã '
    'được reset — vui lòng chọn lại giảng viên hướng dẫn.'
)
MSG_REMINDER_DEADLINE_SOON = (
    'Yêu cầu hướng dẫn của sinh viên <b>%s</b> sắp hết hạn phản hồi (còn dưới 6 giờ).'
)
# ============ KHUNG/MÀU EMAIL — dùng chung với layout eaut_showcase.mail_layout_advisor_notification ============
# Khung ngoài (thanh tên trường + footer) nằm trong template QWeb ở
# views/eaut_showcase_mail_layout_views.xml, truyền qua email_layout_xmlid mỗi lần
# message_post() ở dưới — CHỈ áp dụng cho email thật gửi ra ngoài (Chatter không
# bao giờ render qua layout này, nó luôn hiện thẳng message.body). Các hàm
# _email_* dưới đây đều trả về markupsafe.Markup nên message_post() coi nội
# dung đã an toàn sẵn, không gọi html_sanitize() lại — KHÔNG được truyền
# sanitize=False cho message_post() (Odoo 19 không còn chấp nhận tham số này,
# gọi vào sẽ bị _notify_thread() raise ValueError). Widget hiển thị Chatter tự
# lọc lại thuộc tính style mỗi lần render (giữ color/font-weight, bỏ
# background/padding/border-radius), nên mỗi thẻ badge/nút CTA còn gắn thêm
# class (o_eaut_notif_*, định nghĩa ở static/src/css/backend.css, nạp qua
# bundle web.assets_backend) — CSS từ file ngoài không nằm trong HTML của
# message nên không bị lọc theo cách này. Email thật gửi ra ngoài thì đọc đúng
# style inline như bình thường.
EMAIL_BRAND_COLOR = '#7b3f61'
EMAIL_BADGE_COLORS = {
    'success': ('#e6f4ea', '#1e7e34'),
    'danger': ('#fdecea', '#b02a37'),
    'info': ('#e8f0fe', '#1a56db'),
    'warning': ('#fff4e5', '#b25e00'),
}
EMAIL_STUDENT_PATH = '/my/advisor'
EMAIL_LECTURER_PATH = '/my/advisor-requests'
EMAIL_LAYOUT_XMLID = 'eaut_showcase.mail_layout_advisor_notification'


def _email_badge(text, kind):
    bg, fg = EMAIL_BADGE_COLORS.get(kind, ('#f0f0f0', '#555555'))
    return Markup(
        '<span class="o_eaut_notif_badge o_eaut_notif_badge_%s" '
        'style="background:%s;color:%s;padding:2px 10px;border-radius:4px;'
        'font-weight:600;font-size:13px;white-space:nowrap;">%s</span>'
    ) % (kind, bg, fg, text)


def _email_cta(url, label):
    return Markup(
        '<div class="o_eaut_notif_cta_wrap" style="margin-top:16px;">'
        '<a href="%s" class="o_eaut_notif_cta" style="display:inline-block;'
        'background:%s;color:#ffffff;padding:10px 18px;border-radius:6px;'
        'text-decoration:none;font-weight:600;font-size:14px;">%s</a></div>'
    ) % (url, EMAIL_BRAND_COLOR, label)


def _email_body(greeting_name, paragraphs, cta_url=None, cta_label=None):
    """Dựng phần nội dung "thẻ" bên trong khung email — lời chào + các đoạn nội
    dung (mỗi đoạn tự chèn badge nếu cần, xem các nơi gọi) + 1 nút CTA cuối
    (nếu có). paragraphs: list các đoạn Markup, đoạn nào rỗng/None bị bỏ qua —
    tiện cho trường hợp không có "reason" (VD: submit lần đầu)."""
    html = Markup(
        '<p class="o_eaut_notif_p" style="margin:0 0 12px;font-size:14px;'
        'color:#333333;">Chào <b>%s</b>,</p>'
    ) % greeting_name
    for p in paragraphs:
        if not p:
            continue
        html += Markup(
            '<p class="o_eaut_notif_p" style="margin:0 0 12px;font-size:14px;'
            'color:#333333;line-height:1.6;">%s</p>'
        ) % p
    if cta_url:
        html += _email_cta(cta_url, cta_label)
    return Markup('<div class="o_eaut_notif_card">%s</div>') % html

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
            outcome_text = MSG_ALL_FAILED_SINGLE if submitted_count == 1 \
                else Markup(MSG_ALL_FAILED_MULTI) % submitted_count
            outcome = Markup('%s %s') % (_email_badge('Chưa có GVHD', 'danger'), outcome_text)
            body = _email_body(
                self.student_id.name, [reason, outcome],
                self.get_base_url() + EMAIL_STUDENT_PATH, 'Xem trạng thái nguyện vọng',
            )
            self.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=self.student_id.ids,
                email_layout_xmlid=EMAIL_LAYOUT_XMLID)
            return
        next_line._activate(reason=reason)
        if next_line.state == 'pending':
            self.with_context(advisor_internal_write=True).write({
                'assigned_creator_id': next_line.creator_id.id,
            })
            outcome_text = Markup(MSG_MOVED_TO_NEXT) % next_line.creator_id.name
            outcome = Markup('%s %s') % (_email_badge('Đang chuyển tiếp', 'info'), outcome_text)
            body = _email_body(
                self.student_id.name, [reason, outcome],
                self.get_base_url() + EMAIL_STUDENT_PATH, 'Xem trạng thái nguyện vọng',
            )
            self.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=self.student_id.ids,
                email_layout_xmlid=EMAIL_LAYOUT_XMLID)

    def action_reset_for_withdrawal(self, creator=None):
        """Giảng viên rút khỏi kỳ giữa lúc đang mở vote — reset toàn bộ hồ sơ
        để sinh viên vote lại từ đầu (ngoại lệ duy nhất cho quy tắc SV không
          được tự đổi nguyện vọng). creator (nếu có): GV vừa rút, để báo rõ
        cho SV biết vì sao hồ sơ của họ bị reset. Từng hồ sơ chạy trong 1
        savepoint riêng — 1 sinh viên lỗi (VD. gửi thông báo thất bại) không
        được phép làm mất luôn việc reset của những sinh viên khác của cùng
        giảng viên vừa rút trong cùng 1 lần gọi."""
        for reg in self:
            try:
                with self.env.cr.savepoint():
                    reg.line_ids.unlink()
                    reg.write({'state': 'draft'})
                    reg.with_context(advisor_internal_write=True).write(
                        {'assigned_creator_id': False})
                    if creator:
                        outcome = Markup('%s %s') % (
                            _email_badge('Cần chọn lại', 'warning'),
                            Markup(MSG_CREATOR_WITHDRAWN_RESET) % creator.name,
                        )
                        body = _email_body(
                            reg.student_id.name, [outcome],
                            reg.get_base_url() + EMAIL_STUDENT_PATH,
                            'Chọn lại giảng viên hướng dẫn',
                        )
                        reg.with_context(mail_notify_force_send=False).message_post(
                            body=body, partner_ids=reg.student_id.ids,
                            email_layout_xmlid=EMAIL_LAYOUT_XMLID,
                        )
            except Exception:
                _logger.exception(
                    'Lỗi khi reset hồ sơ đăng ký id=%s do giảng viên rút kỳ — '
                    'bỏ qua, cần xử lý tay.', reg.id,
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
            self.registration_id.with_context(mail_notify_force_send=False).message_post(
                body=body, partner_ids=partner.ids,
                email_layout_xmlid=EMAIL_LAYOUT_XMLID)

    def _activate(self, reason=None):
        """Kích hoạt 1 dòng đang chờ: gửi cho giảng viên, hoặc tự động bỏ qua
        luôn nếu giảng viên đã rút/đã đầy chỗ ngay từ đầu — reason (nếu có) được
        truyền tiếp cho _activate_next_line() khi phải dò tiếp, để không mất lý
        do gốc (bị từ chối/hết hạn) khi ghép vào email kết quả cuối cùng."""
        self.ensure_one()
        capacity = self._get_capacity()
        if not capacity or capacity.withdrawn:
            self.write({'state': 'rejected', 'decided_date': fields.Datetime.now()})
            self.registration_id._activate_next_line(reason=reason)
            return
        # Khoá row sức chứa rồi đếm lại trực tiếp từ DB — cùng cơ chế khoá như
        # action_approve()/_admin_assign(), KHÔNG dùng compute remaining_slots
        # (nó chỉ khai @api.depends trên term_id/creator_id nên không tự làm
        # mới khi 1 dòng khác của cùng giảng viên vừa được ghi state trong
        # cùng transaction — VD. nhiều dòng cùng 1 giảng viên được xử lý nối
        # tiếp trong 1 lượt cron _cron_expire_pending_lines). Nếu không khoá +
        # đếm tươi, 2 nguyện vọng cùng nhắm 1 giảng viên được kích hoạt gần
        # như đồng thời có thể cùng đọc "còn chỗ" và cùng lọt qua, vượt quá
        # max_students.
        self.env.cr.execute(
            'SELECT id FROM eaut_showcase_term_capacity WHERE id = %s FOR UPDATE',
            (capacity.id,),
        )
        taken_count = self.env['eaut_showcase.advisor.registration.line'].search_count([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
            ('state', 'in', ('approved', 'pending')),
        ])
        if taken_count >= capacity.max_students:
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
            _email_body(
                self.creator_id.name,
                [Markup('%s %s') % (
                    _email_badge('Yêu cầu mới', 'info'),
                    Markup(MSG_NEW_PENDING_REQUEST) % self.student_id.name,
                )],
                self.get_base_url() + EMAIL_LECTURER_PATH, 'Vào duyệt yêu cầu',
            ),
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
            _email_body(
                self.student_id.name,
                [Markup('%s %s') % (
                    _email_badge('Đã duyệt', 'success'),
                    Markup(MSG_LINE_APPROVED) % self.creator_id.name,
                )],
                self.get_base_url() + EMAIL_STUDENT_PATH, 'Xem hồ sơ của tôi',
            ),
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
        (tối đa 1 giờ) mới cập nhật đúng trạng thái. Mỗi dòng chạy trong 1
        savepoint riêng — nếu dòng nào lỗi (VD. gửi thông báo thất bại) chỉ
        dòng đó bị rollback, không kéo theo mất luôn kết quả của các dòng
        khác đã xử lý xong trong cùng 1 lượt cron/thao tác, và các dòng còn
        lại vẫn được tiếp tục xử lý thay vì bị chặn đứng ở dòng lỗi đầu tiên."""
        now = fields.Datetime.now()
        for line in self:
            try:
                with self.env.cr.savepoint():
                    line.write({'state': 'expired', 'decided_date': now})
                    # Cùng cơ chế gộp email như action_reject() — không _notify()
                    # riêng ở đây, để _activate_next_line() ghép chung với email
                    # kết quả.
                    notify_reason = Markup(MSG_LINE_EXPIRED) % line.creator_id.name
                    line.registration_id._activate_next_line(reason=notify_reason)
            except Exception:
                _logger.exception(
                    'Lỗi khi xử lý hết hạn nguyện vọng id=%s (registration=%s) — '
                    'bỏ qua, sẽ thử lại ở lượt cron kế tiếp.',
                    line.id, line.registration_id.id,
                )

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
            # Savepoint riêng từng dòng — 1 dòng gửi thông báo lỗi không được
            # phép rollback luôn reminder_sent của các dòng khác đã gửi thành
            # công trong cùng lượt cron này.
            try:
                with self.env.cr.savepoint():
                    line._notify(
                        line.creator_id.user_id.partner_id,
                        _email_body(
                            line.creator_id.name,
                            [Markup('%s %s') % (
                                _email_badge('Sắp hết hạn', 'warning'),
                                Markup(MSG_REMINDER_DEADLINE_SOON) % line.student_id.name,
                            )],
                            line.get_base_url() + EMAIL_LECTURER_PATH, 'Duyệt ngay',
                        ),
                    )
                    line.reminder_sent = True
            except Exception:
                _logger.exception(
                    'Lỗi khi gửi nhắc sắp hết hạn cho dòng nguyện vọng id=%s — '
                    'bỏ qua, sẽ thử lại ở lượt cron kế tiếp.', line.id,
                )