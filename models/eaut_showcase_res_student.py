from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    showcase_student_code = fields.Char(string='Mã sinh viên (MSV)')
    showcase_student_class = fields.Char(string='Lớp')
    showcase_student_major = fields.Char(string='Ngành học')

    @api.constrains('showcase_student_code', 'email')
    def _check_showcase_student_unique(self):
        """Chỉ áp dụng cho các Liên hệ (res.partner) ĐANG được dùng làm Sinh
        viên trong Showcase — nhận diện qua có khai MSV (showcase_student_code),
        để không ảnh hưởng tới các Liên hệ thông thường khác (khách hàng, nhà
        cung cấp...) của res.partner vốn không cần theo các quy tắc này. Bắt
        MSV/Email duy nhất giữa các sinh viên với nhau + Email bắt buộc —
        tránh import/nhập tay bị trùng do gõ nhầm/copy nhầm dòng, rất khó
        phát hiện bằng mắt thường trong danh sách dài."""
        for partner in self:
            code = (partner.showcase_student_code or '').strip()
            if not code:
                continue
            email = (partner.email or '').strip()
            if not email:
                raise ValidationError(
                    'Sinh viên "%s" (MSV: %s) chưa có Email — Email là bắt buộc vì sinh '
                    'viên dùng email này để đăng nhập Portal.' % (partner.name, code))
            dup_code = self.search([
                ('id', '!=', partner.id),
                ('showcase_student_code', '=', code),
            ], limit=1)
            if dup_code:
                raise ValidationError(
                    'Mã sinh viên (MSV) "%s" đã được dùng cho sinh viên khác ("%s") trong '
                    'hệ thống — mỗi sinh viên cần 1 MSV riêng, vui lòng kiểm tra lại.' % (
                        code, dup_code.name))
            dup_email = self.search([
                ('id', '!=', partner.id),
                ('showcase_student_code', 'not in', (False, '')),
                ('email', '=', email),
            ], limit=1)
            if dup_email:
                raise ValidationError(
                    'Email "%s" đã được dùng cho sinh viên khác ("%s", MSV: %s) trong hệ '
                    'thống — mỗi sinh viên cần 1 email riêng, vui lòng kiểm tra lại.' % (
                        email, dup_email.name, dup_email.showcase_student_code))