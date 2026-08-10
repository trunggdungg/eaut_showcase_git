from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    showcase_student_code = fields.Char(string='Mã sinh viên (MSSV)')
    showcase_student_class = fields.Char(string='Lớp')
    showcase_student_major = fields.Char(string='Ngành học')