from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.engine import WorkflowEngine


@tagged("ai_workflow_studio", "post_install")
class TestEngine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = WorkflowEngine(cls.env)

    def _make_workflow(self, name="Engine Test"):
        return self.env["aiws.workflow"].create({"name": name})

    def _node(self, workflow, node_type, name="Nodo", configuration="{}"):
        return self.env["aiws.node"].create(
            {
                "workflow_id": workflow.id,
                "name": name,
                "node_type": node_type,
                "configuration": configuration,
            }
        )

    def _connect(self, workflow, source, target, condition=""):
        return self.env["aiws.connection"].create(
            {
                "workflow_id": workflow.id,
                "source_node_id": source.id,
                "target_node_id": target.id,
                "condition": condition,
            }
        )

    def test_simple_start_to_end(self):
        wf = self._make_workflow()
        start = self._node(wf, "start", "Inicio")
        end = self._node(wf, "end", "Fin")
        self._connect(wf, start, end)

        execution = self.env["aiws.execution"].create(
            {"workflow_id": wf.id, "state": "running", "context": "{}"}
        )
        self.engine.run(execution)
        self.assertEqual(execution.state, "done")
        self.assertEqual(len(execution.log_ids), 2)
        states = execution.log_ids.mapped("node_type")
        self.assertIn("start", states)
        self.assertIn("end", states)

    def test_condition_routes_by_expression(self):
        wf = self._make_workflow()
        start = self._node(wf, "start", "Inicio")
        cond = self._node(wf, "condition", "Condición")
        end_ok = self._node(wf, "end", "Aprobado")
        end_ko = self._node(wf, "end", "Rechazado")
        self._connect(wf, start, cond)
        self._connect(wf, cond, end_ok, "context.get('approve') is True")
        self._connect(wf, cond, end_ko, "context.get('approve') is not True")

        execution = self.env["aiws.execution"].create(
            {
                "workflow_id": wf.id,
                "state": "running",
                'context': '{"approve": true}',
            }
        )
        self.engine.run(execution)
        self.assertEqual(execution.state, "done")
        executed = execution.log_ids.mapped("node_type")
        self.assertIn("condition", executed)
        self.assertIn("end", executed)
        end_names = execution.log_ids.filtered(lambda l: l.node_type == "end").mapped(
            "node_id.name"
        )
        self.assertIn("Aprobado", end_names)

    def test_steps_limit(self):
        wf = self._make_workflow()
        start = self._node(wf, "start", "Inicio")
        n1 = self._node(wf, "odoo_action", "A")
        end = self._node(wf, "end", "Fin")
        self._connect(wf, start, n1)
        self._connect(wf, n1, end)

        engine = WorkflowEngine(self.env)
        engine.MAX_STEPS = 1  # falla al intentar ejecutar el segundo nodo

        execution = self.env["aiws.execution"].create(
            {"workflow_id": wf.id, "state": "running", "context": "{}"}
        )
        engine.run(execution)
        self.assertEqual(execution.state, "error")
