from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    autoproctor_client_id = fields.Char(
        string="AutoProctor Client ID",
        config_parameter="survey_auto_proctor.client_id",
        groups="base.group_system",
    )
    autoproctor_client_secret = fields.Char(
        string="AutoProctor Client Secret",
        config_parameter="survey_auto_proctor.client_secret",
        groups="base.group_system",
    )
