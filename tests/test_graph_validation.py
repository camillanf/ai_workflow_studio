from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.engine import WorkflowEngine


@tagged("ai_workflow_studio", "post_install")
class TestGraphValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Workflow = cls.env["aiws.workflow"]
        cls.Node = cls.env["aiws.node"]
        cls.Connection = cls.env["aiws.connection"]
        cls.engine = WorkflowEngine(cls.env)

    def _make_workflow(self, name="Test"):
        return self.Workflow.create({"name": name})

    def _node(self, workflow, node_type, name="Nodo"):
        return self.Node.create(
            {
                "workflow_id": workflow.id,
                "name": name,
                "node_type": node_type,
                "configuration": "{}",
            }
        )

    def test_requires_start_and_end(self):
        wf = self._make_workflow()
        self._node(wf, "odoo_action", "Acción")
        errors = self.engine.validate_graph(wf)
        self.assertTrue(any("Inicio" in (e.get("message", "") if isinstance(e, dict) else e) for e in errors))
        self.assertTrue(any("Fin" in (e.get("message", "") if isinstance(e, dict) else e) for e in errors))

    def test_only_start_is_invalid(self):
        wf = self._make_workflow()
        self._node(wf, "start", "Inicio")
        errors = self.engine.validate_graph(wf)
        self.assertTrue(any("Fin" in (e.get("message", "") if isinstance(e, dict) else e) for e in errors))

    def test_valid_graph_is_ok(self):
        wf = self._make_workflow()
        start = self._node(wf, "start", "Inicio")
        end = self._node(wf, "end", "Fin")
        self.Connection.create(
            {
                "workflow_id": wf.id,
                "source_node_id": start.id,
                "target_node_id": end.id,
            }
        )
        self.assertEqual(self.engine.validate_graph(wf), [])

    def test_cycle_is_invalid(self):
        wf = self._make_workflow()
        n1 = self._node(wf, "odoo_action", "A")
        n2 = self._node(wf, "odoo_action", "B")
        self.Connection.create(
            {
                "workflow_id": wf.id,
                "source_node_id": n1.id,
                "target_node_id": n2.id,
            }
        )
        self.Connection.create(
            {
                "workflow_id": wf.id,
                "source_node_id": n2.id,
                "target_node_id": n1.id,
            }
        )
        errors = self.engine.validate_graph(wf)
        self.assertTrue(any("ciclo" in (e.get("message", "").lower() if isinstance(e, dict) else e.lower()) for e in errors))

    def test_running_invalid_graph_raises(self):
        from ..services.engine import WorkflowEngine

        wf = self._make_workflow()
        self._node(wf, "odoo_action", "Solo acción")
        execution = self.env["aiws.execution"].create(
            {"workflow_id": wf.id, "state": "running", "context": "{}"}
        )
        engine = WorkflowEngine(self.env)
        engine.run(execution)
        execution = self.env["aiws.execution"].browse(execution.id)
        self.assertEqual(execution.state, "error")
        self.assertTrue(execution.error_message)
