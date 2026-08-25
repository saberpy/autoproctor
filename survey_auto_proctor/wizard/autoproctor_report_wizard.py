import base64
import hashlib
import hmac
import html
import requests

from odoo import api, fields, models


class AutoProctorReportWizard(models.TransientModel):
    _name = "survey.autoproctor.report.wizard"
    _description = "AutoProctor Report"

    user_input_id = fields.Many2one("survey.user_input", string="User Input", required=True, readonly=True,)
    report_html = fields.Html(string="Proctoring Report", readonly=True, sanitize=False,)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user_input = self.env["survey.user_input"].browse(self.env.context.get("active_id")).exists()

        if not user_input:
            return res

        try:
            report = user_input._get_autoproctor_report()
        except Exception as e:
            res.update({
                "user_input_id": user_input.id,
                "report_html": f"""
                    <div class="alert alert-danger">
                        <strong>Failed to load report</strong>
                        <br/>
                        {html.escape(str(e))}
                    </div>
                """,
            })
            return res

        res.update({
            "user_input_id": user_input.id,
            "report_html": self._build_report_html(report, user_input),
        })

        return res

    # =========================================================
    # Build HTML
    # =========================================================

    def _build_report_html(self, final_report, user_input):
        report = final_report.get("report", {},)
        evidence_records = final_report.get("evidence_records", {},)
        primary_device_evidence = evidence_records.get("primary_device_evidence", [],)
        aux_device_evidence = evidence_records.get("aux_device_evidence", [],)
        attempt = report.get("attemptDetails", {},)
        misc_data = attempt.get("miscData", {},)
        user_details = misc_data.get("userDetails", {},)
        user_name = html.escape(str(user_details.get("name") or user_input.partner_id.name or ""))
        user_email = html.escape(str(user_details.get("email") or user_input.partner_id.email or ""))
        trust_score = user_input._get_autoproctor_score() * 100

        result = f"""
            <div class="container-fluid">
                <div class="card mb-3">
                    <div class="card-header">
                        <h4>Proctoring Result</h4>
                    </div>
                    <div class="card-body text-center">
                        <div class="row mb-2">
                            <div class="col-md-3 fw-bold">Status</div>
                            <div class="col-md-9">{html.escape(str(report.get("status") or ""))}</div>
                        </div>
                        <div style="font-size: 36px; font-weight: bold;">{trust_score if trust_score is not None else "-"}</div>
                        <div class="progress mt-3" style="height: 20px;">
                            <div class="progress-bar" style="width: {trust_score}%;">{trust_score}%</div>
                        </div>
                    </div>
                </div>

                <!-- Test Taker -->
                <div class="card mb-3">
                    <div class="card-header">Test Taker</div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-md-3 fw-bold">Name</div>
                            <div class="col-md-9">{user_name}</div>
                        </div>
                        <div class="row">
                            <div class="col-md-3 fw-bold">Email</div>
                            <div class="col-md-9">{user_email}</div>
                        </div>
                    </div>
                </div>

                <!-- Primary Device Evidence -->
                <div class="card mb-3">
                    <div class="card-header">
                        Primary Device Evidence
                        <span class="badge bg-secondary ms-2">{len(primary_device_evidence)}</span>
                    </div>
                    <div class="card-body">{self._build_evidence_items_html(primary_device_evidence)}</div>
                </div>
        """

        # Auxiliary device
        if aux_device_evidence:
            result += f"""
                <div class="card mb-3">
                    <div class="card-header">
                        Auxiliary Device Evidence
                        <span class="badge bg-secondary ms-2">{len(aux_device_evidence)}</span>
                    </div>
                    <div class="card-body">{self._build_evidence_items_html(aux_device_evidence)}</div>
                </div>
            """

        result += """</div>"""

        return result

    # =========================================================
    # Evidence HTML
    # =========================================================

    def _build_evidence_items_html(self, evidence_items):
        if not evidence_items:
            return """<div class="alert alert-info">No evidence records found.</div>"""

        result = ""
        for item in evidence_items:
            label = html.escape(str(item.get("label") or ""))
            evidence_url = item.get("evidence_url")
            violation = bool(item.get("violation"))
            auxiliary_device = bool(item.get("misc_data.auxiliary_device"))
            occurred_at = html.escape(str(item.get("occurred_at_ISO") or ""))
            recorded_at = html.escape(str(item.get("recorded_at_ISO") or ""))

            # -------------------------------------------------
            # Badge
            # -------------------------------------------------
            if violation:
                badge = """<span class="badge bg-danger">Violation</span>"""
                border_class = "border-danger"

            else:
                badge = """<span class="badge bg-success">Normal</span>"""
                border_class = "border-success"

            result += f"""
                <div class="border rounded p-3 mb-3 {border_class}">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong>{label}</strong>
                        {badge}
                    </div>
                    <div class="text-muted small mt-2">
                        Occurred: {occurred_at}
                        <br/>
                        Recorded: {recorded_at}</div>
                    <div class="mt-2">
                        Auxiliary Device:
                        <strong>{"Yes" if auxiliary_device else "No"}</strong>
                    </div>
            """

            # =================================================
            # AUDIO
            # =================================================
            if (label == "noise-detected"and evidence_url):
                safe_url = html.escape(str(evidence_url), quote=True,)
                result += f"""
                    <div class="mt-3">
                        <div class="fw-bold mb-2">Audio Evidence</div>
                        <audio controls preload="metadata" style="width: 100%; max-width: 600px;">
                            <source src="{safe_url}"/>
                            Your browser does not support
                            the audio element.
                        </audio>
                    </div>
                """

            # =================================================
            # IMAGE
            # =================================================
            elif (evidence_url and label in {"random-photo-taken", "test-taker-photo", "photo-taken",}):
                safe_url = html.escape(
                    str(evidence_url),
                    quote=True,
                )
                result += f"""
                    <div class="mt-3">
                        <a
                            href="{safe_url}"
                            target="_blank"
                        >
                            <img
                                src="{safe_url}"
                                style="
                                    max-width: 350px;
                                    max-height: 350px;
                                    object-fit: contain;
                                    border-radius: 8px;
                                "
                                class="img-fluid"
                            />
                        </a>
                    </div>
                """

            # =================================================
            # Other Evidence
            # =================================================
            elif evidence_url:
                safe_url = html.escape(str(evidence_url), quote=True,)
                result += f"""
                    <div class="mt-3">
                        <a href="{safe_url}" target="_blank" class="btn btn-secondary btn-sm">
                            Open Evidence
                        </a>
                    </div>
                """
            else:
                result += """
                    <div class="text-muted mt-3">
                        No evidence file available.
                    </div>
                """

            result += """</div>"""

        return result