# -*- coding: utf-8 -*-
from odoo import fields, models


class ShowcaseTermCloseWarning(models.TransientModel):
    _name = 'eaut_showcase.term.close.warning'
    _description = 'Popup xác nhận đóng kỳ khi còn sinh viên chưa có GVHD'

    term_id = fields.Many2one('eaut_showcase.term', string='Kỳ đồ án', required=True)
    message = fields.Text(string='Thông báo', readonly=True)

    def action_confirm(self):
        self.ensure_one()
        self.term_id.write({'state': 'closed'})
        return {'type': 'ir.actions.act_window_close'}