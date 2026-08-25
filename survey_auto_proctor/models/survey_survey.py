from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SurveySurvey(models.Model):
    _inherit = "survey.survey"

    autoproctor_enabled = fields.Boolean(
        string="Enable AutoProctor",
        help="Require AutoProctor monitoring before participants can start this survey.",
    )
    autoproctor_audio = fields.Boolean(
        string="Background Noise Detection",
        default=True,
    )
    autoproctor_num_humans = fields.Boolean(
        string="Face Count Monitoring",
        default=True,
    )
    autoproctor_tab_switch = fields.Boolean(
        string="Tab and Window Switch Detection",
        default=True,
    )
    autoproctor_photos_at_random = fields.Boolean(
        string="Random Photo Capture",
        default=True,
    )
    autoproctor_configured = fields.Boolean(
        string="AutoProctor Configured",
        compute="_compute_autoproctor_configured",
    )

    stop_survey_with_autoproctor_report = fields.Boolean(
        string="Stop Survey With Autoproctor Report Score ?",
        default=False
    )
    stop_score = fields.Float(
        string="Stop When Score is Lower than",
        default=0.0
    )

    @api.depends_context("uid")
    def _compute_autoproctor_configured(self):
        parameters = self.env["ir.config_parameter"].sudo()
        configured = bool(
            parameters.get_param("survey_auto_proctor.client_id")
            and parameters.get_param("survey_auto_proctor.client_secret")
        )
        for survey in self:
            survey.autoproctor_configured = configured

    @api.constrains("autoproctor_enabled", "survey_type")
    def _check_autoproctor_survey_type(self):
        if any(
            survey.autoproctor_enabled and survey.survey_type == "live_session"
            for survey in self
        ):
            raise ValidationError(
                _("AutoProctor is not supported for Live Session surveys.")
            )

    def _get_autoproctor_tracking_options(self):
        self.ensure_one()
        return {
            "audio": self.autoproctor_audio,
            "numHumans": self.autoproctor_num_humans,
            "tabSwitch": self.autoproctor_tab_switch,
            "photosAtRandom": self.autoproctor_photos_at_random,
        }
