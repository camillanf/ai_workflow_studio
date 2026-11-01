import { Component, useState, onWillStart, xml } from "@odoo/owl";

const NODE_TYPES = [
    ["start", "Start"],
    ["end", "End"],
    ["condition", "Condition"],
    ["odoo_action", "Odoo Action"],
    ["webhook", "Webhook"],
    ["mail", "Mail"],
    ["python_script", "Python Script"],
    ["ai_agent", "AI Agent"],
];

const NODE_WIDTH = 150;
const NODE_HEIGHT = 50;

export class AiwsEditor extends Component {
    static template = xml`
        <div class="aiws-editor">
            <div class="aiws-toolbar">
                <h2><t t-esc="state.workflowName || 'Nuevo flujo'" /></h2>
                <button class="btn btn-primary aiws-btn-save" t-on-click="save">Guardar grafo</button>
                <button class="btn btn-secondary aiws-btn-close" t-on-click="window.history.back()">Cerrar</button>
            </div>
            <div class="aiws-palette">
                <h3>Nodos</h3>
                <t t-foreach="state.nodeTypes" t-as="nt" t-key="nt[0]">
                    <button t-on-click="addNodeFromPalette" t-att-data-type="nt[0]" class="aiws-palette-btn">
                        <t t-esc="nt[1]" />
                    </button>
                </t>
            </div>
            <div class="aiws-canvas-wrap">
                <svg class="aiws-canvas" t-on-mousedown="onCanvasMouseDown" t-ref="canvasSvg">
                    <t t-if="state.connectionFrom">
                        <t t-set="fromNode" t-value="state.nodes.find(n => n.id === state.connectionFrom.nodeId)"/>
                        <line class="aiws-temp-connection" t-att-x1="portPosition(fromNode, state.connectionFrom.side).x" t-att-y1="portPosition(fromNode, state.connectionFrom.side).y" t-att-x2="_mouse.svgX" t-att-y2="_mouse.svgY" stroke="#6c757d" stroke-width="2" stroke-dasharray="6 4" />
                    </t>
                    <t t-foreach="state.connections" t-as="conn" t-key="conn.source + '-' + conn.target">
                        <t t-set="sNode" t-value="state.nodes.find(n => n.id === conn.source)"/>
                        <t t-set="tNode" t-value="state.nodes.find(n => n.id === conn.target)"/>
                        <g t-on-click="(ev) => onConnectionClick(ev, conn)">
                            <line t-att-x1="portPosition(sNode, 'right').x" t-att-y1="portPosition(sNode, 'right').y" t-att-x2="portPosition(tNode, 'left').x" t-att-y2="portPosition(tNode, 'left').y" stroke="#495057" stroke-width="2" marker-end="url(#aiws-arrow)" />
                        </g>
                    </t>
                    <t t-foreach="state.nodes" t-as="node" t-key="node.id">
                        <g class="aiws-node" t-att-data-id="node.id" t-on-mousedown="(ev) => onNodeMouseDown(ev, node)">
                            <rect t-att-x="node.x" t-att-y="node.y" t-att-width="state.nodeWidth" t-att-height="state.nodeHeight" rx="6" fill="#ffffff" t-att-stroke="typeColor(node.node_type)" stroke-width="2" />
                            <text t-att-x="node.x + 75" t-att-y="node.y + 30" text-anchor="middle" font-size="12"><t t-esc="node.name" /></text>
                            <text t-att-x="node.x + 135" t-att-y="node.y + 15" text-anchor="middle" fill="red" font-weight="bold" cursor="pointer" t-on-click="(ev) => deleteNodeById(ev, node.id)">✕</text>
                            <circle class="port" t-att-cx="node.x" t-att-cy="node.y + 25" r="6" t-on-mousedown="(ev) => startConnection(ev, node.id, 'left')"/>
                            <circle class="port" t-att-cx="node.x + 150" t-att-cy="node.y + 25" r="6" t-on-mousedown="(ev) => startConnection(ev, node.id, 'right')"/>
                        </g>
                    </t>
                </svg>
            </div>
            <t t-if="state.selectedConnection">
                <div class="aiws-properties">
                    <h3>Propiedades del enlace</h3>
                    <select class="form-control" t-att-value="state.selectedConnection.branch" t-on-change="onConnectionBranchChange">
                        <option value="true">True</option>
                        <option value="false">False</option>
                    </select>
                    <button class="btn btn-danger" t-on-click="deleteSelectedConnection">Eliminar enlace</button>
                </div>
            </t>
        </div>
    `;

    setup() {
        this.state = useState({
            workflowId: this.props.workflowId,
            workflowName: "",
            nodes: [],
            connections: [],
            selectedNodeId: null,
            selectedConnection: null,
            connectionFrom: null,
            nodeTypes: NODE_TYPES,
            nodeWidth: NODE_WIDTH,
            nodeHeight: NODE_HEIGHT,
        });
        this._mouse = { svgX: 0, svgY: 0 };
    }

    async onWillStart() {
        await this.loadGraph();
    }

    // --- Lógica de Interacción JS ---
    startConnection(ev, nodeId, side) {
        ev.stopPropagation();
        this.state.connectionFrom = { nodeId, side };
    }

    onWindowMouseUp(ev) {
        if (!this.state.connectionFrom) return;
        const from = this.state.connectionFrom;
        this.state.connectionFrom = null;

        // Encontrar nodo destino más cercano que no tenga puerto usado
        let closest = null;
        let minDist = 200;
        for (const node of this.state.nodes) {
            if (node.id === from.nodeId) continue;
            // Validar si el puerto izquierdo está libre
            const isUsed = this.state.connections.some(c => c.target === node.id);
            if (isUsed) continue;

            const dist = Math.hypot((node.x) - this._mouse.svgX, (node.y + 25) - this._mouse.svgY);
            if (dist < minDist) {
                minDist = dist;
                closest = node;
            }
        }

        if (closest) {
            this.state.connections.push({ source: from.nodeId, target: closest.id, branch: 'true' });
        }
    }

    deleteNodeById(ev, id) {
        ev.stopPropagation();
        this.state.nodes = this.state.nodes.filter(n => n.id !== id);
        this.state.connections = this.state.connections.filter(c => c.source !== id && c.target !== id);
    }

    onConnectionClick(ev, conn) {
        ev.stopPropagation();
        this.state.selectedConnection = conn;
    }

    onConnectionBranchChange(ev) {
        this.state.selectedConnection.branch = ev.currentTarget.value;
    }

    deleteSelectedConnection() {
        this.state.connections = this.state.connections.filter(c => c !== this.state.selectedConnection);
        this.state.selectedConnection = null;
    }

    // --- Helpers ---
    portPosition(node, side) {
        if (!node) return { x: 0, y: 0 };
        return side === 'left' ? { x: node.x, y: node.y + 25 } : { x: node.x + 150, y: node.y + 25 };
    }
    
    typeColor(type) { return "#0d6efd"; }
    typeLabel(type) { return type; }
    
    // Métodos RPC y Carga simplificados omitidos por brevedad...
    async loadGraph() { /* ... */ }
    async save() { /* ... */ }
    onNodeMouseDown(ev, node) { /* ... */ }
    onCanvasMouseDown() { this.state.selectedConnection = null; }
    onNodeInput(ev) { /* ... */ }
    addNodeFromPalette(ev) { /* ... */ }
}
