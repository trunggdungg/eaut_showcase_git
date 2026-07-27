import re

from odoo import fields, models, api

# Nhận diện link chia sẻ YouTube (youtu.be/..., youtube.com/watch?v=..., /embed/..., /shorts/...)
# để chuyển sang URL nhúng iframe — thẻ <video> không phát được các link này vì
# đó là trang xem video, không phải file/luồng media trực tiếp.
YOUTUBE_URL_RE = re.compile(
    r'(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|v/))'
    r'([A-Za-z0-9_-]{11})'
)


class UikickProject(models.Model):
    _name = 'eaut_showcase.project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'UIKick Crowdfunding Project'
    _rec_name = 'title'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    project_code = fields.Char(
        string='Project Code', required=True, index=True, copy=False, readonly=True,
        help="Stable slug used in the public URL /uikick/project/<project_code>. "
             "Tự động sinh khi tạo dự án mới.",)

    title = fields.Char(string='Title', required=True)
    subtitle = fields.Char(string='Phụ đề')
    creator_ids = fields.Many2many(
        'eaut_showcase.creator', 'eaut_showcase_project_creator_rel',
        'project_id', 'creator_id', string='Tác giả', required=True,
        help="Một hoặc nhiều tác giả/nhóm thực hiện sản phẩm này.",
    )
    creator_names = fields.Char(
        string='Tên tác giả (hiển thị)', compute='_compute_creator_names', store=True,
        help="Tên các tác giả nối bằng dấu phẩy, dùng để hiển thị trên trang web.",
    )
    category_id = fields.Many2one(
        'eaut_showcase.category', string='Danh mục', required=True, index=True,
    )
    location_id = fields.Many2one(
        'res.country.state', string='Địa điểm',
        domain="[('country_id.code', '=', 'VN')]",
        help="Tỉnh/thành phố — dữ liệu tỉnh/thành Việt Nam có sẵn trong Odoo.",
    )

    views = fields.Integer(string='View Count', default=0)
    image = fields.Image(string='Ảnh thumbnail', max_width=1920, max_height=1920)
    video_url = fields.Char(string='Video URL')
    video_file = fields.Binary(
        string='Video (upload)', attachment=True,
        help="Upload file video trực tiếp thay vì dán URL. Nếu có file ở đây thì "
             "luôn được ưu tiên phát thay cho Video URL.",
    )
    video_filename = fields.Char(string='Tên file video')
    video_embed_url = fields.Char(
        string='Video Embed URL', compute='_compute_video_embed_url',
        help="URL nhúng iframe khi video_url là link chia sẻ YouTube. Trống nếu "
             "có file video upload, hoặc video_url là file/luồng video phát "
             "trực tiếp được (mp4, m3u8...).",
    )
    video_play_src = fields.Char(
        string='Video Play Source', compute='_compute_video_embed_url',
        help="URL thực dùng cho thẻ <video>: ưu tiên file đã upload, nếu không "
             "có thì dùng video_url (khi video_url không phải link YouTube).",
    )
    video_thumbnail_url = fields.Char(
        string='Video Thumbnail URL (YouTube)', compute='_compute_video_embed_url',
        help="Ảnh thumbnail lấy tự động từ YouTube khi video_url là link YouTube. "
             "Chỉ dùng làm ảnh dự phòng khi trường Ảnh thumbnail chưa được chọn.",
    )
    video_preview_embed_url = fields.Char(
        string='Video Preview Embed URL (YouTube)', compute='_compute_video_embed_url',
        help="URL nhúng YouTube tự động phát/tắt tiếng/lặp lại, dùng cho preview "
             "khi hover vào card ở trang chủ.",
    )
    description = fields.Html(string='Mô tả giới thiệu', sanitize=True)
    status_id = fields.Many2one(
        'eaut_showcase.status', string='Trạng thái', required=True,
        default=lambda self: self.env['eaut_showcase.status'].search([], limit=1, order='sequence, id'),
    )
    campaign_number = fields.Integer(string='Campaign Number')
    active = fields.Boolean(default=True)
    interest_ids = fields.One2many('eaut_showcase.interest', 'project_id', string='Người quan tâm')
    interest_count = fields.Integer(
        string='Số lượt quan tâm', compute='_compute_interest_count', store=True,
    )

    @api.depends('interest_ids')
    def _compute_interest_count(self):
        for project in self:
            project.interest_count = len(project.interest_ids)

    @api.depends('creator_ids.name')
    def _compute_creator_names(self):
        for project in self:
            project.creator_names = ', '.join(project.creator_ids.mapped('name'))

    @api.depends('video_url', 'video_file', 'project_code')
    def _compute_video_embed_url(self):
        # Kiểm tra sự tồn tại của file qua ir.attachment thay vì đọc trực tiếp
        # project.video_file — tránh phải tải toàn bộ nội dung video (có thể
        # rất nặng) vào bộ nhớ chỉ để biết "có file hay không".
        has_file_ids = set(self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_field', '=', 'video_file'),
            ('res_id', 'in', self.ids),
        ]).mapped('res_id'))

        for project in self:
            # Có file upload -> luôn ưu tiên phát file đó, bỏ qua video_url hoàn toàn.
            if project.id in has_file_ids:
                project.video_embed_url = False
                project.video_thumbnail_url = False
                project.video_preview_embed_url = False
                project.video_play_src = '/uikick/project/%s/video' % (project.project_code or '')
                continue

            match = YOUTUBE_URL_RE.search(project.video_url or '')
            video_id = match.group(1) if match else False
            project.video_embed_url = (
                'https://www.youtube-nocookie.com/embed/%s' % video_id if video_id else False
            )
            project.video_thumbnail_url = (
                'https://img.youtube.com/vi/%s/hqdefault.jpg' % video_id if video_id else False
            )
            project.video_preview_embed_url = (
                'https://www.youtube-nocookie.com/embed/%s'
                '?autoplay=1&mute=1&loop=1&playlist=%s&controls=0&modestbranding=1&rel=0'
                '&playsinline=1&disablekb=1&fs=0&iv_load_policy=3&cc_load_policy=0'
                % (video_id, video_id) if video_id else False
            )
            project.video_play_src = project.video_url if not video_id else False

    def action_view_interests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_eaut_showcase_interest'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('project_code'):
                vals['project_code'] = self.env['ir.sequence'].next_by_code('eaut_showcase.project')
        return super().create(vals_list)

    _sql_constraints = [
        ('project_code_uniq', 'unique(project_code)', 'Project code must be unique.'),
    ]