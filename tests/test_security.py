from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..controllers.main import AiwsController


@tagged("ai_workflow_studio", "post_install")
class TestSecurity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("ai_workflow_studio.aiws_group_user")
        cls.group_admin = cls.env.ref("ai_workflow_studio.aiws_group_admin")
        cls.user_aiws_user = cls.env["res.users"].create(
            {
                "name": "Usuario AIWS",
                "login": "aiws_user",
                "group_ids": [(6, 0, [cls.group_user.id])],
            }
        )
        cls.user_aiws_admin = cls.env["res.users"].create(
            {
                "name": "Administrador AIWS",
                "login": "aiws_admin",
                "group_ids": [(6, 0, [cls.group_admin.id])],
            }
        )

    def _provider(self, env):
        return env["aiws.ai_provider"].create(
            {"name": "Proveedor prueba", "provider": "openai", "api_key": "sk-secret"}
        )

    def test_admin_reads_ai_provider(self):
        env = self.env(user=self.user_aiws_admin)
        provider = self._provider(env)
        env["aiws.ai_provider"].search([("id", "=", provider.id)])

    def test_user_cannot_read_ai_provider(self):
        env_user = self.env(user=self.user_aiws_user)
        provider = self._provider(self.env(user=self.user_aiws_admin))
        with self.assertRaises(AccessError):
            env_user["aiws.ai_provider"].browse([provider.id]).read()

    def test_admin_creates_python_script_node(self):
        env = self.env(user=self.user_aiws_admin)
        wf = env["aiws.workflow"].create({"name": "W"})
        node = env["aiws.node"].create(
            {
                "workflow_id": wf.id,
                "name": "Script",
                "node_type": "python_script",
                "configuration": "{}",
            }
        )
        self.assertEqual(node.node_type, "python_script")

    def test_user_cannot_create_python_script_node(self):
        env = self.env(user=self.user_aiws_user)
        wf = env["aiws.workflow"].create({"name": "W"})
        with self.assertRaises(UserError):
            env["aiws.node"].create(
                {
                    "workflow_id": wf.id,
                    "name": "Script",
                    "node_type": "python_script",
                    "configuration": "{}",
                }
            )

    def test_webhook_ssrf_blocks_loopback(self):
        controller = AiwsController()
        with self.assertRaises(UserError):
            controller.call_webhook("http://127.0.0.1:8069/")

    def test_webhook_ssrf_blocks_private_ip(self):
        controller = AiwsController()
        with self.assertRaises(UserError):
            controller.call_webhook("http://10.0.0.1/")

    def test_webhook_call_rejects_invalid_scheme(self):
        controller = AiwsController()
        with self.assertRaises(UserError):
            controller.call_webhook("ftp://files.example.com/")
