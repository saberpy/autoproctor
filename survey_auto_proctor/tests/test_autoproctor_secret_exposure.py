import json
import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Historical value of the secret that used to be hardcoded in this module.
# Kept here only so a regression test can assert it never reappears in source.
_LEAKED_CLIENT_SECRET = "gexcTV6jcboEqYa"

_HARDCODED_SECRET_RE = re.compile(
    r"CLIENT_SECRET\s*[:=]\s*['\"][^'\"]+['\"]"
)

_SOURCE_EXTENSIONS = (".py", ".js")


@tagged("post_install", "-at_install")
class TestAutoProctorSecretExposure(TransactionCase):
    def _module_root(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _iter_source_files(self):
        for root, _dirs, files in os.walk(self._module_root()):
            for name in files:
                if name.endswith(_SOURCE_EXTENSIONS):
                    yield os.path.join(root, name)

    def test_no_hardcoded_client_secret_in_source(self):
        """The AutoProctor Client Secret must never be hardcoded in
        Python or JavaScript source shipped with this module (JS in
        particular ends up as a browser-loaded asset)."""
        offending = []
        for path in self._iter_source_files():
            with open(path, "r", encoding="utf-8") as fobj:
                content = fobj.read()
            if _LEAKED_CLIENT_SECRET in content or _HARDCODED_SECRET_RE.search(content):
                offending.append(path)
        self.assertFalse(
            offending,
            "AutoProctor Client Secret must not be hardcoded in source "
            "files (found in: %s)" % offending,
        )

    def test_credentials_payload_excludes_secret(self):
        """Only clientId/testAttemptId/hashedTestAttemptId may ever be
        handed to the browser; the Client Secret itself must never be
        part of that payload."""
        client_secret = "unit-test-secret-value"
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("survey_auto_proctor.client_id", "unit-test-client-id")
        ICP.set_param("survey_auto_proctor.client_secret", client_secret)

        survey = self.env["survey.survey"].create({
            "title": "AutoProctor Secret Exposure Test Survey",
            "autoproctor_enabled": True,
        })
        user_input = self.env["survey.user_input"].create({
            "survey_id": survey.id,
        })

        credentials = user_input._get_autoproctor_credentials()

        self.assertEqual(
            set(credentials.keys()),
            {"clientId", "testAttemptId", "hashedTestAttemptId"},
        )
        serialized = json.dumps(credentials)
        self.assertNotIn(client_secret, serialized)
