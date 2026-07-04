/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";

export class BuscadorPublico extends Component {
    setup() {
        this.state = useState({
            sorteos: [],
            sorteoId: null,
            fecha: '',
            resultados: null,
            cargando: false,
        });

        onWillStart(async () => {
            try {
                const data = await jsonrpc("/lottery/sorteos-publicos", {});
                this.state.sorteos = data.sorteos || [];
                this.state.sorteoId = data.default_id || null;
            } catch (e) {
                this.state.sorteos = [];
            }
        });
    }

    onSorteoChange(ev) {
        this.state.sorteoId = parseInt(ev.target.value) || null;
        this.state.fecha = '';
        this.state.resultados = null;
    }

    async buscarSalida(ev) {
        this.state.fecha = ev.target.value;
        if (!this.state.fecha || !this.state.sorteoId) {
            this.state.resultados = null;
            return;
        }
        this.state.cargando = true;
        try {
            const data = await jsonrpc("/salidas/buscar", {
                fecha: this.state.fecha,
                sorteo_id: this.state.sorteoId,
            });
            this.state.resultados = data;
        } catch (e) {
            this.state.resultados = null;
        } finally {
            this.state.cargando = false;
        }
    }
}

BuscadorPublico.template = "lottery_portal.BuscadorPublico";

registry.category("public_components").add(
    "lottery_portal.BuscadorPublico",
    BuscadorPublico
);
