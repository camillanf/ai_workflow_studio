// Editor Visual Standalone - Vanilla JS
// IIFE con reintentos cada 100ms: soporta carga dinámica de Odoo donde
// DOMContentLoaded ya habrá ocurrido antes de que este script se ejecute.
(function () {
    "use strict";

    var _initTries = 0;

    function init() {
        var root = document.getElementById("aiws-editor-root");
        if (!root) return false;

        // workflow_id del atributo data-workflow-id (pasado por el controlador)
        var workflowId = parseInt(root.dataset.workflowId || root.dataset.workflow_id || "0", 10);
        if (workflowId) state.workflowId = workflowId;

        createEditorUI();
        if (state.workflowId) loadGraph();
        else console.warn("AIWS Editor: no workflow_id found, graph won't load");

        return true;
    }

    function _tryInit() {
        if (init()) return;
        _initTries++;
        if (_initTries < 600) { // hasta 60s
            setTimeout(_tryInit, 100);
        }
    }

    // ====================================================================
    // CSS incorporado
    // ====================================================================
    var style = document.createElement("style");
    style.textContent = "\n" +
        "        .aiws-main { display: flex; height: calc(100vh - 50px); overflow: hidden; }\n" +
"        .aiws-toolbar { display: flex; align-items: center; padding: 8px 16px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; }\n" +
"        .aiws-toolbar h2 { margin: 0 12px 0 0; font-size: 16px; color: #495057; }\n" +
"        .aiws-btn { padding: 6px 14px; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; margin-left: 6px; }\n" +
"        .aiws-btn-primary { background: #0d6efd; color: #fff; }\n" +
"        .aiws-btn-primary:hover { background: #0b5ed7; }\n" +
"        .aiws-btn-secondary { background: #6c757d; color: #fff; }\n" +
"        .aiws-btn-secondary:hover { background: #5c6268; }\n" +
"        .aiws-message { padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-left: 16px; display: none; }\n" +
"        .aiws-message-success { background: #d1e7dd; color: #155; }\n" +
"        .aiws-message-error { background: #f8d7da; color: #155; }\n" +
"        .aiws-message-info { background: #cfe2ff; color: #155; }\n" +
"        .aiws-palette { width: 220px; padding: 12px; background: #f8f9fa; border-right: 1px solid #dee2e6; flex-shrink: 0; overflow-y: auto; }\n" +
"        .aiws-palette h3 { margin: 0 0 10px 0; font-size: 14px; color: #495057; }\n" +
"        .aiws-palette-btn { display: block; width: 100%; padding: 8px 12px; margin-bottom: 6px; background: #fff; border: 1px solid #ced4da; border-radius: 4px; color: #495057; cursor: pointer; font-size: 13px; text-align: left; }\n" +
"        .aiws-palette-btn:hover { background: #e9ecef; border-color: #adb5bd; }\n" +
"        .aiws-palette-btn:active { background: #dee2e6; }\n" +
"        .aiws-hint { font-size: 11px; color: #6c757d; margin-top: 10px; line-height: 1.4; }\n" +
"        .aiws-canvas-wrap { flex: 1 1 auto; position: relative; overflow: auto; background: #ffffff; }\n" +
"        .aiws-canvas { display: block; background: #ffffff; cursor: crosshair; }\n" +
"        .aiws-node { cursor: move; }\n" +
"        .aiws-node.aiws-selected rect { stroke: #ff0000 !important; stroke-width: 3; }\n" +
"        .aiws-temp-connection { stroke: #6c757d; stroke-width: 2; stroke-dasharray: 6 4; }\n" +
"        .aiws-conn-marker { cursor: pointer; user-select: none; }\n" +
"        .aiws-conn-marker.true { fill: #1e7e34; }\n" +
"        .aiws-conn-marker.false { fill: #dc3545; }\n" +
"        .aiws-properties { width: 320px; padding: 20px; overflow-y: auto; border-left: 1px solid #dee2e6; background: #f8f9fa; flex-shrink: 0; }\n" +
"        .aiws-properties h3 { margin-top: 0; font-size: 16px; color: #495057; border-bottom: 1px solid #dee2e6; padding-bottom: 8px; }\n" +
"        .aiws-properties h4 { font-size: 14px; color: #495057; margin: 16px 0 8px 0; }\n" +
"        .aiws-prop-row { display: flex; flex-direction: column; margin-bottom: 14px; }\n" +
"        .aiws-prop-row label { font-size: 12px; font-weight: 600; color: #495057; margin-bottom: 4px; }\n" +
"        .aiws-prop-row input, .aiws-prop-row textarea, .aiws-prop-row select { width: 100%; padding: 6px 8px; font-size: 13px; border: 1px solid #ced4da; border-radius: 4px; }\n" +
"        .aiws-badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 600; }\n" +
"        .btn { padding: 6px 14px; border: none; border-radius: 4px; font-size: 13px; cursor: pointer; }\n" +
"        .btn-danger { background: #dc3545; color: #fff; margin-top: 10px; width: 100%; }\n" +
"        .btn-danger:hover { background: #c82333; }\n" +
        "\n";
    document.head.appendChild(style);

    // ====================================================================
    // Utilidades DOM
    // ====================================================================
    function $(sel) { return document.querySelector(sel); }
    function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

    // ====================================================================
    // Constantes
    // ====================================================================
    var NODE_TYPES = [
        ["start", "Start"],
        ["end", "End"],
        ["condition", "Condition"],
        ["odoo_action", "Odoo Action"],
        ["webhook", "Webhook"],
        ["mail", "Mail"],
        ["python_script", "Python Script"],
        ["ai_agent", "AI Agent"],
    ];

    var NODE_WIDTH = 150;
    var NODE_HEIGHT = 50;
    var DRAG_THRESHOLD = 5;

    function typeColor(type) {
        switch (type) {
            case "start": return "#6f42c1";
            case "end": return "#dc3545";
            case "condition": return "#ffc107";
            case "odoo_action": return "#0d6efd";
            case "webhook": return "#198754";
            case "mail": return "#6610f2";
            case "python_script": return "#fd7e14";
            case "ai_agent": return "#20c997";
            default: return "#6c757d";
        }
    }

    function typeLabel(type) {
        var map = {};
        NODE_TYPES.forEach(function (nt) { map[nt[0]] = nt[1]; });
        return map[type] || type;
    }

    function nearestEdgePoint(node, tx, ty) {
        // Devuelve el punto del borde del rectangulo del nodo mas cercano al punto (tx, ty)
        var cx = node.x + NODE_WIDTH / 2;
        var cy = node.y + NODE_HEIGHT / 2;
        var dx = tx - cx;
        var dy = ty - cy;
        var ax = Math.abs(dx);
        var ay = Math.abs(dy);
        if (ax * NODE_HEIGHT > ay * NODE_WIDTH) {
            if (dx > 0) {
                return { x: node.x + NODE_WIDTH, y: Math.min(Math.max(ty, node.y), node.y + NODE_HEIGHT) };
            } else {
                return { x: node.x, y: Math.min(Math.max(ty, node.y), node.y + NODE_HEIGHT) };
            }
        } else {
            if (dy > 0) {
                return { x: Math.min(Math.max(tx, node.x), node.x + NODE_WIDTH), y: node.y + NODE_HEIGHT };
            } else {
                return { x: Math.min(Math.max(tx, node.x), node.x + NODE_WIDTH), y: node.y };
            }
        }
    }

    function connectionPoints(sNode, tNode) {
        // Devuelve los puntos de inicio y fin de una conexión entre dos nodos.
        // Si hay solapamiento en el eje perpendicular (alineados lado a lado o uno sobre otro),
        // la conexión es una línea recta horizontal o vertical en el punto medio del solapamiento.
        // De lo contrario, usa nearestEdgePoint para ambos extremos.

        var sRight = sNode.x + NODE_WIDTH;
        var sBottom = sNode.y + NODE_HEIGHT;
        var tRight = tNode.x + NODE_WIDTH;
        var tBottom = tNode.y + NODE_HEIGHT;

        // Solapamiento en Y (para conexión horizontal lado a lado)
        var yOverlapStart = Math.max(sNode.y, tNode.y);
        var yOverlapEnd = Math.min(sBottom, tBottom);
        var yOverlap = yOverlapEnd - yOverlapStart;

        // Solapamiento en X (para conexión vertical uno sobre otro)
        var xOverlapStart = Math.max(sNode.x, tNode.x);
        var xOverlapEnd = Math.min(sRight, tRight);
        var xOverlap = xOverlapEnd - xOverlapStart;

        // Nodos lado a lado (solapamiento en Y, sin solapamiento en X)
        if (yOverlap > 0 && xOverlap <= 0) {
            var yMid = yOverlapStart + yOverlap / 2;
            if (sRight <= tNode.x) {
                return { p1: { x: sRight, y: yMid }, p2: { x: tNode.x, y: yMid } };
            } else {
                return { p1: { x: sNode.x, y: yMid }, p2: { x: tRight, y: yMid } };
            }
        }

        // Nodos uno sobre otro (solapamiento en X, sin solapamiento en Y)
        if (xOverlap > 0 && yOverlap <= 0) {
            var xMid = xOverlapStart + xOverlap / 2;
            if (sBottom <= tNode.y) {
                return { p1: { x: xMid, y: sBottom }, p2: { x: xMid, y: tNode.y } };
            } else {
                return { p1: { x: xMid, y: sNode.y }, p2: { x: xMid, y: tBottom } };
            }
        }

        // Caso general: usar nearestEdgePoint para ambos extremos
        var p1 = nearestEdgePoint(sNode, tNode.x + NODE_WIDTH / 2, tNode.y + NODE_HEIGHT / 2);
        var p2 = nearestEdgePoint(tNode, sNode.x + NODE_WIDTH / 2, sNode.y + NODE_HEIGHT / 2);
        return { p1: p1, p2: p2 };
    }

    // ====================================================================
    // State
    // ====================================================================
    var state = {
        workflowId: null,
        workflowName: "",
        nodes: [],
        connections: [],
        providers: [],
        selectedNodeId: null,
        selectedConnection: null,
        connectionFrom: null,
        draggingConnection: false,
        mouseX: 0,
        mouseY: 0,
        rightClickConnection: false,
    };

    // Arastre de nodo: { node, gEl, offsetX, offsetY, startX, startY, moved }
    var _drag = null;

    // ====================================================================
    // RPC helper
    // ====================================================================
    function _rpc(url, params) {
        var csrfToken = window.odoo && window.odoo.csrf_token ? window.odoo.csrf_token : "";
        return fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },
            credentials: "same-origin",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params }),
        }).then(function (resp) { return resp.json(); }).then(function (data) {
            if (data.error) throw new Error(data.error.message || data.error || "RPC error");
            return data.result;
        });
    }

    // ====================================================================
    // Cargar grafo
    // ====================================================================
    function loadGraph() {
        if (!state.workflowId) return;
        _rpc("/aiws/workflow/" + state.workflowId + "/graph", {}).then(function (result) {
            state.workflowName = result.workflow.name;
            state.nodes = (result.nodes || []).map(function (n) {
                return {
                    id: n.id, name: n.name || "Nodo",
                    node_type: n.node_type || "odoo_action",
                    configuration: n.configuration || "{}",
                    condition: n.condition || "",
                    x: n.position_x || 100, y: n.position_y || 100,
                };
            });
            state.connections = (result.connections || []).map(function (c) {
                var source = c.source_node_id ? c.source_node_id[0] : false;
                var target = c.target_node_id ? c.target_node_id[0] : false;
                if (!source || !target) return null;
                return {
                    source: source, target: target,
                    label: c.label || "", condition: c.condition || "",
                    branch: c.branch || "",
                };
            }).filter(Boolean);
            state.providers = result.providers || [];
            render();
            renderProperties();
        }).catch(function (e) { show("Error cargando el grafo: " + (e.message || e), "error"); });
    }

    // ====================================================================
    // Nodos
    // ====================================================================
    function addNode(nodeType) {
        var id = Date.now() + Math.random();
        state.nodes.push({
            id: id, name: NODE_TYPES.find(function(n){return n[0]===nodeType;}) ? typeLabel(nodeType) : nodeType,
            node_type: nodeType, configuration: "{}", condition: "",
            x: 300 + state.nodes.length * 40, y: 150 + (state.nodes.length % 5) * 70,
        });
        state.selectedNodeId = id;
        render();
        renderProperties();
    }

    function deleteNode(nodeId) {
        state.nodes = state.nodes.filter(function (n) { return n.id !== nodeId; });
        state.connections = state.connections.filter(function (c) {
            return c.source !== nodeId && c.target !== nodeId;
        });
        state.selectedNodeId = null;
        render();
        renderProperties();
        show("Nodo eliminado", "success");
    }

    function deleteConnection(source, target) {
        state.connections = state.connections.filter(function (c) {
            return !(c.source === source && c.target === target);
        });
        renumberSequences();
        render();
    }

    function renumberSequences() {
        state.connections.forEach(function (c, i) { c.sequence = i + 1; });
    }

    function defaultBranch(fromNodeId) {
        var fromNode = state.nodes.find(function (n) { return n.id === fromNodeId; });
        var outCount = state.connections.filter(function (c) { return c.source === fromNodeId; }).length;
        if (fromNode && fromNode.node_type === "condition") {
            return outCount === 0 ? "true" : "false";
        }
        return "";
    }

    // ====================================================================
    // Guardar grafo
    // ====================================================================
    function saveGraph() {
        var payload = {
            nodes: state.nodes.map(function (n) {
                return { id: n.id, name: n.name, node_type: n.node_type,
                    configuration: n.configuration, position_x: Math.round(n.x),
                    position_y: Math.round(n.y), sequence: 10 };
            }),
            connections: state.connections.map(function (c, i) {
                return { source: c.source, target: c.target, label: c.label,
                    condition: c.condition, branch: c.branch || "", sequence: i };
            }),
        };
        _rpc("/aiws/workflow/" + state.workflowId + "/save_graph", payload).then(function (result) {
            if (result.error) { show(result.error || "Error guardando", "error"); }
            else { show("Grafo guardado correctamente", "success"); render(); }
        }).catch(function (e) { show("Error guardando: " + (e.message || e), "error"); });
    }

    // ====================================================================
    // Mensajes
    // ====================================================================
    function show(msg, type) {
        var el = $("#aiws-message");
        if (!el) return;
        el.textContent = msg || "";
        el.style.display = msg ? "block" : "none";
        el.className = "aiws-message aiws-message-" + (type || "info");
        if (msg) {
            setTimeout(function () {
                var cur = $("#aiws-message");
                if (cur && cur.textContent === msg) { cur.style.display = "none"; cur.textContent = ""; }
            }, 5000);
        }
    }

    // ====================================================================
    // Render SVG
    // ====================================================================
    function render() {
        var svg = $(".aiws-canvas");
        if (!svg) return;

        var defs = svg.querySelector("defs");
        svg.innerHTML = "";
        if (defs) svg.appendChild(defs);

        // Línea temporal de conexión (arrastrando desde puerto)
        if (state.connectionFrom) {
            var fromNode = state.nodes.find(function (n) { return n.id === state.connectionFrom.nodeId; });
            if (fromNode) {
                var p1 = nearestEdgePoint(fromNode, state.mouseX, state.mouseY);
                var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("class", "aiws-temp-connection");
                line.setAttribute("x1", p1.x); line.setAttribute("y1", p1.y);
                line.setAttribute("x2", state.mouseX); line.setAttribute("y2", state.mouseY);
                line.setAttribute("stroke", "#6c757d"); line.setAttribute("stroke-width", "2");
                line.setAttribute("stroke-dasharray", "6 4");
                svg.appendChild(line);
            }
        }

        // Conexiones guardadas
        state.connections.forEach(function (conn) {
            var sNode = state.nodes.find(function (n) { return n.id === conn.source; });
            var tNode = state.nodes.find(function (n) { return n.id === conn.target; });
            if (!sNode || !tNode) return;
            var pts = connectionPoints(sNode, tNode);
            var p1 = pts.p1, p2 = pts.p2;
            var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", p1.x); line.setAttribute("y1", p1.y);
            line.setAttribute("x2", p2.x); line.setAttribute("y2", p2.y);
            line.setAttribute("stroke", "#495057"); line.setAttribute("stroke-width", "2");
            line.setAttribute("marker-end", "url(#aiws-arrow)");
            svg.appendChild(line);

            var isCondition = (sNode.node_type === "condition");
            var midX = (p1.x + p2.x) / 2, midY = (p1.y + p2.y) / 2;
            var markerColor = (isCondition && conn.branch === "true") ? "#1e7e34" : "#dc3545";
            var markerText = (isCondition) ? ((conn.branch === "true") ? "v" : "f") : "x";

            var markerGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
            markerGroup.setAttribute("class", "aiws-conn-marker");
            markerGroup.setAttribute("transform", "translate(" + midX + "," + midY + ")");

            var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("r", "10");
            circle.setAttribute("fill", markerColor);
            circle.setAttribute("stroke", "#333");
            circle.setAttribute("stroke-width", "1");

            var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("dominant-baseline", "middle");
            text.setAttribute("font-size", "14");
            text.setAttribute("font-weight", "bold");
            text.setAttribute("fill", "#ffffff");
            text.textContent = markerText;

            markerGroup.appendChild(circle);
            markerGroup.appendChild(text);

            markerGroup.addEventListener("mousedown", function (ev) {
                ev.stopPropagation();
            });
            markerGroup.addEventListener("click", function (ev) {
                ev.stopPropagation();
                if (isCondition) {
                    selectConnection(conn);
                } else {
                    deleteConnection(conn.source, conn.target);
                }
            });
            svg.appendChild(markerGroup);
        });

        // Nodos
        state.nodes.forEach(function (node) {
            var g = document.createElementNS("http://www.w3.org/2000/svg", "g");
            var className = "aiws-node";
            if (node.id === state.selectedNodeId) className += " aiws-selected";
            g.setAttribute("class", className);
            g.setAttribute("data-id", node.id);
            g.style.cursor = "move";

            var rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            rect.setAttribute("x", node.x); rect.setAttribute("y", node.y);
            rect.setAttribute("width", NODE_WIDTH); rect.setAttribute("height", NODE_HEIGHT);
            rect.setAttribute("rx", "6"); rect.setAttribute("fill", "#ffffff");
            rect.setAttribute("stroke", typeColor(node.node_type)); rect.setAttribute("stroke-width", "5");
            g.appendChild(rect);

            var text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("x", node.x + NODE_WIDTH / 2);
            text.setAttribute("y", node.y + NODE_HEIGHT / 2 + 5);
            text.setAttribute("text-anchor", "middle"); text.setAttribute("fill", "#333");
            text.setAttribute("font-size", "13"); text.setAttribute("pointer-events", "none");
            text.textContent = node.name;
            g.appendChild(text);

            svg.appendChild(g);
        });
    }

    // ====================================================================
    // ====================================================================
    // Selección de conexión
    // ====================================================================
    function selectConnection(conn) {
        state.selectedConnection = conn;
        state.selectedNodeId = null;
        render();
        renderProperties();
    }

    // Panel de propiedades
    // ====================================================================
    function renderProperties() {
        var container = $("#aiws-properties");
        if (!container) return;
        container.innerHTML = "";

        var h3 = document.createElement("h3"); h3.textContent = "Propiedades";
        container.appendChild(h3);

        if (state.selectedConnection) {
            var conn = state.selectedConnection;
            var sNode = state.nodes.find(function (n) { return n.id === conn.source; });
            var isCondition = sNode && sNode.node_type === "condition";

            if (isCondition) {
                var row = document.createElement("div"); row.className = "aiws-prop-row";
                var label = document.createElement("label"); label.textContent = "Rama";
                var select = document.createElement("select");
                var optTrue = document.createElement("option"); optTrue.value = "true"; optTrue.textContent = "v  True";
                var optFalse = document.createElement("option"); optFalse.value = "false"; optFalse.textContent = "f  False";
                select.appendChild(optTrue); select.appendChild(optFalse);
                select.value = conn.branch || "true";
                select.addEventListener("change", function (ev) {
                    ev.stopPropagation();
                    conn.branch = ev.currentTarget.value;
                    render();
                    renderProperties();
                });
                row.appendChild(label); row.appendChild(select); container.appendChild(row);
            }

            var btnDel = document.createElement("button");
            btnDel.className = "btn btn-danger"; btnDel.textContent = "Eliminar conexión";
            btnDel.addEventListener("click", function (ev) {
                ev.stopPropagation();
                deleteConnection(conn.source, conn.target);
                state.selectedConnection = null;
                render();
                renderProperties();
            });
            container.appendChild(btnDel);
            return;
        }

        if (!state.selectedNodeId) {
            container.innerHTML = "<p style='font-size:12px;color:#6c757d;'>Selecciona un nodo para ver sus propiedades.</p>";
            return;
        }

        var node = state.nodes.find(function (n) { return n.id === state.selectedNodeId; });
        if (!node) return;

        // Nombre
        var row = document.createElement("div"); row.className = "aiws-prop-row";
        var label = document.createElement("label"); label.textContent = "Nombre";
        var input = document.createElement("input"); input.type = "text";
        input.value = node.name || ""; input.dataset.id = node.id; input.dataset.field = "name";
        input.addEventListener("input", onNodeInput);
        row.appendChild(label); row.appendChild(input); container.appendChild(row);

        // Tipo
        var row2 = document.createElement("div"); row2.className = "aiws-prop-row";
        var label2 = document.createElement("label"); label2.textContent = "Tipo";
        var badge = document.createElement("span");
        badge.className = "aiws-badge"; badge.style.backgroundColor = typeColor(node.node_type);
        badge.style.color = "#fff"; badge.textContent = typeLabel(node.node_type);
        row2.appendChild(label2); row2.appendChild(badge); container.appendChild(row2);

        // Configuración JSON
        var row3 = document.createElement("div"); row3.className = "aiws-prop-row";
        var label3 = document.createElement("label"); label3.textContent = "Configuración (JSON)";
        var ta = document.createElement("textarea"); ta.value = node.configuration || "{}"; ta.rows = 4;
        ta.dataset.id = node.id; ta.dataset.field = "configuration";
        ta.addEventListener("input", onNodeInput);
        row3.appendChild(label3); row3.appendChild(ta); container.appendChild(row3);

        // Paneles específicos
        if (node.node_type === "condition") renderConditionPanel(node, container);
        else if (node.node_type === "ai_agent") renderAIAgentPanel(node, container);
        else if (node.node_type === "python_script") renderPythonScriptPanel(node, container);

        // Eliminar
        var btnDel = document.createElement("button");
        btnDel.className = "btn btn-danger"; btnDel.textContent = "Eliminar nodo";
        btnDel.addEventListener("click", function (ev) { ev.stopPropagation(); deleteNode(node.id); });
        container.appendChild(btnDel);
    }

    function _parseConfig(node) {
        var config = {};
        try { config = JSON.parse(node.configuration || "{}"); } catch (e) {}
        return config;
    }

    function renderConditionPanel(node, container) {
        var h4 = document.createElement("h4"); h4.textContent = "Condición"; container.appendChild(h4);
        var row = document.createElement("div"); row.className = "aiws-prop-row";
        var label = document.createElement("label"); label.textContent = "Expresión de condición";
        var input = document.createElement("input"); input.type = "text";
        var config = _parseConfig(node);
        input.value = config.condition_expression || "";
        input.placeholder = "Ej: {{ ctx.amount > 100 }}";
        input.dataset.id = node.id; input.dataset.key = "condition_expression";
        input.addEventListener("input", onConfigInput);
        row.appendChild(label); row.appendChild(input); container.appendChild(row);

        var help = document.createElement("p"); help.className = "aiws-hint";
        help.textContent = "La condición determina qué rama (true/false) seguir. Conecta 2 nodos de salida.";
        container.appendChild(help);
    }

    function renderAIAgentPanel(node, container) {
        var h4 = document.createElement("h4"); h4.textContent = "Agente IA"; container.appendChild(h4);
        var config = _parseConfig(node);

        var rowProv = document.createElement("div"); rowProv.className = "aiws-prop-row";
        var labelProv = document.createElement("label"); labelProv.textContent = "Proveedor";
        var selectProv = document.createElement("select");
        selectProv.dataset.id = node.id; selectProv.dataset.key = "provider";
        selectProv.addEventListener("change", onConfigInput);
        var defOpt = document.createElement("option"); defOpt.value = ""; defOpt.textContent = "Seleccionar proveedor...";
        selectProv.appendChild(defOpt);
        (state.providers || []).forEach(function (p) {
            var opt = document.createElement("option"); opt.value = p.id; opt.textContent = p.name;
            selectProv.appendChild(opt);
        });
        selectProv.value = config.provider || "";
        rowProv.appendChild(labelProv); rowProv.appendChild(selectProv); container.appendChild(rowProv);

        var rowPrompt = document.createElement("div"); rowPrompt.className = "aiws-prop-row";
        var labelPrompt = document.createElement("label"); labelPrompt.textContent = "Prompt";
        var taPrompt = document.createElement("textarea"); taPrompt.value = config.prompt || "";
        taPrompt.placeholder = "Prompt para el agente IA..."; taPrompt.rows = 3;
        taPrompt.dataset.id = node.id; taPrompt.dataset.key = "prompt";
        taPrompt.addEventListener("input", onConfigInput);
        rowPrompt.appendChild(labelPrompt); rowPrompt.appendChild(taPrompt); container.appendChild(rowPrompt);

        var rowSys = document.createElement("div"); rowSys.className = "aiws-prop-row";
        var labelSys = document.createElement("label"); labelSys.textContent = "System Prompt";
        var taSys = document.createElement("textarea"); taSys.value = config.system_prompt || "";
        taSys.placeholder = "Instrucciones del sistema (opcional)..."; taSys.rows = 2;
        taSys.dataset.id = node.id; taSys.dataset.key = "system_prompt";
        taSys.addEventListener("input", onConfigInput);
        rowSys.appendChild(labelSys); rowSys.appendChild(taSys); container.appendChild(rowSys);

        var rowOut = document.createElement("div"); rowOut.className = "aiws-prop-row";
        var labelOut = document.createElement("label"); labelOut.textContent = "Variable de salida";
        var inputOut = document.createElement("input"); inputOut.type = "text";
        inputOut.value = config.output_variable || "ai_response";
        inputOut.dataset.id = node.id; inputOut.dataset.key = "output_variable";
        inputOut.addEventListener("input", onConfigInput);
        rowOut.appendChild(labelOut); rowOut.appendChild(inputOut); container.appendChild(rowOut);
    }

    function renderPythonScriptPanel(node, container) {
        var h4 = document.createElement("h4"); h4.textContent = "Python Script"; container.appendChild(h4);
        var config = _parseConfig(node);

        var rowCode = document.createElement("div"); rowCode.className = "aiws-prop-row";
        var labelCode = document.createElement("label"); labelCode.textContent = "Código Python";
        var taCode = document.createElement("textarea");
        taCode.value = config.code || ""; taCode.placeholder = "# Escribe tu código Python\nctx.result = ...";
        taCode.rows = 8; taCode.dataset.id = node.id; taCode.dataset.key = "code";
        taCode.addEventListener("input", onConfigInput);
        rowCode.appendChild(labelCode); rowCode.appendChild(taCode); container.appendChild(rowCode);

        var rowTimeout = document.createElement("div"); rowTimeout.className = "aiws-prop-row";
        var labelTimeout = document.createElement("label"); labelTimeout.textContent = "Tiempo máximo (s)";
        var inputTimeout = document.createElement("input"); inputTimeout.type = "number";
        inputTimeout.value = config.timeout || 30; inputTimeout.min = "1"; inputTimeout.max = "300";
        inputTimeout.dataset.id = node.id; inputTimeout.dataset.key = "timeout";
        inputTimeout.addEventListener("input", onConfigInput);
        rowTimeout.appendChild(labelTimeout); rowTimeout.appendChild(inputTimeout); container.appendChild(rowTimeout);

        var rowKey = document.createElement("div"); rowKey.className = "aiws-prop-row";
        var labelKey = document.createElement("label"); labelKey.textContent = "Clave de salida";
        var inputKey = document.createElement("input"); inputKey.type = "text";
        inputKey.value = config.output_key || "result"; inputKey.placeholder = "result";
        inputKey.dataset.id = node.id; inputKey.dataset.key = "output_key";
        inputKey.addEventListener("input", onConfigInput);
        rowKey.appendChild(labelKey); rowKey.appendChild(inputKey); container.appendChild(rowKey);
    }

    // ====================================================================
    // Input handlers
    // ====================================================================
    function onNodeInput(ev) {
        var id = parseFloat(ev.currentTarget.dataset.id);
        var field = ev.currentTarget.dataset.field;
        var node = state.nodes.find(function (n) { return n.id === id; });
        if (node) node[field] = ev.currentTarget.value;
    }

    function onConfigInput(ev) {
        var id = parseFloat(ev.currentTarget.dataset.id);
        var key = ev.currentTarget.dataset.key;
        var node = state.nodes.find(function (n) { return n.id === id; });
        if (node && key) {
            var config = _parseConfig(node);
            config[key] = ev.currentTarget.value;
            node.configuration = JSON.stringify(config);
        }
    }

    // ====================================================================
    // Arrastre de nodos y creación de conexiones
    // ====================================================================
    function onWindowMouseMove(ev) {
        var svg = $(".aiws-canvas");
        if (svg) {
            var rect = svg.getBoundingClientRect();
            state.mouseX = ev.clientX - rect.left;
            state.mouseY = ev.clientY - rect.top;
        }

        // Línea temporal de conexión
        if (state.connectionFrom && svg) {
            var tempLine = svg.querySelector(".aiws-temp-connection");
            if (tempLine) {
                var fromNode = state.nodes.find(function (n) { return n.id === state.connectionFrom.nodeId; });
                if (fromNode) {
                    var p1 = nearestEdgePoint(fromNode, state.mouseX, state.mouseY);
                    tempLine.setAttribute("x1", p1.x);
                    tempLine.setAttribute("y1", p1.y);
                }
                tempLine.setAttribute("x2", state.mouseX);
                tempLine.setAttribute("y2", state.mouseY);
            }
        }

        // Arrastrar nodo — solo si se superó el umbral
        if (_drag && _drag.moved) {
            var svg2 = $(".aiws-canvas");
            var rect2 = svg2 ? svg2.getBoundingClientRect() : { left: 0, top: 0, right: 0, bottom: 0 };
            var newX = ev.clientX - rect2.left - _drag.offsetX;
            var newY = ev.clientY - rect2.top - _drag.offsetY;
            _drag.node.x = newX;
            _drag.node.y = newY;
            _updateNodeElement(_drag.gEl, newX, newY);
        }
    }

    function _updateNodeElement(g, x, y) {
        if (!g) return;
        var r = g.querySelector("rect");
        if (r) { r.setAttribute("x", x); r.setAttribute("y", y); }
        var t = g.querySelector("text");
        if (t) { t.setAttribute("x", x + NODE_WIDTH / 2); t.setAttribute("y", y + NODE_HEIGHT / 2 + 5); }
    }

    function onWindowMouseMoveWrapper(ev) {
        // Verificar umbral de arrastre
        if (_drag && !_drag.moved) {
            var dx = Math.abs(ev.clientX - _drag.startX);
            var dy = Math.abs(ev.clientY - _drag.startY);
            if (dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD) {
                _drag.moved = true;
            }
        }
        onWindowMouseMove(ev);
    }

    function onWindowMouseUp(ev) {
        // Finalizar arrastre de nodo
        if (_drag) {
            var g = _drag.gEl;
            if (g) {
                g.style.opacity = "";
                var r = g.querySelector("rect");
                if (r) r.setAttribute("stroke", typeColor(_drag.node.node_type));
            }
            render();
            renderProperties();
            _drag = null;
            return;
        }

        // Finalizar creación de conexión
        if (state.draggingConnection && state.connectionFrom) {
            var svg = $(".aiws-canvas");
            if (svg) {
                var rect = svg.getBoundingClientRect();
                var sx = ev.clientX - rect.left;
                var sy = ev.clientY - rect.top;

                var targetNodeEl = null;
                var groups = svg.querySelectorAll(".aiws-node");
                for (var i = 0; i < groups.length; i++) {
                    var gEl = groups[i];
                    var bb = gEl.getBoundingClientRect();
                    var gRect = { left: bb.left - rect.left, top: bb.top - rect.top, width: bb.width, height: bb.height };
                    if (sx >= gRect.left && sx <= gRect.left + gRect.width &&
                        sy >= gRect.top && sy <= gRect.top + gRect.height) {
                        targetNodeEl = gEl;
                        break;
                    }
                }

                if (targetNodeEl && targetNodeEl.dataset.id) {
                    var targetNodeId = parseFloat(targetNodeEl.dataset.id);
                    var fromNodeId = state.connectionFrom.nodeId;
                    if (fromNodeId !== targetNodeId) {
                        var exists = state.connections.some(function (c) {
                            return c.source === fromNodeId && c.target === targetNodeId;
                        });
                        if (!exists) {
                            state.connections.push({
                                source: fromNodeId, target: targetNodeId,
                                label: "", condition: "",
                                branch: defaultBranch(fromNodeId),
                            });
                        }
                    }
                }
            }
            state.connectionFrom = null;
            state.draggingConnection = false;
            state.rightClickConnection = false;
            render();
        }
    }

    // ====================================================================
    // Canvas mousedown
    // ====================================================================
    function attachCanvasEvents() {
        var svg = $(".aiws-canvas");
        if (!svg) return;

        // Prevenir menú contextual del navegador
        svg.addEventListener("contextmenu", function (ev) {
            ev.preventDefault();
        });

        svg.addEventListener("mousedown", function (ev) {
            // Click derecho sobre nodo: iniciar creación de conexión
            if (ev.button === 2) {
                var gEl = ev.target.closest ? ev.target.closest(".aiws-node") : null;
                if (!gEl && ev.target && ev.target.classList) {
                    var el = ev.target;
                    while (el && el !== svg) {
                        if (el.classList && el.classList.contains("aiws-node")) { gEl = el; break; }
                        el = el.parentNode;
                    }
                }
                if (gEl) {
                    ev.stopPropagation();
                    ev.preventDefault();
                    var nodeId = parseFloat(gEl.dataset.id);
                    state.connectionFrom = { nodeId: nodeId };
                    state.rightClickConnection = true;
                    state.draggingConnection = true;
                    state.selectedNodeId = null;
                    render();
                    return;
                }
            }

            // Click izquierdo sobre nodo: seleccionar e iniciar arrastre (con umbral)
            if (ev.button === 0) {
                var gEl2 = ev.target.closest ? ev.target.closest(".aiws-node") : null;
                if (!gEl2 && ev.target && ev.target.classList) {
                    var el2 = ev.target;
                    while (el2 && el2 !== svg) {
                        if (el2.classList && el2.classList.contains("aiws-node")) { gEl2 = el2; break; }
                        el2 = el2.parentNode;
                    }
                }
                if (gEl2) {
                    ev.stopPropagation();
                    var nodeId = parseFloat(gEl2.dataset.id);
                    var node = state.nodes.find(function (n) { return n.id === nodeId; });
                    if (!node) return;

                    var rect = svg.getBoundingClientRect();
                    state.selectedNodeId = nodeId;
                    state.selectedConnection = null;

                    _drag = {
                        node: node, gEl: gEl2,
                        offsetX: ev.clientX - rect.left - node.x,
                        offsetY: ev.clientY - rect.top - node.y,
                        startX: ev.clientX, startY: ev.clientY,
                        moved: false,
                    };

                    gEl2.style.opacity = "0.7";
                    var r = gEl2.querySelector("rect");
                    if (r) r.setAttribute("stroke", "#ff0000");

                    renderProperties();
                    ev.preventDefault();
                    return;
                }
            }

            // Fondo del canvas: deseleccionar
            state.selectedNodeId = null;
            state.selectedConnection = null;
            state.connectionFrom = null;
            state.draggingConnection = false;
            state.rightClickConnection = false;
            _drag = null;
            render();
            renderProperties();
        });
    }

    // ====================================================================
    // Paleta de nodos
    // ====================================================================
    function attachPaletteEvents() {
        $$(".aiws-palette-btn").forEach(function (btn) {
            btn.addEventListener("click", function (ev) {
                ev.stopPropagation();
                addNode(btn.dataset.type);
            });
        });

        var btnSave = $("#aiws-btn-save");
        if (btnSave) btnSave.addEventListener("click", function (ev) { ev.stopPropagation(); saveGraph(); });

        var btnClose = $("#aiws-btn-close");
        if (btnClose) btnClose.addEventListener("click", function (ev) {
            ev.stopPropagation();
            if (window.opener || window.parent !== window) window.close();
            else window.location.href = "/web#action=ai_workflow_studio.action_aiws_workflow";
        });
    }

    // ====================================================================
    // Crear UI del editor
    // ====================================================================
    function createEditorUI() {
        var root = $("#aiws-editor-root");
        if (!root) return;
        root.innerHTML = "";
        root.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

        var toolbar = document.createElement("div");
        toolbar.className = "aiws-toolbar";
        toolbar.innerHTML =
            '<h2 id="aiws-title">Nuevo flujo</h2>' +
            '<button id="aiws-btn-save" class="aiws-btn aiws-btn-primary">Guardar grafo</button>' +
            '<button id="aiws-btn-close" class="aiws-btn aiws-btn-secondary">Cerrar</button>' +
            '<div id="aiws-message" class="aiws-message" style="display:none;"></div>';
        root.appendChild(toolbar);

        var main = document.createElement("div");
        main.className = "aiws-main";
        main.style.display = "flex"; main.style.height = "calc(100vh - 46px)";
        main.style.overflow = "hidden";

        var palette = document.createElement("div");
        palette.className = "aiws-palette";
        palette.innerHTML =
            '<h3>Nodos disponibles</h3>' +
            '<div id="aiws-palette-buttons"></div>' +
            '<p class="aiws-hint">Haz clic en un nodo para seleccionarlo. Click y arrastra el nodo para moverlo. Click en un puerto y arrastra hasta otro nodo para crear una conexión.</p>';
        main.appendChild(palette);

        var canvasWrap = document.createElement("div");
        canvasWrap.className = "aiws-canvas-wrap";
        canvasWrap.style.flex = "1 1 auto"; canvasWrap.style.overflow = "auto";
        canvasWrap.style.position = "relative";
        var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "aiws-canvas");
        svg.setAttribute("width", "100%"); svg.setAttribute("height", "100%");
        svg.style.display = "block"; svg.style.background = "#ffffff"; svg.style.border = "none";
        svg.style.cursor = "crosshair";

        var defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        var marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
        marker.setAttribute("id", "aiws-arrow"); marker.setAttribute("markerWidth", "10");
        marker.setAttribute("markerHeight", "7"); marker.setAttribute("refX", "9");
        marker.setAttribute("refY", "3.5"); marker.setAttribute("orient", "auto");
        var polygon = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
        polygon.setAttribute("points", "0 0, 10 3.5, 0 7"); polygon.setAttribute("fill", "#495057");
        marker.appendChild(polygon); defs.appendChild(marker); svg.appendChild(defs);
        canvasWrap.appendChild(svg);
        main.appendChild(canvasWrap);

        var props = document.createElement("div");
        props.id = "aiws-properties"; props.className = "aiws-properties";
        main.appendChild(props);

        root.appendChild(main);

        var paletteBtns = $("#aiws-palette-buttons");
        NODE_TYPES.forEach(function (nt) {
            var btn = document.createElement("button");
            btn.className = "aiws-palette-btn"; btn.dataset.type = nt[0]; btn.textContent = nt[1];
            paletteBtns.appendChild(btn);
        });

        attachCanvasEvents();
        attachPaletteEvents();

        window.addEventListener("mousemove", onWindowMouseMoveWrapper);
        window.addEventListener("mouseup", onWindowMouseUp);
    }

    // ====================================================================
    // Arranque
    // ====================================================================
    _tryInit();
})();