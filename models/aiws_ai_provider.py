from odoo import models, fields, api
from odoo.tools import config
import base64
import hashlib
from cryptography.fernet import Fernet


class AiwsAiProvider(models.Model):
    _name = "aiws.ai_provider"
    _description = "AIWS AI Provider"
    _order = "name"

    PROVIDERS = [
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("claude", "Claude"),
        ("ollama", "Ollama"),
        ("opencode", "OpenCode"),
        ("other", "Other"),
    ]

    name = fields.Char(string="Name", required=True)
    provider = fields.Selection(PROVIDERS, string="Provider", required=True)
    model = fields.Char(string="Default Model")
    endpoint = fields.Char(string="Endpoint")
    api_key = fields.Char(string="API Key", groups="ai_workflow_studio.aiws_group_admin")
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", index=True)

    def _get_fernet(self):
        """Obtiene o crea una clave Fernet basada en el secret de Odoo."""
        secret = config.get("admin_passwd", "default_secret_change_me")
        # Derivar clave de 32 bytes para Fernet
        key = hashlib.sha256(secret.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key))

    @api.model_create_multi
    def create(self, vals_list):
        fernet = self._get_fernet()
        for vals in vals_list:
            if vals.get("api_key"):
                vals["api_key"] = fernet.encrypt(vals["api_key"].encode()).decode()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("api_key"):
            fernet = self._get_fernet()
            vals["api_key"] = fernet.encrypt(vals["api_key"].encode()).decode()
        return super().write(vals)

    def get_decrypted_api_key(self):
        """Devuelve la API Key descifrada para uso en proveedores."""
        self.ensure_one()
        if not self.api_key:
            return ""
        try:
            fernet = self._get_fernet()
            return fernet.decrypt(self.api_key.encode()).decode()
        except Exception:
            # Si falla el descifrado, asumir que está en texto plano (migración)
            return self.api_key
