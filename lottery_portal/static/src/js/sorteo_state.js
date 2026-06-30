/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";

const STORAGE_KEY = "lottery_portal_sorteo_id";

export const sorteoState = reactive({
    sorteoId: null,
    sorteoName: "",
    sorteos: [],
    loaded: false,
    listeners: [],
});

function notify() {
    for (const cb of sorteoState.listeners) {
        cb(sorteoState.sorteoId);
    }
}

export function onSorteoChange(callback) {
    sorteoState.listeners.push(callback);
}

let _loadingPromise = null;

export async function ensureSorteoLoaded() {
    if (sorteoState.loaded) {
        return sorteoState;
    }
    if (_loadingPromise) {
        return _loadingPromise;
    }
    _loadingPromise = (async () => {
        try {
            const data = await jsonrpc("/lottery/sorteos", {});
            sorteoState.sorteos = data.sorteos || [];

            let storedId = null;
            try {
                const raw = window.localStorage.getItem(STORAGE_KEY);
                storedId = raw ? parseInt(raw) : null;
            } catch (e) {
                storedId = null;
            }

            const valid = storedId && sorteoState.sorteos.some((s) => s.id === storedId);
            const selected = valid ? storedId : data.default_id;

            const found = sorteoState.sorteos.find((s) => s.id === selected);
            sorteoState.sorteoId = selected;
            sorteoState.sorteoName = found ? found.name : "";
            sorteoState.loaded = true;
            return sorteoState;
        } catch (e) {
            // No cachear el fallo: la próxima llamada a ensureSorteoLoaded()
            // debe poder reintentar en vez de quedar bloqueada para siempre
            // (lo que dejaría todos los componentes de la página sin datos).
            _loadingPromise = null;
            throw e;
        }
    })();
    return _loadingPromise;
}

export function setSorteo(id) {
    const sorteoId = parseInt(id);
    if (sorteoId === sorteoState.sorteoId) {
        return;
    }
    const found = sorteoState.sorteos.find((s) => s.id === sorteoId);
    sorteoState.sorteoId = sorteoId;
    sorteoState.sorteoName = found ? found.name : "";
    try {
        window.localStorage.setItem(STORAGE_KEY, String(sorteoId));
    } catch (e) {
        /* localStorage no disponible */
    }
    notify();
}
