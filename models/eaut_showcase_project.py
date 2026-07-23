from odoo import fields, models, api

class UikickProject(models.Model):
    _name = 'eaut_showcase.project'
    _description = 'UIKick Crowdfunding Project'
    _rec_name = 'title'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    project_code = fields.Char(
        string='Project Code', required=True, index=True, copy=False,
        help="Stable slug used in the public URL /uikick/project/<project_code>.",
    )
    title = fields.Char(string='Title', required=True)
    subtitle = fields.Char(string='Phụ đề')
    creator = fields.Char(string='Creator', required=True)
    category_id = fields.Many2one(
        'eaut_showcase.category', string='Danh mục', required=True, index=True,
    )
    location = fields.Char(string='Location')
    days_left = fields.Integer(string='Days Left')
    percent_funded = fields.Integer(string='Percent Funded')
    amount_raised = fields.Integer(string='Amount Raised (US$)')
    backers = fields.Integer(string='Backers')
    goal = fields.Integer(string='Goal (US$)')
    views = fields.Integer(string='View Count', default=0)
    image = fields.Char(string='Ảnh thumbnail (URL)')
    video_url = fields.Char(string='Video URL')
    description = fields.Html(string='Mô tả giới thiệu', sanitize=True)
    status_id = fields.Many2one(
        'eaut_showcase.status', string='Trạng thái', required=True,
        default=lambda self: self.env['eaut_showcase.status'].search([], limit=1, order='sequence, id'),
    )
    campaign_number = fields.Integer(string='Campaign Number')
    total_raised = fields.Char(string='Total Raised (all campaigns)')
    total_backers = fields.Char(string='Total Backers (all campaigns)')
    active = fields.Boolean(default=True)
    interest_ids = fields.One2many('eaut_showcase.interest', 'project_id', string='Người quan tâm')
    interest_count = fields.Integer(
        string='Số lượt quan tâm', compute='_compute_interest_count', store=True,
    )

    @api.depends('interest_ids')
    def _compute_interest_count(self):
        for project in self:
            project.interest_count = len(project.interest_ids)

    def action_view_interests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'eaut_showcase.action_eaut_showcase_interest'
        )
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action

    _sql_constraints = [
        ('project_code_uniq', 'unique(project_code)', 'Project code must be unique.'),
    ]