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
                <div t-if="state.message" t-att-class="state.messageClass">
                    <t t-esc="state.message" />
                </div>
            </div>
            <div class="aiws-palette">
                <h3>Nodos</h3>
                <t t-foreach="state.nodeTypes" t-as="nt" t-key="nt[0]">
                    <button
                        t-on-click="addNodeFromPalette"
                        t-att-data-type="nt[0]"
                        class="aiws-palette-btn"
                    >
                        <t t-esc="nt[1]" />
                    </button>
                </t>
                <p class="aiws-hint">Arrastra los nodos en el lienzo. Haz clic en un puerto para conectar nodos.</p>
            </div>
            <div class="aiws-canvas-wrap">
                <svg class="aiws-canvas" t-on-mousedown="onCanvasMouseDown">
                    <t t-if="state.connectionFrom">
                        <t t-set="fromNode" t-value="state.nodes.find(n => n.id === state.connectionFrom.nodeId)"/>
                        <t t-if="fromNode">
                            <t t-set="p1" t-value="portPosition(fromNode, state.connectionFrom.side)"/>
                            <line
                                class="aiws-temp-connection"
                                t-att-x1="p1.x"
                                t-att-y1="p1.y"
                                t-att-x2="_mouse.x"
                                t-att-y2="_mouse.y"
                                stroke="#6c757d"
                                stroke-width="2"
                                stroke-dasharray="6 4"
                            />
                        </t>
                    </t>
                    <t t-foreach="state.connections" t-as="conn" t-key="conn.source + '-' + conn.target">
                        <t t-set="sNode" t-value="state.nodes.find(n => n.id === conn.source)"/>
                        <t t-set="tNode" t-value="state.nodes.find(n => n.id === conn.target)"/>
                        <t t-if="sNode and tNode">
                            <t t-set="p1" t-value="portPosition(sNode, 'right')"/>
                            <t t-set="p2" t-value="portPosition(tNode, 'left')"/>
                            <line
                                t-att-x1="p1.x"
                                t-att-y1="p1.y"
                                t-att-x2="p2.x"
                                t-att-y2="p2.y"
                                stroke="#495057"
                                stroke-width="2"
                                marker-end="url(#aiws-arrow)"
                            />
                        </t>
                    </t>
                    <t t-foreach="state.nodes" t-as="node" t-key="node.id" class="aiws-node" t-att-data-id="node.id" t-on-mousedown="(ev) => onNodeMouseDown(ev, node)">
                        <rect
                            t-att-x="node.x"
                            t-att-y="node.y"
                            t-att-width="state.nodeWidth"
                            t-att-height="state.nodeHeight"
                            rx="6"
                            fill="#ffffff"
                            t-att-stroke="typeColor(node.node_type)"
                            stroke-width="2"
                            cursor="move"
                        />
                        <text
                            t-att-x="node.x + state.nodeWidth / 2"
                            t-att-y="node.y + state.nodeHeight / 2 + 5"
                            text-anchor="middle"
                            fill="#333"
                            font-size="13"
                            pointer-events="none"
                        ><t t-esc="node.name" /></text>
                        <t t-set="p" t-value="portPosition(node, 'top')"/>
                        <circle class="port port-top" t-att-cx="p.x" t-att-cy="p.y" r="6" t-att-fill="typeColor(node.node_type)" stroke="#333" stroke-width="1" cursor="crosshair" t-on-mousedown="(ev) => startConnection(node.id, 'top')"/>
                        <t t-set="p" t-value="portPosition(node, 'bottom')"/>
                        <circle class="port port-bottom" t-att-cx="p.x" t-att-cy="p.y" r="6" t-att-fill="typeColor(node.node_type)" stroke="#333" stroke-width="1" cursor="crosshair" t-on-mousedown="(ev) => startConnection(node.id, 'bottom')"/>
                        <t t-set="p" t-value="portPosition(node, 'left')"/>
                        <circle class="port port-left" t-att-cx="p.x" t-att-cy="p.y" r="6" t-att-fill="typeColor(node.node_type)" stroke="#333" stroke-width="1" cursor="crosshair" t-on-mousedown="(ev) => startConnection(node.id, 'left')"/>
                        <t t-set="p" t-value="portPosition(node, 'right')"/>
                        <circle class="port port-right" t-att-cx="p.x" t-att-cy="p.y" r="6" t-att-fill="typeColor(node.node_type)" stroke="#333" stroke-width="1" cursor="crosshair" t-on-mousedown="(ev) => endConnection(node.id)"/>
                    </t>
                    <defs>
                        <marker id="aiws-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#495057"/>
                        </marker>
                    </defs>
                </svg>
            </div>
            <t t-if="state.selectedNode">
                <t t-set="node" t-value="selectedNode"/>
                <div class="aiws-properties">
                    <h3>Propiedades del nodo</h3>
                    <div class="aiws-prop-row">
                        <label>Nombre</label>
                        <input class="form-control" t-att-data-id="node.id" data-field="name" t-att-value="node.name" t-on-input="onNodeInput"/>
                    </div>
                    <div class="aiws-prop-row">
                        <label>Tipo</label>
                        <span class="aiws-badge" t-att-style="'background-color: ' + typeColor(node.node_type) + '; color: #fff'"><t t-esc="typeLabel(node.node_type)" /></span>
                    </div>
                    <div class="aiws-prop-row">
                        <label>Configuración (JSON)</label>
                        <textarea class="form-control" t-att-data-id="node.id" data-field="configuration" t-att-value="node.configuration" t-on-input="onNodeInput"></textarea>
                    </div>
                    <button class="btn btn-danger" t-on-click="deleteNode">Eliminar nodo</button>
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
            connectionFrom: null,
            message: "",
            messageType: "info",
            messageClass: "",
            loading: true,
            nodeTypes: NODE_TYPES,
            nodeWidth: NODE_WIDTH,
            nodeHeight: NODE_HEIGHT,
        });
        this._drag = null;
        this._mouse = { x: 0, y: 0 };
        this._boundMove = this._onWindowMouseMove.bind(this);
        this._boundUp = this._onWindowMouseUp.bind(this);
    }

    async onWillStart() {
        await this.loadGraph();
        window.addEventListener("mousemove", this._boundMove);
        window.addEventListener("mouseup", this._boundUp);
    }

    show(message, type = "info") {
        this.state.message = message;
        this.state.messageType = type;
        this.state.messageClass = "aiws-message aiws-message-" + type;
        setTimeout(() => {
            if (this.state.message === message) {
                this.state.message = "";
                this.state.messageClass = "";
            }
        }, 5000);
    }

    // ------------------------------------------------------------------
    // JSON-RPC helper (fetch nativo, usa window.odoo.csrf_token)
    // ------------------------------------------------------------------
    async _rpc(url, params = {}) {
        const csrfToken = window.odoo && window.odoo.csrf_token ? window.odoo.csrf_token : "";
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            credentials: "same-origin",
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
            }),
        });
        const data = await resp.json();
        if (data.error) {
            throw new Error(data.error.message || data.error || "RPC error");
        }
        return data.result;
    }

    // ------------------------------------------------------------------
    // Carga
    // ------------------------------------------------------------------
    async loadGraph() {
        try {
            const result = await this._rpc(
                "/aiws/workflow/" + this.state.workflowId + "/graph",
                {}
            );
            if (result.error) {
                throw new Error(result.error);
            }
            this.state.workflowName = result.workflow.name;
            this.state.nodes = (result.nodes || []).map((n) => ({
                id: n.id,
                name: n.name || "Nodo",
                node_type: n.node_type || "odoo_action",
                configuration: n.configuration || "{}",
                x: n.position_x || 100,
                y: n.position_y || 100,
            }));
            this.state.connections = (result.connections || []).map((c) => {
                const source = c.source_node_id ? c.source_node_id[0] : false;
                const target = c.target_node_id ? c.target_node_id[0] : false;
                if (!source || !target) return null;
                return {
                    source: source,
                    target: target,
                    label: c.label || "",
                    condition: c.condition || "",
                };
            }).filter(Boolean);
        } catch (e) {
            this.show("Error cargando el grafo: " + (e.message || e), "error");
        } finally {
            this.state.loading = false;
        }
    }

    // ------------------------------------------------------------------
    // Nodos
    // ------------------------------------------------------------------
    addNode(nodeType) {
        const id = Date.now() + Math.random();
        this.state.nodes.push({
            id: id,
            name: nodeType.charAt(0).toUpperCase() + nodeType.slice(1),
            node_type: nodeType,
            configuration: "{}",
            x: 300 + this.state.nodes.length * 40,
            y: 150 + (this.state.nodes.length % 5) * 70,
        });
        this.state.selectedNodeId = id;
    }

    deleteNode() {
        if (!this.state.selectedNodeId) return;
        const id = this.state.selectedNodeId;
        this.state.nodes = this.state.nodes.filter((n) => n.id !== id);
        this.state.connections = this.state.connections.filter(
            (c) => c.source !== id && c.target !== id
        );
        this.state.selectedNodeId = null;
        this.show("Nodo eliminado");
    }

    selectNode(id) {
        this.state.selectedNodeId = id;
    }

    get selectedNode() {
        return this.state.nodes.find((n) => n.id === this.state.selectedNodeId);
    }

    // ------------------------------------------------------------------
    // Conexiones
    // ------------------------------------------------------------------
    startConnection(nodeId, side) {
        this.state.connectionFrom = { nodeId, side };
    }

    endConnection(nodeId) {
        if (!this.state.connectionFrom) return;
        const from = this.state.connectionFrom;
        if (from.nodeId === nodeId) {
            this.state.connectionFrom = null;
            return;
        }
        const exists = this.state.connections.some(
            (c) => c.source === from.nodeId && c.target === nodeId
        );
        if (!exists) {
            this.state.connections.push({
                source: from.nodeId,
                target: nodeId,
                label: "",
                condition: "",
            });
        }
        this.state.connectionFrom = null;
    }

    deleteConnection(index) {
        this.state.connections.splice(index, 1);
    }

    // ------------------------------------------------------------------
    // Guardado y validación
    // ------------------------------------------------------------------
    async save() {
        const payload = {
            nodes: this.state.nodes.map((n) => ({
                id: n.id,
                name: n.name,
                node_type: n.node_type,
                configuration: n.configuration,
                position_x: Math.round(n.x),
                position_y: Math.round(n.y),
                sequence: 10,
            })),
            connections: this.state.connections.map((c, i) => ({
                source: c.source,
                target: c.target,
                label: c.label,
                condition: c.condition,
                sequence: i,
            })),
        };
        try {
            const result = await this._rpc(
                "/aiws/workflow/" + this.state.workflowId + "/save_graph",
                payload
            );
            if (result.error) {
                if (result.messages) {
                    this.show(result.messages.join("\n"), "error");
                } else {
                    this.show(result.error, "error");
                }
            } else {
                this.show("Grafo guardado y validado correctamente", "success");
            }
        } catch (e) {
            this.show("Error guardando: " + (e.message || e), "error");
        }
    }

    // ------------------------------------------------------------------
    // Interacción (arrastrar, puertos, lienzo)
    // ------------------------------------------------------------------
    onNodeMouseDown(ev, node) {
        ev.stopPropagation();
        this.state.selectedNodeId = node.id;
        this._drag = {
            node: node,
            offsetX: ev.clientX - node.x,
            offsetY: ev.clientY - node.y,
        };
    }

    onCanvasMouseDown(ev) {
        this.state.selectedNodeId = null;
        this.state.connectionFrom = null;
    }

    _onWindowMouseMove(ev) {
        this._mouse = { x: ev.clientX, y: ev.clientY };
        if (this._drag) {
            this._drag.node.x = ev.clientX - this._drag.offsetX;
            this._drag.node.y = ev.clientY - this._drag.offsetY;
        }
    }

    _onWindowMouseUp(ev) {
        if (this._drag) this._drag = null;
    }

    portPosition(node, side) {
        switch (side) {
            case "top": return { x: node.x + state.nodeWidth / 2, y: node.y };
            case "bottom": return { x: node.x + state.nodeWidth / 2, y: node.y + state.nodeHeight };
            case "left": return { x: node.x, y: node.y + state.nodeHeight / 2 };
            case "right": return { x: node.x + state.nodeWidth, y: node.y + state.nodeHeight / 2 };
        }
        return { x: node.x, y: node.y };
    }

    typeLabel(nodeType) {
        const map = Object.fromEntries(NODE_TYPES);
        return map[nodeType] || nodeType;
    }

    typeColor(nodeType) {
        const colors = {
            start: "#6f42c1",
            end: "#dc3545",
            condition: "#ffc107",
            odoo_action: "#0d6efd",
            webhook: "#198754",
            mail: "#6610f2",
            python_script: "#fd7e14",
            ai_agent: "#20c997",
        };
        return colors[nodeType] || "#6c757d";
    }

    addNodeFromPalette(ev) {
        const nodeType = ev.currentTarget.dataset.type;
        this.addNode(nodeType);
    }

    onNodeInput(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        const field = ev.currentTarget.dataset.field;
        const node = this.state.nodes.find((n) => n.id === id);
        if (node) {
            node[field] = ev.currentTarget.value;
        }
    }
}
