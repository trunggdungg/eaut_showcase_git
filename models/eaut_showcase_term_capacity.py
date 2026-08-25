# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ADVISOR_REQUEST_ACTIVITY_XMLID = 'eaut_showcase.mail_activity_type_advisor_request'

class ShowcaseTermCapacity(models.Model):
    _name = 'eaut_showcase.term.capacity'
    _description = 'Sức chứa nhận hướng dẫn của giảng viên theo từng kỳ'
    _order = 'term_id, creator_id'
    _rec_name = 'creator_id'

    term_id = fields.Many2one(
        'eaut_showcase.term', string='Kỳ đồ án', required=True, ondelete='cascade',
    )
    creator_id = fields.Many2one(
        'eaut_showcase.creator', string='Giảng viên', required=True,
    )
    max_students = fields.Integer(string='Số sinh viên tối đa', default=1, required=True)
    withdrawn = fields.Boolean(string='Đã rút khỏi kỳ')
    pending_action = fields.Selection([
        ('none', 'Không có'),
        ('join', 'Chờ duyệt tham gia'),
        ('withdraw', 'Chờ duyệt rút'),
        ('update', 'Chờ duyệt đổi số lượng'),
    ], string='Yêu cầu đang chờ', default='none', required=True,
        help="GV tự đăng ký tham gia/rút/đổi số lượng qua Portal chỉ tạo ra "
             "yêu cầu ở đây — phải Admin duyệt "
             "mới thật sự có hiệu lực, tránh GV tự do thay đổi tuỳ ý. Sửa "
             "trực tiếp 'Số sinh viên tối đa' ở backend (form/list) thì "
             "không cần duyệt — chỉ áp dụng cho GV tự sửa qua Portal.")
    pending_max_students = fields.Integer(
        string='Số SV tối đa (yêu cầu mới)',
        help="Giá trị GV muốn đổi 'Số sinh viên tối đa' thành — chỉ có ý "
             "nghĩa khi pending_action = 'update', chưa áp dụng cho tới khi "
             "Admin duyệt.")

    approved_count = fields.Integer(string='Đã duyệt', compute='_compute_counts')
    pending_count = fields.Integer(string='Đang chờ duyệt', compute='_compute_counts')
    remaining_slots = fields.Integer(string='Còn trống', compute='_compute_counts')

    _term_creator_uniq = models.Constraint(
        'unique(term_id, creator_id)',
        'Giảng viên này đã có khai báo sức chứa trong kỳ này rồi.',
    )

    # Đếm chéo model advisor.registration.line — không có field liên kết trực
    # tiếp để dùng @api.depends chuẩn, nên chỉ khai depends trên field của
    # chính record này. LƯU Ý: giá trị chỉ chắc chắn mới ở request/cron MỚI
    # (env/cache mới) — trong CÙNG 1 transaction, nếu record capacity này đã
    # được đọc rồi (giá trị vào cache), 1 write() sau đó lên
    # advisor.registration.line KHÔNG làm cache này bị invalidate (không có
    # field liên kết để Odoo biết mà làm mới). Chỗ dùng field này để quyết
    # định có còn chỗ hay không (eaut_showcase_advisor_registration.py) vì
    # vậy KHÔNG đọc remaining_slots ở đây — mà khoá row rồi search_count()
    # trực tiếp; chỉ dùng field này cho mục đích hiển thị (đọc-thôi) là an toàn.
    @api.depends('term_id', 'creator_id')
    def _compute_counts(self):
        Line = self.env['eaut_showcase.advisor.registration.line']
        for capacity in self:
            approved = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', '=', 'approved'),
            ])
            pending = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', '=', 'pending'),
            ])
            capacity.approved_count = approved
            capacity.pending_count = pending
            capacity.remaining_slots = capacity.max_students - approved - pending

    @api.constrains('max_students')
    def _check_max_students(self):
        for capacity in self:
            capacity._check_new_max_students(capacity.max_students)

    def _check_new_max_students(self, max_students):
        """Dùng chung cho _check_max_students (khi ghi trực tiếp) và cho lúc
        GV gửi/Admin duyệt yêu cầu đổi số lượng qua Portal (khi đó giá trị
        mới nằm ở pending_max_students, chưa ghi vào max_students nên
        constrains không tự bắt được)."""
        self.ensure_one()
        approved = self.env['eaut_showcase.advisor.registration.line'].search_count([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
            ('state', '=', 'approved'),
        ])
        if max_students < approved:
            raise ValidationError(
                'Không thể đặt "Số sinh viên tối đa" (%s) thấp hơn số sinh viên đã '
                'duyệt hiện có (%s) của giảng viên "%s" trong kỳ "%s". Dùng nút "Bỏ '
                'gán" cho SV thừa trước, hoặc giữ nguyên số lớn hơn/bằng %s.'
                % (max_students, approved, self.creator_id.name, self.term_id.name, approved)
            )

    def unlink(self):
        Line = self.env['eaut_showcase.advisor.registration.line']
        for capacity in self:
            count = Line.search_count([
                ('term_id', '=', capacity.term_id.id),
                ('creator_id', '=', capacity.creator_id.id),
                ('state', 'in', ('approved', 'pending')),
            ])
            if count:
                raise UserError(
                    'Không thể xoá — giảng viên "%s" đang có %s sinh viên đã duyệt/đang '
                    'chờ trong kỳ "%s". Dùng nút "Rút khỏi kỳ" để xử lý đúng quy trình '
                    '(sinh viên sẽ được reset để chọn lại) thay vì xoá trực tiếp, tránh '
                    'mất dấu vết dữ liệu.' % (capacity.creator_id.name, count, capacity.term_id.name)
                )
        return super().unlink()

    def _get_admin_users(self):
        """Lấy danh sách user thuộc nhóm Admin (base.group_system) — dò field
        many2many còn tồn tại trên res.groups thay vì hard-code 1 tên cụ
        thể, vì tên field này đã đổi giữa các bản Odoo (users/user_ids/...).
        Không tìm được field nào phù hợp thì trả rỗng, không raise lỗi —
        tính năng nhắc Admin là phụ, không được làm hỏng thao tác chính
        (gửi/duyệt yêu cầu) của GV/Admin."""
        group_system = self.env.ref('base.group_system', raise_if_not_found=False)
        if not group_system:
            return self.env['res.users']
        for fname in ('user_ids', 'users', 'all_user_ids'):
            if fname in group_system._fields:
                return group_system[fname]
        return self.env['res.users']

    def _sync_admin_activity(self):
        """Gọi _do_sync_admin_activity() nhưng nuốt mọi lỗi phát sinh — đây
               chỉ là tính năng phụ (nhắc Admin), lỗi ở đây (VD: field của
               mail.activity/res.groups đổi tên giữa các bản Odoo) không được phép
               làm hỏng thao tác chính (gửi/duyệt yêu cầu) của GV/Admin."""
        try:
            self._do_sync_admin_activity()
        except Exception:
            _logger.warning(
                'Không tạo/cập nhật được hoạt động nhắc Admin cho yêu cầu GV — '
                'bỏ qua, không ảnh hưởng thao tác chính.', exc_info=True)

    def _do_sync_admin_activity(self):
        """Đồng bộ hoạt động nhắc Admin (chuông "Hoạt động" hiện ở mọi trang
        trong Odoo, không cần mở đúng menu mới thấy) trên record Kỳ tương
        ứng — còn yêu cầu GV nào đang chờ duyệt thì tạo/giữ hoạt động (1 cái
        cho mỗi Admin), hết yêu cầu thì tự đánh dấu hoàn thành. Gọi lại mỗi
        khi pending_action của 1 dòng capacity thay đổi (gửi/huỷ/duyệt/từ
        chối) để chuông luôn đúng thực tế."""
        activity_type = self.env.ref(ADVISOR_REQUEST_ACTIVITY_XMLID, raise_if_not_found=False)
        if not activity_type:
            return
        admins = self._get_admin_users()
        if not admins:
            return
        for term in self.mapped('term_id'):
            pending = term.capacity_ids.filtered(lambda c: c.pending_action != 'none')
            open_activities = term.activity_ids.filtered(
                lambda a: a.activity_type_id == activity_type)
            if not pending:
                for act in open_activities:
                    act.action_feedback(feedback='Đã xử lý hết yêu cầu đang chờ.')
                continue
            summary = 'Có %s yêu cầu từ giảng viên đang chờ duyệt' % len(pending)
            already_notified = open_activities.mapped('user_id')
            for admin in admins:
                if admin in already_notified:
                    open_activities.filtered(lambda a: a.user_id == admin).write({'summary': summary})
                else:
                    term.activity_schedule(
                        act_type_xmlid=ADVISOR_REQUEST_ACTIVITY_XMLID,
                        summary=summary,
                        note='Vào tab "Giảng viên nhận hướng dẫn" để duyệt/từ chối.',
                        user_id=admin.id,
                    )


    def action_withdraw(self):
        """Rút thật — chỉ nên gọi bởi Admin (form/list backend) hoặc bởi
               action_admin_approve_request() khi duyệt yêu cầu của GV, không phải
               chỗ GV tự bấm trực tiếp (xem action_gv_request_withdraw)."""
        self.ensure_one()
        if self.term_id.state != 'open':
            raise UserError('Chỉ có thể rút khỏi kỳ trong lúc kỳ còn đang mở đăng ký.')
        self.withdrawn = True
        affected_lines = self.env['eaut_showcase.advisor.registration.line'].search([
            ('term_id', '=', self.term_id.id),
            ('creator_id', '=', self.creator_id.id),
            ('state', 'in', ['pending', 'approved']),
        ])
        affected_lines.registration_id.action_reset_for_withdrawal(creator=self.creator_id)

    def action_gv_request_join(self, max_students):
        """GV tự bấm 'Đăng ký lại' trên Portal (đã có record capacity từ
        trước, đang withdrawn=True) — chỉ tạo yêu cầu chờ Admin duyệt, KHÔNG
        active ngay."""
        self.ensure_one()
        if self.pending_action != 'none':
            raise UserError('Bạn đang có 1 yêu cầu chờ Admin duyệt cho kỳ này rồi.')
        if max_students < 1:
            raise UserError('Số sinh viên tối đa phải lớn hơn 0.')
        self.write({'max_students': max_students, 'pending_action': 'join'})
        self._sync_admin_activity()

    @api.model
    def create_join_request(self, term, creator, max_students):
        """GV tự bấm 'Đăng ký nhận hướng dẫn' lần đầu trên Portal (chưa từng
        có record capacity ở kỳ này) — tạo mới ở trạng thái chờ Admin duyệt,
        KHÔNG active ngay."""
        if max_students < 1:
            raise UserError('Số sinh viên tối đa phải lớn hơn 0.')
        capacity = self.create({
            'term_id': term.id, 'creator_id': creator.id, 'max_students': max_students,
            'withdrawn': True, 'pending_action': 'join',
        })
        capacity._sync_admin_activity()
        return capacity

    def action_gv_request_withdraw(self):
        """GV tự bấm 'Rút khỏi kỳ' trên Portal — chỉ tạo yêu cầu chờ Admin
        duyệt, KHÔNG rút ngay. Trong lúc chờ, GV vẫn hoạt động bình thường
        (vẫn hiện công khai, SV vẫn chọn được) — chỉ khi Admin duyệt mới
        thật sự rút (action_withdraw)."""
        self.ensure_one()
        if self.term_id.state != 'open':
            raise UserError('Chỉ có thể gửi yêu cầu rút trong lúc kỳ còn đang mở đăng ký.')
        if self.pending_action != 'none':
            raise UserError('Bạn đang có 1 yêu cầu chờ Admin duyệt cho kỳ này rồi.')
        self.pending_action = 'withdraw'
        self._sync_admin_activity()

    def action_gv_request_update(self, max_students):
        """GV tự bấm 'Cập nhật' số lượng nhận hướng dẫn trên Portal — chỉ tạo
        yêu cầu chờ Admin duyệt, KHÔNG áp dụng ngay. max_students hiện tại
        vẫn giữ nguyên cho tới khi Admin duyệt (action_admin_approve_request)."""
        self.ensure_one()
        if self.term_id.state != 'open':
            raise UserError('Chỉ có thể gửi yêu cầu đổi số lượng trong lúc kỳ còn đang mở đăng ký.')
        if self.withdrawn:
            raise UserError('Bạn đã rút khỏi kỳ này — cần đăng ký tham gia lại trước.')
        if self.pending_action != 'none':
            raise UserError('Bạn đang có 1 yêu cầu chờ Admin duyệt cho kỳ này rồi.')
        if max_students < 1:
            raise UserError('Số sinh viên tối đa phải lớn hơn 0.')
        self._check_new_max_students(max_students)
        self.write({'pending_action': 'update', 'pending_max_students': max_students})
        self._sync_admin_activity()

    def action_gv_cancel_request(self):
        """GV tự huỷ yêu cầu tham gia/rút/đổi số lượng do chính mình gửi,
        trước khi Admin kịp xử lý — không cần Admin can thiệp cho việc rút
        lại ý định của chính GV."""
        self.ensure_one()
        if self.pending_action == 'none':
            raise UserError('Hiện không có yêu cầu nào đang chờ duyệt.')
        self.write({'pending_action': 'none', 'pending_max_students': 0})
        self._sync_admin_activity()

    def action_admin_approve_request(self):
        self.ensure_one()
        if self.pending_action == 'join':
            self.write({'withdrawn': False, 'pending_action': 'none'})
        elif self.pending_action == 'withdraw':
            self.action_withdraw()
            self.pending_action = 'none'
        elif self.pending_action == 'update':
            # Đếm lại ngay lúc duyệt (không chỉ tin số đã kiểm tra lúc GV gửi
            # yêu cầu) — phòng trường hợp có thêm SV được duyệt trong lúc
            # yêu cầu này đang chờ xử lý.
            self._check_new_max_students(self.pending_max_students)
            self.write({
                'max_students': self.pending_max_students,
                'pending_action': 'none', 'pending_max_students': 0,
            })
        else:
            raise UserError('Hiện không có yêu cầu nào đang chờ duyệt.')
        self._sync_admin_activity()

    def action_admin_reject_request(self):
        self.ensure_one()
        if self.pending_action == 'none':
            raise UserError('Hiện không có yêu cầu nào đang chờ duyệt.')
        self.write({'pending_action': 'none', 'pending_max_students': 0})
        self._sync_admin_activity()