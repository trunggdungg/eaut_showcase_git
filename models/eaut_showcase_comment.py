from odoo import fields, models


class ShowcaseComment(models.Model):
    _name = 'eaut_showcase.comment'
    _description = 'Bình luận của khách trên trang chi tiết dự án'
    _order = 'create_date desc'
    _rec_name = 'name'

    project_id = fields.Many2one(
        'eaut_showcase.project', string='Dự án', required=True,
        ondelete='cascade', index=True,
    )
    name = fields.Char(string='Tên người bình luận', required=True)
    content = fields.Text(string='Nội dung', required=True)
    state = fields.Selection([
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái', default='pending', required=True)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})