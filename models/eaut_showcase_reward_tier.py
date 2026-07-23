from odoo import fields, models


class UikickRewardTier(models.Model):
    _name = 'eaut_showcase.reward.tier'
    _description = 'UIKick Reward Tier'
    _rec_name = 'title'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    title = fields.Char(string='Title', required=True)
    amount = fields.Integer(string='Pledge Amount (US$)', required=True)
    description = fields.Text(string='Description')
    estimated = fields.Char(string='Estimated Delivery')
    backers = fields.Integer(string='Backers')
    limited = fields.Boolean(string='Limited Quantity')
    remaining = fields.Integer(string='Remaining Units')
    active = fields.Boolean(default=True)