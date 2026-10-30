{
    "name": "AI Workflow Studio",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Visual no-code workflow automation based on AI agents",
    "description": """
AI Workflow Studio
=================

Allows non-technical users to create visual automation workflows based on AI
agents inside Odoo 19 Community.

V1 features:
- Visual workflow editor (OWL, no external libraries)
- Node types: Start, End, Condition, Odoo Action, Webhook, Mail, Python Script, AI Agent
- Manual and scheduled execution (ir.cron)
- Execution history and per-node traceability (logs)
- AI provider interface (stub in V1, no real network calls)

Security:
- Groups: User (view/run), Editor (create/edit), Administrator (credentials, scripts)
- Multi-company record rules
- API keys never exposed in logs

V2/V3 roadmap: secured Python Script node, real AI providers, event triggers, templates marketplace.
""",
    "author": "AI Workflow Studio Contributors",
    "website": "https://github.com/ai-workflow-studio/ai_workflow_studio",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/aiws_groups.xml",
        "security/aiws_security.xml",
        "views/actions.xml",
        "views/menus.xml",
        "views/aiws_workflow_views.xml",
        "views/aiws_execution_views.xml",
        "views/aiws_execution_log_views.xml",
        "views/aiws_ai_provider_views.xml",
        "data/aiws_data.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
    "assets": {},
}
