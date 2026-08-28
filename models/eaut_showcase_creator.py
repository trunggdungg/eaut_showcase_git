# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ShowcaseCreator(models.Model):
    _name = 'eaut_showcase.creator'
    _description = 'Tác giả / nhóm thực hiện sản phẩm'
    _order = 'name'

    name = fields.Char(string='Tên tác giả', required=True)
    avatar = fields.Image(string='Ảnh đại diện', max_width=512, max_height=512)
    role = fields.Char(string='Vai trò', default='Tác giả sản phẩm')
    bio = fields.Html(string='Giới thiệu', sanitize=True)
    suggested_topics = fields.Html(
        string='Đề tài gợi ý', sanitize=True,
        help="GV tự viết sẵn 1 vài đề tài dự kiến để SV tham khảo trước khi "
             "chọn làm nguyện vọng — hiển thị công khai trên trang chi tiết "
             "giảng viên.",
    )
    location_id = fields.Many2one(
        'res.country.state', string='Địa điểm',
        domain="[('country_id.code', '=', 'VN')]",
    )
    email = fields.Char(string='Email liên hệ')
    website_url = fields.Char(string='Website / mạng xã hội')
    user_id = fields.Many2one(
        'res.users', string='Tài khoản Portal',
        help="Tài khoản Portal giảng viên dùng để đăng nhập và duyệt yêu cầu "
             "hướng dẫn đồ án ở trang /my/advisor-requests.",
    )
    category_ids = fields.Many2many(
        'eaut_showcase.category', string='Lĩnh vực',
        help="Dùng để lọc giảng viên theo lĩnh vực ở trang chọn giảng viên "
             "hướng dẫn đồ án — dùng chung danh mục với dự án Showcase.",
    )
    department_id = fields.Many2one(
        'eaut_showcase.department', string='Khoa',
        help="Khoa quản lý giảng viên này — chỉ dùng để lọc trên trang công "
             "khai, không giới hạn sinh viên khoa khác chọn giảng viên này. "
             "Do Admin gán ở đây, giảng viên không tự sửa được qua Portal.",
    )
    project_ids = fields.Many2many(
        'eaut_showcase.project', 'eaut_showcase_project_creator_rel',
        'creator_id', 'project_id', string='Dự án đã đăng',
    )
    project_count = fields.Integer(
        string='Số dự án đã đăng', compute='_compute_project_count', store=True,
    )

    capacity_ids = fields.One2many(
        'eaut_showcase.term.capacity', 'creator_id', string='Sức chứa theo kỳ',
    )

    @api.model_create_multi
    def create(self, vals_list):
        name_by_email = {}
        for vals in vals_list:
            self._check_email_conflict(
                vals.get('email'), vals.get('name'),
                ignore_user_id=vals.get('user_id'),
            )
            email = (vals.get('email') or '').strip()
            name = (vals.get('name') or '').strip()
            if not email:
                continue
            prev_name = name_by_email.get(email)
            if prev_name is not None:
                # Không cần so tên nữa — kể cả 2 dòng trùng cả email lẫn
                # tên (copy nhầm 1 dòng) cũng phải chặn, vì mỗi Tác giả cần
                # 1 email liên hệ riêng.
                raise UserError(
                    'File import có nhiều dòng cùng Email liên hệ "%s" (dòng tên "%s" và dòng '
                    'tên "%s") — mỗi Tác giả cần 1 email liên hệ riêng, vui lòng kiểm tra lại '
                    'trước khi import.' % (email, prev_name, name)
                )
            name_by_email.setdefault(email, name)
        return super().create(vals_list)

    def write(self, vals):
        self._sync_name_from_user_vals(vals)
        changed_fields = [f for f in ('name', 'email') if f in vals]
        if self.env.context.get('showcase_skip_reverse_sync'):
            return super().write(vals)
        if 'email' in changed_fields:
            for creator in self:
                self._check_email_conflict(
                    vals.get('email'), vals.get('name', creator.name),
                    ignore_creator_id=creator.id,
                    ignore_user_id=creator.user_id.id,
                )
        result = super().write(vals)
        if changed_fields:
            self._sync_account_from_creator(changed_fields)
        return result


    @api.model
    def _sync_name_from_user_vals(self, vals):
        """Gán/đổi 'Tài khoản Portal' (user_id) cho 1 Creator thì đồng bộ luôn
        'Tên tác giả' theo đúng tên tài khoản đó (res.users -> partner_id.name)
        — tránh tình trạng tên hiển thị công khai/portal (creator.name) lệch
        với tên GV thấy khi tự đăng nhập, vì trước đây 2 field này không liên
        quan gì nhau, Admin gán tay user_id là dễ bị lệch ngay. Creator không
        gắn tài khoản (tác giả dự án không có đăng nhập) thì không bị ảnh
        hưởng — vẫn tự đặt tên tự do như trước."""
        user_id = vals.get('user_id')
        if not user_id:
            return
        partner_name = self.env['res.users'].browse(user_id).partner_id.name
        if partner_name:
            vals['name'] = partner_name

    @api.model
    def _check_email_conflict(self, email, name, ignore_creator_id=None, ignore_user_id=None):
        """Chặn TRƯỚC khi ghi (gọi ở create()/write(), trước super()) nếu
          Email liên hệ trùng với 1 tài khoản/Tác giả KHÁC đã có sẵn trong hệ
        thống — trùng với 1 Tác giả khác thì luôn chặn (kể cả trùng tên,
        vì mỗi Tác giả phải có 1 email liêng hệ riêng); trùng với 1 Liên hệ
        (res.partner) thường không phải lỗi — action_create_portal_user() cố
        ý tái sử dụng đúng Liên hệ đó khi tên khớp — nên chỉ chặn khi tên
        lại khác nhau (dấu hiệu gõ nhầm email hoặc nhầm người). Trước đây
        chỉ action_create_portal_user() kiểm tra việc này — và chỉ khi Admin
        bấm nút "Tạo tài khoản người dùng"; nếu Admin chỉ gõ trùng email rồi
        Lưu (không bấm nút) thì không có gì chặn cả, dễ tạo ra 2 bản ghi
        khác tên cùng 1 email, hoặc sau này bấm nút cấp Portal sẽ âm thầm
        "chiếm" nhầm Liên hệ của người khác. Phải kiểm tra TRƯỚC khi ghi,
        không dùng @api.constrains, vì Odoo không tự rollback khi controller
        bắt UserError rồi redirect bình thường."""
        if not email:
            return
        email = email.strip()
        if not email:
            return
        name = (name or '').strip()

        other_user = self.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if other_user and other_user.id != ignore_user_id:
            raise UserError(
                'Email "%s" đã là tên đăng nhập của tài khoản "%s" trong hệ thống — không '
                'thể dùng email này, trừ khi vào field "Tài khoản Portal" để chọn đúng tài '
                'khoản đó thay vì nhập trùng.' % (email, other_user.name)
            )

        ignore_partner_id = False
        if ignore_user_id:
            ignore_partner_id = self.env['res.users'].sudo().browse(ignore_user_id).partner_id.id
        partner = self.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        if partner and partner.id != ignore_partner_id \
                and name and partner.name and partner.name.strip() != name:
            raise UserError(
                'Email "%s" đã được dùng bởi Liên hệ "%s" trong hệ thống (khác với tên "%s" '
                'vừa nhập) — vui lòng kiểm tra lại, có thể email bị gõ nhầm hoặc đây là cùng '
                '1 người nhưng tên chưa thống nhất.' % (email, partner.name, name)
            )

        domain = [('email', '=', email)]
        if ignore_creator_id:
            domain.append(('id', '!=', ignore_creator_id))
        dup_creator = self.sudo().search(domain, limit=1)
        if dup_creator:
            # Không cần so tên nữa — mỗi Tác giả phải có 1 email liên hệ
            # riêng, kể cả khi trùng tên (2 người trùng tên) hay trùng cả
            # tên (nhập lặp/sao chép nhầm 1 Tác giả) đều là dữ liệu sai.
            raise UserError(
                'Email "%s" đã được dùng cho Tác giả khác ("%s") trong hệ thống — mỗi Tác giả '
                'cần 1 email liên hệ riêng, vui lòng kiểm tra lại.' % (email, dup_creator.name)
            )
    def _sync_account_from_creator(self, changed_fields):
        """Chiều ngược lại của _sync_name_from_user_vals(): GV tự sửa 'Tên
        hiển thị'/'Email liên hệ' trên Portal (my_advisor_lecturer_profile_save)
            thì ghi luôn giá trị mới vào res.partner + res.users.login của tài
        khoản Odoo đang gắn (user_id) — hệ thống dùng email làm tên đăng
        nhập nên email liên hệ và login luôn phải là 1. Trùng login đã được
       chặn từ trước ở _check_email_conflict(), gọi trước super().write()."""
        for creator in self:
            if not creator.user_id:
                continue
            partner = creator.user_id.partner_id
            partner_vals = {}
            if 'name' in changed_fields and creator.name and partner.name != creator.name:
                partner_vals['name'] = creator.name
            if 'email' in changed_fields and creator.email and partner.email != creator.email:
                partner_vals['email'] = creator.email
            if partner_vals:
                partner.write(partner_vals)
            if 'email' in changed_fields and creator.email \
                    and creator.user_id.login != creator.email:
                creator.user_id.write({'login': creator.email})

    def get_open_capacity_for_partner(self, partner):
        """Tìm đúng sức chứa (chưa rút) của GV này ở đúng kỳ đang mở mà
        `partner` đủ điều kiện — dùng cho trang chi tiết GV công khai để
        quyết định có hiện nút "Chọn làm giảng viên hướng dẫn" hay không.
        Khi có nhiều kỳ mở song song (nhiều khoa), không được chỉ lấy đại 1
        kỳ mở mới nhất chung cho mọi người — mỗi kỳ BẮT BUỘC phải khai danh
        sách 'Sinh viên đủ điều kiện' riêng (để trống = chưa ai đăng ký
        được, xem eaut_showcase_term.py), và GV có thể chỉ tham gia 1 trong
        số các kỳ đó. Phải khớp đúng luật với _get_open_term() ở
        controllers/eaut_showcase_portal.py — nếu không, SV có thể thấy nút
        "Chọn làm GVHD" ở đây nhưng bấm vào lại bị portal chặn."""
        self.ensure_one()
        terms = self.env['eaut_showcase.term'].sudo().search(
            [('state', '=', 'open')], order='date_start desc')
        for term in terms:
            if partner not in term.eligible_student_ids:
                continue
            capacity = self.env['eaut_showcase.term.capacity'].sudo().search([
                ('term_id', '=', term.id), ('creator_id', '=', self.id),
                ('withdrawn', '=', False),
            ], limit=1)
            if capacity:
                return capacity
        return self.env['eaut_showcase.term.capacity']

    kanban_term_id = fields.Many2one(
        'eaut_showcase.term', string='Kỳ đồ án',
        compute='_compute_kanban_term_id', inverse='_inverse_kanban_term_id', store=True,
        group_expand='_group_expand_kanban_terms',
        help="Suy ra từ sức chứa (term.capacity) thật của giảng viên — kỳ còn "
             "hiệu lực (chưa rút) có ngày mở gần nhất. Kéo-thả trên Kanban "
             "'Phân bổ giảng viên theo kỳ' sẽ tự tạo sức chứa nếu chưa có; "
             "field này luôn phản ánh đúng dữ liệu dù thêm/sửa từ đâu (Kanban "
             "hay tab 'Giảng viên nhận hướng dẫn' trong form Kỳ).",
    )

    @api.depends('project_ids')
    def _compute_project_count(self):
        for creator in self:
            creator.project_count = len(creator.project_ids)

    @api.depends('capacity_ids.term_id', 'capacity_ids.withdrawn')
    def _compute_kanban_term_id(self):
        for creator in self:
            active = creator.capacity_ids.filtered(lambda c: not c.withdrawn)
            active = active.sorted(key=lambda c: c.term_id.date_start, reverse=True)
            creator.kanban_term_id = active[:1].term_id if active else False

    def _inverse_kanban_term_id(self):
        for creator in self:
            creator._assign_to_term(creator.kanban_term_id.id)

    @api.model
    def _group_expand_kanban_terms(self, terms, domain):
        # Luôn hiện đủ các kỳ draft/open làm cột, kể cả kỳ chưa có giảng
        # viên nào — nếu không, Kanban mặc định chỉ hiện cột cho giá trị đã
        # tồn tại, không có chỗ để kéo giảng viên vào 1 kỳ mới toanh.
        return self.env['eaut_showcase.term'].search(
            [('state', 'in', ('draft', 'open'))], order='date_start desc')

    def _assign_to_term(self, term_id):
        self.ensure_one()
        if not term_id:
            # self.with_context(creator_internal_write=True).write({'kanban_term_id': False})
            return
        Capacity = self.env['eaut_showcase.term.capacity']
        existing = Capacity.search([
            ('term_id', '=', term_id), ('creator_id', '=', self.id),
        ], limit=1)
        if not existing:
            Capacity.create({'term_id': term_id, 'creator_id': self.id, 'max_students': 1})
        # self.with_context(creator_internal_write=True).write({'kanban_term_id': term_id})
        elif existing.withdrawn:
            existing.write({'withdrawn': False, 'pending_action': 'none'})

    def action_view_projects(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_uikick_project'
        )
        action['domain'] = [('creator_ids', 'in', self.id)]
        return action

    def action_create_portal_user(self):
        """Tạo Liên hệ (nếu chưa có) và cấp quyền truy cập Portal cho đúng
           Liên hệ đó — đi qua đúng cơ chế "Grant Portal Access" chuẩn của Odoo
           (portal.wizard) thay vì tự tạo res.users tay, để dùng đúng mẫu email
           mời + luồng bảo mật (signup token) mà Odoo tự quản lý."""
        self.ensure_one()
        if self.user_id:
            raise UserError('Tác giả này đã có tài khoản Portal (%s) rồi.' % self.user_id.login)
        if not self.email:
            raise UserError('Vui lòng nhập Email liên hệ trước khi tạo tài khoản Portal.')

        email = self.email.strip()

        # Email đã là login của 1 tài khoản khác (Portal hay Internal) chưa?
        existing_user = self.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing_user:
            raise UserError(
                'Email này đã được dùng làm tài khoản đăng nhập (%s) — vào field "Tài '
                'khoản Portal" để chọn thủ công tài khoản đó thay vì tạo mới.' % existing_user.login
            )

        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', email)], limit=1)
        # Email đã được cấp quyền Portal cho 1 liên hệ khác chưa?
        if partner and partner.user_ids:
            raise UserError(
                'Email này đã được cấp quyền Portal cho liên hệ "%s" (đăng nhập: %s) rồi — '
                'không thể cấp trùng.' % (partner.name, partner.user_ids[0].login)
            )
        if not partner:
            partner = Partner.create({
                'name': self.name,
                'email': email,
                'company_type': 'person',
            })

        wizard = self.env['portal.wizard'].sudo().with_context(
            active_model='res.partner', active_ids=partner.ids,
        ).create({})
        wizard_user = wizard.user_ids.filtered(lambda u: u.partner_id == partner)
        if not wizard_user:
            raise UserError('Không thể khởi tạo yêu cầu cấp quyền Portal cho liên hệ này.')
        wizard_user.email = email
        wizard_user.action_grant_access()

        self.user_id = partner.user_ids[:1].id

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Đã cấp quyền Portal',
                'message': 'Email mời đăng nhập Portal đã được gửi tới %s.' % email,
                'type': 'success',
                'sticky': False,
            },
        }


