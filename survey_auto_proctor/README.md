# Survey AutoProctor Integration

This Odoo 19 module adds optional AutoProctor monitoring to standard Odoo surveys. Odoo remains responsible for survey questions, answers, timing, scoring, retries, and final submission. AutoProctor provides browser-based monitoring and its hosted report.

## Features

- Per-survey `Enable AutoProctor` option.
- Configurable background-noise, face-count, tab/window-switch, and random-photo tracking.
- HMAC-SHA256 authentication generated exclusively by the Odoo backend.
- A unique 32-character AutoProctor attempt ID for each `survey.user_input`.
- Monitoring starts before Odoo begins the survey.
- Incomplete attempts resume with the same AutoProctor attempt ID.
- Monitoring stops only after Odoo successfully marks the attempt as completed.
- AutoProctor status and timestamps on the participant record.
- Hosted proctoring report available only to Survey Administrators.

## Installation and configuration

1. Install the module.
2. Open **Settings > General Settings > Integrations > AutoProctor**.
3. Enter the AutoProctor Client ID and Client Secret, then save.
4. Open a survey and go to **Options > Proctoring**.
5. Enable AutoProctor and select the required tracking options.

The Client Secret is stored as a system parameter and is never included in QWeb templates, JavaScript assets, URLs, or controller responses. Rotate any secret that has previously been exposed in chat, source control, logs, or browser code.

## Operational notes

- HTTPS is required for dependable camera and microphone access.
- Proctored Live Session surveys are intentionally rejected because their host-driven lifecycle does not use the normal participant start flow.
- The module is fail-closed: an enabled proctored survey cannot start if SDK loading, configuration, permission acquisition, setup, or monitoring startup fails.
- Closing or refreshing an in-progress survey does not stop AutoProctor. The participant must resume monitoring with the same attempt ID.
- Evidence is kept by AutoProctor. This module does not copy camera, microphone, or screenshot evidence into Odoo attachments.

## Acceptance checklist

1. A survey with AutoProctor disabled behaves exactly like the standard Odoo survey.
2. A proctored survey stays in `New` when the SDK cannot load or the participant denies a required permission.
3. The Odoo attempt moves to `In Progress` only after the AutoProctor status becomes `Monitoring`.
4. Calling the standard begin or submit JSON-RPC route before monitoring is active is rejected.
5. Refreshing an in-progress attempt displays the resume gate and reuses the same 32-character attempt ID.
6. A required-question validation error leaves monitoring active.
7. A successful final submission moves the Odoo attempt to `Completed`, then finalizes AutoProctor.
8. A Survey Administrator can open the AutoProctor report from the participant form after finalization.
9. A Survey User who is not a Survey Administrator cannot open the report route.
