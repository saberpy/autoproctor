import werkzeug
import base64
from odoo import _, http
from odoo.addons.survey.controllers.main import Survey
from odoo.exceptions import AccessError, UserError
from odoo.http import request
import requests


class SurveyAutoProctorController(Survey):
    def _get_autoproctor_answer(self, survey_token, answer_token):
        access_data = self._get_access_data(
            survey_token,
            answer_token,
            ensure_token=True,
        )
        if access_data["validity_code"] is not True:
            return request.env["survey.user_input"]

        survey_sudo = access_data["survey_sudo"]
        answer_sudo = access_data["answer_sudo"]
        if (
            not answer_sudo
            or not survey_sudo.autoproctor_enabled
            or answer_sudo.is_session_answer
        ):
            return request.env["survey.user_input"]
        return answer_sudo

    def _is_autoproctor_monitoring_active(self, survey_token, answer_token):
        answer_sudo = self._get_autoproctor_answer(survey_token, answer_token)
        return not answer_sudo or answer_sudo.autoproctor_state == "active"

    # @http.route()
    # def survey_begin(self, survey_token, answer_token, **post):
    #     if not self._is_autoproctor_monitoring_active(survey_token, answer_token):
    #         return {}, {"error": "autoproctor_required"}
    #     return super().survey_begin(survey_token, answer_token, **post)

    # @http.route()
    # def survey_submit(self, survey_token, answer_token, **post):
    #     if not self._is_autoproctor_monitoring_active(survey_token, answer_token):
    #         return {}, {"error": "autoproctor_required"}
    #     return super().survey_submit(survey_token, answer_token, **post)

    @http.route(
        "/survey/autoproctor/config/<string:survey_token>/<string:answer_token>",
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def autoproctor_config(self, survey_token, answer_token):
        answer_sudo = self._get_autoproctor_answer(survey_token, answer_token)
        if not answer_sudo:
            return {"ok": False, "error": _("AutoProctor access was denied.")}
        if answer_sudo.autoproctor_state == "stopped":
            return {
                "ok": False,
                "error": _("This AutoProctor session has already been finalized."),
            }

        try:
            credentials = answer_sudo._get_autoproctor_credentials()
        except UserError as error:
            return {"ok": False, "error": str(error)}

        return {
            "ok": True,
            "credentials": credentials,
            "proctoringOptions": {
                "trackingOptions": (
                    answer_sudo.survey_id._get_autoproctor_tracking_options()
                ),
            },
            "state": answer_sudo.autoproctor_state,
        }

    @http.route(
        "/survey/autoproctor/event/<string:survey_token>/<string:answer_token>",
        type="jsonrpc",
        auth="public",
        website=True,
    )
    def autoproctor_event(
        self,
        survey_token,
        answer_token,
        event_name=None,
        error_message=None,
    ):
        answer_sudo = self._get_autoproctor_answer(survey_token, answer_token)
        if not answer_sudo:
            return {"ok": False, "error": _("AutoProctor access was denied.")}
        try:
            answer_sudo._register_autoproctor_event(event_name, error_message)
        except UserError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True}

    @http.route(
        "/survey/autoproctor/report/<int:user_input_id>",
        type="http",
        auth="user",
        website=True,
    )
    def autoproctor_report(self, user_input_id):
        if not request.env.user.has_group("survey.group_survey_manager"):
            raise werkzeug.exceptions.NotFound()

        user_input = request.env["survey.user_input"].browse(user_input_id).exists()
        if not user_input:
            raise werkzeug.exceptions.NotFound()
        try:
            user_input.check_access("read")
        except AccessError:
            raise werkzeug.exceptions.NotFound() from None
        if (
            not user_input.survey_id.autoproctor_enabled
            or user_input.autoproctor_state != "stopped"
        ):
            raise werkzeug.exceptions.NotFound()

        try:
            credentials = user_input._get_autoproctor_credentials()
        except UserError:
            raise werkzeug.exceptions.NotFound() from None

        return request.render(
            "survey_auto_proctor.autoproctor_report_page",
            {
                "user_input": user_input,
                "credentials": credentials,
            },
        )

    @http.route("/survey/autoproctor/event/addattemptid",type="jsonrpc", auth="public", website=True,)
    def add_hashed_test_attempt_id_to_user_input(self, survey_token=None, answer_token=None, test_attempt_id=None):
        UserInput = request.env["survey.user_input"].sudo()

        user_input = UserInput.search([
            ("access_token", "=", answer_token),
            ("survey_id.access_token", "=", survey_token),
        ], limit=1)

        if not user_input:
            return {
                "success": False,
                "error": "User input not found",
            }

        user_input.write({
            "autoproctor_attempt_id": test_attempt_id,
        })

        return True

        # return {
        #     "success": True,
        #     "user_input_id": user_input.id,
        #     "autoproctor_attempt_id": user_input.autoproctor_attempt_id,
        # }


    @http.route("/survey/autoproctor/report/<string:test_attempt_id>", type="http", auth="user", website=False,)
    def autoproctor_report(self, test_attempt_id=None):
        ICP = request.env["ir.config_parameter"].sudo()

        client_id = ICP.get_param("survey_auto_proctor.client_id")
        client_secret = ICP.get_param("survey_auto_proctor.client_secret")

        if not client_id or not client_secret:
            return request.make_response(
                """
                <html>
                    <body>
                        <h3>AutoProctor configuration is missing.</h3>
                    </body>
                </html>
                """, headers=[("Content-Type", "text/html; charset=utf-8"),], status=500,)

        api_url = ("https://www.autoproctor.co" f"/api/v2/test-attempts/{test_attempt_id}/")

        try:
            response = requests.get(
                api_url,
                params={
                    "clientId": client_id,
                },
                # در صورتی که API شما برای GET به Authorization
                # نیاز داشته باشد، اینجا اضافه می‌شود.
                timeout=30,
            )

            response.raise_for_status()
            report = response.json()

        except requests.RequestException as e:
            return request.make_response(
                f"""
                <html>
                    <body>
                        <h3>Unable to load Proctoring Report</h3>
                        <p>{str(e)}</p>
                    </body>
                </html>
                """,
                headers=[
                    ("Content-Type", "text/html; charset=utf-8"),
                ],
                status=500,
            )

        return request.render(
            "survey_auto_proctor.autoproctor_report",
            {
                "report": report,
            },
        )