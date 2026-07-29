from odoo import fields, models


class UikickFaq(models.Model):
    _name = 'eaut_showcase.faq'
    _description = 'Câu hỏi thường gặp (FAQ) của dự án'
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'eaut_showcase.project', string='Dự án', required=True,
        ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Thứ tự', default=10)
    question = fields.Char(string='Câu hỏi', required=True)
    answer = fields.Text(string='Câu trả lời', required=True)