# -*- coding: utf-8 -*-
import base64
import csv
import io

from odoo import fields, models
from odoo.exceptions import UserError

EXPECTED_HEADERS = ['Họ tên', 'Email', 'MSSV', 'Lớp', 'Ngành']


class ShowcaseEligibleImportWizard(models.TransientModel):
    _name = 'eaut_showcase.eligible.import.wizard'
    _description = (
        'Nhập nhanh danh sách "Sinh viên đủ điều kiện" của 1 kỳ từ file CSV — '
        'khớp theo Email để cập nhật MSSV/Lớp/Ngành cho liên hệ đã có sẵn, hoặc '
        'tạo liên hệ mới nếu chưa có, rồi thêm tất cả vào danh sách của kỳ. '
        'KHÔNG tự cấp Portal access — Admin vẫn tự cấp tay như quy trình hiện tại.'
    )

    term_id = fields.Many2one('eaut_showcase.term', string='Kỳ đồ án', required=True)
    file = fields.Binary(string='File CSV')
    filename = fields.Char(string='Tên file')
    state = fields.Selection([
        ('upload', 'Chọn file'), ('done', 'Kết quả'),
    ], string='Trạng thái', default='upload', required=True)
    result_message = fields.Text(string='Kết quả', readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.file:
            raise UserError('Vui lòng chọn file trước khi nhập.')
        rows = self._parse_file()

        Partner = self.env['res.partner'].sudo()
        created = updated = 0
        skipped = []
        seen_emails = set()
        partners_to_add = Partner

        for line_no, row in enumerate(rows, start=2):  # dòng 1 là tiêu đề
            name = (row.get('Họ tên') or '').strip()
            email = (row.get('Email') or '').strip().lower()
            mssv = (row.get('MSSV') or '').strip()
            student_class = (row.get('Lớp') or '').strip()
            major = (row.get('Ngành') or '').strip()

            if not email:
                skipped.append('Dòng %s: thiếu Email, đã bỏ qua.' % line_no)
                continue
            if email in seen_emails:
                skipped.append('Dòng %s: email "%s" bị trùng trong file, đã bỏ qua.'
                                % (line_no, email))
                continue
            seen_emails.add(email)

            vals = {}
            if mssv:
                vals['showcase_student_code'] = mssv
            if student_class:
                vals['showcase_student_class'] = student_class
            if major:
                vals['showcase_student_major'] = major

            partner = Partner.search([('email', '=ilike', email)], limit=1)
            if partner:
                if name and not partner.name:
                    vals['name'] = name
                if vals:
                    partner.write(vals)
                updated += 1
            else:
                if not name:
                    skipped.append(
                        'Dòng %s (%s): chưa có liên hệ nào với email này và thiếu Họ tên '
                        'nên không tạo mới được, đã bỏ qua.' % (line_no, email))
                    continue
                vals.update({'name': name, 'email': email})
                partner = Partner.create(vals)
                created += 1
            partners_to_add |= partner

        newly_added = partners_to_add - self.term_id.eligible_student_ids
        if partners_to_add:
            self.term_id.write({
                'eligible_student_ids': [(4, partner.id) for partner in partners_to_add],
            })

        lines = [
            'Đã xử lý %s dòng hợp lệ trong file.' % (created + updated),
            '- Tạo liên hệ mới: %s' % created,
            '- Cập nhật liên hệ đã có (MSSV/Lớp/Ngành): %s' % updated,
            '- Thêm mới vào "Sinh viên đủ điều kiện": %s' % len(newly_added),
        ]
        if skipped:
            lines.append('')
            lines.append('Bỏ qua %s dòng:' % len(skipped))
            lines.extend(skipped)
        self.write({'state': 'done', 'result_message': '\n'.join(lines)})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_upload(self):
        self.ensure_one()
        self.write({'state': 'upload', 'result_message': False, 'file': False, 'filename': False})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _parse_file(self):
        """Đọc file CSV đã upload thành list dict theo tên cột — hỗ trợ cả
        dấu phẩy và chấm phẩy (Excel bản tiếng Việt hay xuất CSV bằng dấu
        chấm phẩy vì dấu phẩy đã dùng làm dấu thập phân) và vài encoding phổ
        biến. Chỉ bắt buộc cột "Email" — dùng làm khoá khớp với liên hệ đã
        có sẵn, các cột còn lại (Họ tên/MSSV/Lớp/Ngành) là tuỳ chọn."""
        self.ensure_one()
        raw = base64.b64decode(self.file)
        text = None
        for encoding in ('utf-8-sig', 'utf-8', 'cp1258'):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise UserError(
                'Không đọc được file — hãy lưu lại dưới dạng CSV UTF-8 '
                '(Excel: Save As > CSV UTF-8 (Comma delimited)).')

        try:
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise UserError('File trống hoặc không có dòng tiêu đề.')
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
        if 'Email' not in reader.fieldnames:
            raise UserError(
                'File thiếu cột bắt buộc "Email". Các cột hợp lệ: %s (chỉ "Email" là '
                'bắt buộc).' % ', '.join(EXPECTED_HEADERS))
        return list(reader)
