import hashlib
import hmac
import uuid
import base64
import requests
import json

from odoo import _, fields, models
from odoo.exceptions import UserError


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    autoproctor_enabled = fields.Boolean(
        related="survey_id.autoproctor_enabled",
        readonly=True,
    )
    autoproctor_attempt_id = fields.Char(
        string="AutoProctor Attempt ID",
        default=lambda self: uuid.uuid4().hex,
        readonly=True,
        copy=False,
        index=True,
    )
    autoproctor_state = fields.Selection(
        selection=[
            ("not_started", "Not Started"),
            ("ready", "Ready"),
            ("active", "Monitoring"),
            ("stopped", "Finalized"),
            ("error", "Error"),
        ],
        string="AutoProctor Status",
        default="not_started",
        readonly=True,
        copy=False,
        tracking=True,
    )
    autoproctor_started_at = fields.Datetime(
        string="Monitoring Started At",
        readonly=True,
        copy=False,
    )
    autoproctor_stopped_at = fields.Datetime(
        string="Monitoring Stopped At",
        readonly=True,
        copy=False,
    )
    autoproctor_last_error = fields.Text(
        string="Last AutoProctor Error",
        readonly=True,
        copy=False,
    )

    autoproctor_trust_score = fields.Float(
        readonly=True
    )

    autoproctor_test_attempt = fields.Json(readonly=True)

    autoproctor_report_json = fields.Json(
        string="AutoProctor Report JSON",
        copy=False,
        readonly=True,
    )

    # _autoproctor_attempt_id_unique = models.Constraint(
    #     "UNIQUE (autoproctor_attempt_id)",
    #     "The AutoProctor attempt ID must be unique.",
    # )

    def _get_autoproctor_credentials(self):
        self.ensure_one()
        parameters = self.env["ir.config_parameter"].sudo()
        client_id = parameters.get_param("survey_auto_proctor.client_id")
        client_secret = parameters.get_param(
            "survey_auto_proctor.client_secret"
        )
        if not client_id or not client_secret:
            raise UserError(
                _(
                    "AutoProctor credentials are not configured. "
                    "Configure them in General Settings before using proctoring."
                )
            )

        attempt_id = self.autoproctor_attempt_id
        if not attempt_id:
            attempt_id = uuid.uuid4().hex
            self.sudo().autoproctor_attempt_id = attempt_id
        if len(attempt_id) > 40:
            raise UserError(_("The AutoProctor attempt ID is invalid."))

        attempt_hash = hmac.new(
            client_secret.encode("utf-8"),
            attempt_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "clientId": client_id,
            "testAttemptId": attempt_id,
            "hashedTestAttemptId": attempt_hash,
        }

    def _register_autoproctor_event(self, event_name, error_message=None):
        self.ensure_one()
        if self.autoproctor_state == "stopped" and event_name != "monitoring_stopped":
            raise UserError(_("The AutoProctor session is already finalized."))
        if event_name in ("setup_completed", "monitoring_started") and self.state == "done":
            raise UserError(_("A completed survey attempt cannot start monitoring."))
        if event_name == "monitoring_stopped" and self.state != "done":
            raise UserError(
                _("Monitoring can be finalized only after the survey is completed.")
            )

        values_by_event = {
            "setup_completed": {
                "autoproctor_state": "ready",
                "autoproctor_last_error": False,
            },
            "monitoring_started": {
                "autoproctor_state": "active",
                "autoproctor_started_at": fields.Datetime.now(),
                "autoproctor_last_error": False,
            },
            "monitoring_stopped": {
                "autoproctor_state": "stopped",
                "autoproctor_stopped_at": fields.Datetime.now(),
                "autoproctor_last_error": False,
            },
            "error": {
                "autoproctor_state": "error",
                "autoproctor_last_error": (error_message or "Unknown error")[:2000],
            },
        }
        values = values_by_event.get(event_name)
        if not values:
            raise UserError(_("Unsupported AutoProctor event."))
        self.sudo().write(values)

    def action_open_autoproctor_report(self):
        self.ensure_one()
        if not self.survey_id.autoproctor_enabled:
            raise UserError(_("AutoProctor is not enabled for this survey."))
        if self.autoproctor_state != "stopped":
            raise UserError(
                _("The AutoProctor session has not been finalized yet.")
            )
        return {
            "type": "ir.actions.act_url",
            "name": _("AutoProctor Report"),
            "target": "new",
            "url": f"/survey/autoproctor/report/{self.id}",
        }

    def _compute_hashed_test_attempt_id(self, answer_token, client_secret,):
        signature = hmac.new(
            client_secret.encode("utf-8"),
            answer_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        return base64.b64encode(signature).decode("utf-8")

    def _get_autoproctor_report(self):
        self.ensure_one()

        # =====================================================
        # 1. اگر قبلاً دریافت شده، اصلاً API را صدا نزن
        # =====================================================

        if self.autoproctor_report_json:
            return self.autoproctor_report_json

        ICP = self.env["ir.config_parameter"].sudo()

        client_id = ICP.get_param(
            "survey_auto_proctor.client_id"
        )

        client_secret = ICP.get_param(
            "survey_auto_proctor.client_secret"
        )

        if not client_id or not client_secret:
            raise ValueError(
                "AutoProctor Client ID or Client Secret is not configured."
            )

        if not self.access_token:
            raise ValueError(
                "Survey answer token is missing."
            )

        # =====================================================
        # 2. ساخت hashedTestAttemptId
        # =====================================================

        hashed_test_attempt_id = (
            self._compute_hashed_test_attempt_id(
                self.access_token,
                client_secret,
            )
        )

        # =====================================================
        # 3. دریافت Report اصلی
        # =====================================================

        api_url = (
            "https://www.autoproctor.co"
            f"/api/v2/test-attempts/{self.access_token}/evidence-records-file-url/"
        )

        response = requests.get(
            api_url,
            params={
                "clientId": client_id,
                "hashed_test_attempt_id": hashed_test_attempt_id,
            },
            timeout=30,
        )

        response.raise_for_status()

        report = response.json()

        # =====================================================
        # 4. دریافت فایل Evidence JSON
        # =====================================================

        evidence_records = {}

        evidence_file_url = report.get(
            "all_evidence_records_file_url"
        )

        if evidence_file_url:

            evidence_response = requests.get(
                evidence_file_url,
                timeout=30,
            )

            evidence_response.raise_for_status()

            evidence_records = evidence_response.json()

        # =====================================================
        # 5. JSON نهایی
        # =====================================================

        final_report = {
            "report": report,
            "evidence_records": evidence_records,
        }

        # =====================================================
        # 6. ذخیره دائمی روی user_input
        # =====================================================

        self.write({
            "autoproctor_report_json": final_report,
        })
        self.env.cr.commit()
        return final_report

    def _get_autoproctor_score(self):
        self.ensure_one()
        
        if self.autoproctor_trust_score:
            return self.autoproctor_trust_score

        ICP = self.env["ir.config_parameter"].sudo()
        client_id = ICP.get_param("survey_auto_proctor.client_id")
        client_secret = ICP.get_param("survey_auto_proctor.client_secret")

        if not client_id or not client_secret:
            raise ValueError("AutoProctor Client ID or Client Secret is not configured.")

        if not self.access_token:
            raise ValueError("Survey answer token is missing.")

        hashed_test_attempt_id = (
            self._compute_hashed_test_attempt_id(self.access_token, client_secret,))

        api_url = ("https://www.autoproctor.co" f"/api/v2/test-attempts/{self.access_token}")
        response = requests.get(api_url, params={"clientId": client_id, "hashed_test_attempt_id": hashed_test_attempt_id,}, timeout=30,)
        response.raise_for_status()
        report = response.json()
        if report['status'] == 'success':
            
            self.write({
                "autoproctor_test_attempt" : report['test_attempt'],
                "autoproctor_trust_score": report['test_attempt']['trust_score']
            })
            return report['test_attempt']['trust_score']
        return 0



    def action_open_autoproctor_report(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Proctoring Report",
            "res_model": "survey.autoproctor.report.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": self.id,
                "active_model": self._name,
            },
        }