class ResPartnerAdvisorSync(models.Model):
    """GV đổi tên/email qua trang chuẩn của Odoo (VD: '/my/account' — form
    địa chỉ Portal, hoặc Admin sửa trực tiếp Liên hệ ở backend) thì ghi
    thẳng vào res.partner, KHÔNG đi qua ShowcaseCreator.write() nên không tự
    đồng bộ ngược lại — bổ sung chiều còn thiếu này ở đây, đối xứng với
    ShowcaseCreator._sync_account_from_creator() (chiều Creator -> partner).
    Dùng context showcase_skip_reverse_sync để creator.write() không ghi
    ngược lại partner (vô nghĩa, giá trị đang bằng nhau) và không đụng tới
    login — đổi login là quyết định lớn hơn, chỉ nên xảy ra khi GV chủ động
    đổi email liên hệ ngay trên trang Hồ sơ giảng viên, không phải như 1
    tác dụng phụ của việc sửa Liên hệ ở nơi khác."""
    _inherit = 'res.partner'

    def write(self, vals):
        result = super().write(vals)
        if 'name' in vals or 'email' in vals:
            creators = self.env['eaut_showcase.creator'].sudo().search([
                ('user_id.partner_id', 'in', self.ids),
            ])
            for creator in creators:
                partner = creator.user_id.partner_id
                creator_vals = {}
                if 'name' in vals and partner.name and creator.name != partner.name:
                    creator_vals['name'] = partner.name
                if 'email' in vals and partner.email and creator.email != partner.email:
                    creator_vals['email'] = partner.email
                if creator_vals:
                    creator.with_context(showcase_skip_reverse_sync=True).write(creator_vals)
        return result