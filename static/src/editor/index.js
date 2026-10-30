import { App } from "@odoo/owl";
import { AiwsEditor } from "./editor";

// Bloquear cualquier cambio de URL (redirect) del WebClient de Odoo
// para que la página del editor standalone no sea redirigida a otra acción.
try {
    const _loc = window.location;
    const _desc = Object.getOwnPropertyDescriptor(window, "location") || {};
    if (_desc.configurable) {
        Object.defineProperty(window, "location", {
            configurable: true,
            get: function () { return _loc; },
            set: function () { /* bloquear redirect */ },
        });
    }
    _loc.assign = function () {};
    _loc.replace = function () {};
} catch (e) {
    // eslint-disable-next-line no-console
    console.warn("AIWS Editor: no se pudo bloquear location", e);
}

function mount() {
    const root = document.getElementById("aiws-editor-root");
    if (!root) {
        if (mount._attempts === undefined) mount._attempts = 0;
        mount._attempts++;
        if (mount._attempts < 100) {
            setTimeout(mount, 100);
        } else {
            // eslint-disable-next-line no-console
            console.error("AIWS Editor: no se encontró el nodo #aiws-editor-root tras 100 intentos");
        }
        return;
    }

    const workflowId = root.dataset.workflowId
        ? parseInt(root.dataset.workflowId, 10)
        : undefined;

    try {
        const app = new App(AiwsEditor, {
            props: { workflowId },
        });
        app.mount(root);
        // eslint-disable-next-line no-console
        console.log("AIWS Editor: componente OWL montado correctamente");
    } catch (e) {
        // eslint-disable-next-line no-console
        console.error("AIWS Editor: error montando el componente OWL", e);
        root.innerHTML =
            '<div style="padding:16px;color:#c00">Error cargando el editor visual. Revisa la consola del navegador.</div>';
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
} else {
    mount();
}
