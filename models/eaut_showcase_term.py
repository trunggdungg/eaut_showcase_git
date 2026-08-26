# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

ELIGIBLE_LOG_NAMES_LIMIT = 5

DEFAULT_SLA_HOURS = 24

class ShowcaseTerm(models.Model):
    _name = 'eaut_showcase.term'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Kỳ đồ án — đợt đăng ký chọn giảng viên hướng dẫn'
    _order = 'date_start desc'

    name = fields.Char(string='Tên kỳ', required=True)
    date_start = fields.Date(string='Ngày mở đăng ký', required=True)
    date_end = fields.Date(string='Ngày đóng đăng ký', required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('open', 'Đang mở'),
        ('locked', 'Chốt danh sách'),
        ('closed', 'Đã đóng'),
    ], string='Trạng thái', default='draft', required=True,
        help="Đang mở: SV nộp nguyện vọng, GV tự đăng ký/rút sức chứa. Chốt "
             "danh sách: khoá GV rút khỏi kỳ và SV nộp mới, nhưng vẫn hiện "
             "công khai trên website. Đã đóng: công tắc ẩn GV của kỳ này "
             "khỏi website.")

    sla_hours = fields.Integer(
        string='Hạn phản hồi của giảng viên (giờ)', default=DEFAULT_SLA_HOURS,
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

    def unlink(self):
        """term_id trên advisor.registration/term.capacity dùng
        ondelete='cascade' ở tầng DB — xoá thẳng 1 Kỳ sẽ để Postgres tự xoá
        cascade toàn bộ hồ sơ đăng ký/nguyện vọng/sức chứa của kỳ đó, KHÔNG
        đi qua unlink() Python của 2 model con nên bỏ qua hẳn các chặn xoá
        đã viết ở đó (SV đã duyệt/đang chờ...). Chặn ở đây — chỉ cho xoá kỳ
        nào hoàn toàn chưa có dữ liệu (chưa giảng viên nào khai sức chứa,
        chưa sinh viên nào có hồ sơ đăng ký, kể cả hồ sơ rỗng tự tạo qua
        "Sinh viên đủ điều kiện") — không quan tâm trạng thái kỳ đang là gì,
        vì kỳ trống thì dù 'closed' hay 'draft' cũng chẳng có gì để mất."""
        for term in self:
            if term.registration_ids or term.capacity_ids:
                raise UserError(
                    'Không thể xoá kỳ "%s" — kỳ này đã có sinh viên đăng ký hoặc giảng viên '
                    'khai sức chứa. Gỡ hết dữ liệu liên quan trước nếu chắc chắn không cần '
                    'giữ kỳ này nữa.' % term.name
                )
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        terms = super().create(vals_list)
        terms._sync_eligible_student_registrations()
        return terms

    def write(self, vals):
        old_eligible_by_term = {}
        if 'eligible_student_ids' in vals:
            old_eligible_by_term = {term.id: term.eligible_student_ids for term in self}
        result = super().write(vals)
        if 'eligible_student_ids' in vals:
            self._sync_eligible_student_registrations()
            self._cleanup_removed_eligible_students(old_eligible_by_term)
            self._log_eligible_student_changes(old_eligible_by_term)
        return result

    def _log_eligible_student_changes(self, old_eligible_by_term):
        """Log gọn phần THAY ĐỔI (thêm/bớt) vào chatter — không dùng
        tracking=True mặc định của Odoo cho field này vì nó dump nguyên
        danh sách cũ + mới đầy đủ mỗi lần đổi, với kỳ có hàng trăm SV thì
        1 dòng chatter sẽ dài không đọc nổi. Tên chỉ liệt kê tối đa
        ELIGIBLE_LOG_NAMES_LIMIT người, còn lại rút gọn thành "và N khác"."""
        for term in self:
            old = old_eligible_by_term.get(term.id, self.env['res.partner'])
            new = term.eligible_student_ids
            added = new - old
            removed = old - new
            lines = []
            if added:
                lines.append(Markup('Thêm %s') % self._format_eligible_names(added, 'sinh viên đủ điều kiện'))
            if removed:
                lines.append(Markup('Xoá %s') % self._format_eligible_names(
                    removed, 'sinh viên khỏi danh sách đủ điều kiện'))
            if lines:
                term.message_post(body=Markup('<br/>').join(lines))

    @api.model
    def _format_eligible_names(self, partners, suffix):
        shown = partners[:ELIGIBLE_LOG_NAMES_LIMIT]
        names = ', '.join(shown.mapped('name'))
        extra = len(partners) - len(shown)
        if extra > 0:
            names = '%s và %s người khác' % (names, extra)
        return Markup('%s %s: <b>%s</b>.') % (len(partners), suffix, names)

    def _cleanup_removed_eligible_students(self, old_eligible_by_term):
        """Bớt 1 SV khỏi 'Sinh viên đủ điều kiện' (VD: lỡ thêm nhầm) — hồ sơ
        đăng ký 'Chưa có GVHD' đã tự tạo cho họ trước đó (bởi
        _sync_eligible_student_registrations) sẽ thành mồ côi nếu không dọn,
        vẫn đếm vào 'Chưa có GVHD' dù không còn trong danh sách. Chỉ tự xoá
        khi hồ sơ chưa có gì thật sự (draft/unassigned) — SV lỡ đã nộp
        nguyện vọng hoặc đã được duyệt thì giữ nguyên, không tự mất dữ liệu."""
        Registration = self.env['eaut_showcase.advisor.registration']
        for term in self:
            removed = old_eligible_by_term.get(term.id, self.env['res.partner']) - term.eligible_student_ids
            if not removed:
                continue
            orphaned = Registration.search([
                ('term_id', '=', term.id),
                ('student_id', 'in', removed.ids),
                ('state', 'in', ('draft', 'unassigned')),
            ])
            orphaned.unlink()

    def _sync_eligible_student_registrations(self):
        """Thêm 1 SV vào 'Sinh viên đủ điều kiện' → tạo ngay 1 hồ sơ đăng ký
        ở trạng thái "Chưa có GVHD" cho họ (nếu chưa có) — để họ được tính
        vào số đếm và xuất hiện sẵn trên Kanban phân bổ, kể cả khi họ chưa
        từng tự đăng nhập nộp nguyện vọng. Nếu sau đó SV tự nộp thật, hệ
        thống dùng lại đúng bản ghi này (action_cart_add/action_submit_cart
        chỉ cần state == 'draft', không quan tâm state ban đầu là gì)."""
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

    def action_lock(self):
        """Chốt danh sách giảng viên — từ đây action_withdraw() tự chặn (nó
        chỉ cho rút khi term.state == 'open'), không cần thêm điều kiện gì
        ở đó. SV cũng không nộp mới được vì _get_open_term() chỉ tìm state
        == 'open'. Web công khai vẫn hiện GV — chỉ 'closed' mới ẩn."""
        self.write({'state': 'locked'})

    def action_set_draft(self):
        self.write({'state': 'draft'})

    def action_close(self):
        self.ensure_one()
        unassigned = self.unassigned_count

        if unassigned:

            warning = self.env['eaut_showcase.term.close.warning'].create({
                'term_id': self.id,
                'message': (
                               'Kỳ này vẫn còn %s sinh viên chưa được gán giảng viên '
                               'hướng dẫn. Bạn có chắc muốn đóng kỳ không? Vào "Phân '
                               'bổ GVHD" để gán tay trước nếu cần.'
                           ) % unassigned,
            })
            return {
                'type': 'ir.actions.act_window',
                'name': 'Đóng kỳ',
                'res_model': 'eaut_showcase.term.close.warning',
                'view_mode': 'form',
                'res_id': warning.id,
                'view_id': self.env.ref(
                    'eaut_showcase.view_eaut_showcase_term_close_warning_form').id,
                'target': 'new',

            }
        self.write({'state': 'closed'})
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

    # def action_assign_creators_kanban(self):
    #     """Mở thẳng Kanban kéo-thả giảng viên vào kỳ, thay vì phải "Thêm một
    #     dòng" + tìm tên từng giảng viên trong tab capacity_ids."""
    #     self.ensure_one()
    #     return self.env['ir.actions.act_window']._for_xml_id(
    #         'eaut_showcase.action_eaut_showcase_creator_kanban'
    #     )
    def action_view_eligible_students(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sinh viên đủ điều kiện',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.eligible_student_ids.ids)],
        }