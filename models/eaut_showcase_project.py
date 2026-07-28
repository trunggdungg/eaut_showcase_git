from odoo import fields, models, api
import re

YOUTUBE_URL_RE = re.compile(
    r'(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|v/))'
    r'([A-Za-z0-9_-]{11})'
)

class UikickProject(models.Model):
    _name = 'eaut_showcase.project'
    _description = 'UIKick Crowdfunding Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'title'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    project_code = fields.Char(
        string='Project Code', required=True, index=True, copy=False, readonly=True,tracking=True)

    title = fields.Char(string='Title', required=True,tracking=True)
    subtitle = fields.Char(string='Phụ đề',tracking=True)
    creator_ids = fields.Many2many(
        'eaut_showcase.creator', 'eaut_showcase_project_creator_rel',
        'project_id', 'creator_id', string='Tác giả', required=True,
        help="Một hoặc nhiều tác giả/nhóm thực hiện sản phẩm này.",
    )
    creator_names = fields.Char(
        string='Tên tác giả', compute='_compute_creator_names', store=True,
        help="Tên các tác giả nối bằng dấu phẩy, dùng để hiển thị trên trang web.",tracking=True,
    )
    category_id = fields.Many2one(
        'eaut_showcase.category', string='Danh mục', required=True, index=True,
    )
    location_id = fields.Many2one(
        'res.country.state', string='Địa điểm',
        domain="[('country_id.code', '=', 'VN')]",
        help="Tỉnh/thành phố — dữ liệu tỉnh/thành Việt Nam có sẵn trong Odoo.",tracking=True
    )

    views = fields.Integer(string='View Count', default=0)
    image = fields.Image(string='Ảnh thumbnail', max_width=1920, max_height=1920,tracking=True)
    video_url = fields.Char(string='Video URL',tracking=True)
    video_embed_url = fields.Char(
        string='Video Embed URL', compute='_compute_video_embed_url',
        help="URL nhúng iframe khi video_url là link chia sẻ YouTube. Trống nếu "
             "video_url là file/luồng video phát trực tiếp được (mp4, m3u8...).",tracking=True
    )
    video_thumbnail_url = fields.Char(
        string='Video Thumbnail URL', compute='_compute_video_embed_url',
        help="Ảnh thumbnail lấy tự động từ YouTube khi video_url là link YouTube. "
             "Chỉ dùng làm ảnh dự phòng khi trường Ảnh thumbnail chưa được chọn.",tracking=True
    )
    video_preview_embed_url = fields.Char(
        string='Video Preview Embed URL', compute='_compute_video_embed_url',
        help="URL nhúng YouTube tự động phát/tắt tiếng/lặp lại, dùng cho preview "
             "khi hover vào card ở trang chủ.",tracking=True
    )
    description = fields.Html(string='Mô tả giới thiệu', sanitize=True)
    status_id = fields.Many2one(
        'eaut_showcase.status', string='Trạng thái', required=True,
        default=lambda self: self.env['eaut_showcase.status'].search([], limit=1, order='sequence, id'),
    )
    campaign_number = fields.Integer(string='Campaign Number')
    active = fields.Boolean(default=True,tracking=True)
    interest_ids = fields.One2many('eaut_showcase.interest', 'project_id', string='Người quan tâm')
    interest_count = fields.Integer(
        string='Số lượt quan tâm', compute='_compute_interest_count', store=True,tracking=True
    )

    @api.depends('interest_ids')
    def _compute_interest_count(self):
        for project in self:
            project.interest_count = len(project.interest_ids)

    @api.depends('creator_ids.name')
    def _compute_creator_names(self):
        for project in self:
            project.creator_names = ', '.join(project.creator_ids.mapped('name'))

    @api.depends('video_url')
    def _compute_video_embed_url(self):
        for project in self:
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