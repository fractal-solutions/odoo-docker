from odoo import models, fields


class AppDrawerItem(models.Model):
    _name = "app_drawer.item"
    _description = "App Drawer Item"

    name = fields.Char(required=True)
