from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.ai_provider import StubAIProvider, AIResponse
from ..services.engine import WorkflowEngine


@tagged("ai_workflow_studio", "post_install")
class TestStubIA(TransactionCase):
    def test_stub_provider_without_network(self):
        provider = StubAIProvider()
        response = provider.generate(prompt="Hola", context={"foo": 1})
        self.assertIsInstance(response, AIResponse)
        self.assertTrue(response.stub)
        self.assertEqual(response.provider, "stub")
        self.assertIn("simulada", response.text)

    def test_ai_agent_node_returns_stub(self):
        wf = self.env["aiws.workflow"].create({"name": "IA Test"})
        node = self.env["aiws.node"].create(
            {
                "workflow_id": wf.id,
                "name": "Agente",
                "node_type": "ai_agent",
                'configuration': {"prompt": "dime algo"},
            }
        )
        eng = WorkflowEngine(self.env)
        outputs = eng._handle_ai_agent(node, {"foo": 1}, wf)
        self.assertIn("ai_response", outputs)
        self.assertTrue(outputs.get("ai_stub"))
        self.assertEqual(outputs["context"].get("foo"), 1)
        self.assertIn("ai_response", outputs["context"])
