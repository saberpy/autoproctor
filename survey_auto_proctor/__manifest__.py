{
    "name": "Survey Auto Proctor",
    "summary": "Add browser-based proctoring to Odoo surveys",
    "version": "19.0.1.0.0",
    "category": "Marketing/Surveys",
    "author": "saber Zakariaee",
    "license": "LGPL-3",
    "depends": [
        "base_setup",
        "survey",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/survey_survey_views.xml",
        "views/survey_user_input_views.xml",
        "views/survey_templates.xml",
        "views/autoproctor_report_templates.xml",
    ],
    "assets": {
        "survey.survey_assets": [
            "survey_auto_proctor/static/src/scss/autoproctor.scss",
            "survey_auto_proctor/static/src/interactions/autoproctor_survey.js",
        ],
    },
    "installable": True,
    "application": False,
}
