/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class ConsultarAcompanantes extends Component {
    setup() {
        this.state = useState({
            numero_text: '',
            number_id: null,
            sugerencias: [],
            socios_posteriores: [],
            socios_anteriores: [],
            loading: false,
        });

        onSorteoChange(() => {
            if (this.state.number_id) {
                this.loadSocios();
            }
        });
    }

    async loadSocios() {
        await ensureSorteoLoaded();
        this.state.loading = true;
        const data = await jsonrpc(
            "/estadisticas-numeros/numeros-socios",
            { number_id: this.state.number_id, sorteo_id: sorteoState.sorteoId }
        );
        this.state.socios_posteriores = data.salidas_numeros_despues_numero || [];
        this.state.socios_anteriores  = data.salidas_numeros_antes_numero   || [];
        this.state.loading = false;
    }

    getBallClass(i) {
        if (i < 3) return "ball-red";
        if (i < 7) return "ball-blue";
        return "ball-green";
    }

    async onBuscarNumero(ev) {
        const term = ev.target.value;
        this.state.numero_text = term;
        if (!term) {
            this.state.sugerencias = [];
            this.state.socios_posteriores = [];
            this.state.socios_anteriores = [];
            return;
        }
        this.state.sugerencias = await jsonrpc(
            "/estadisticas-numeros/search_number", { term }
        );
    }

    async seleccionarNumero(ev) {
        ev.preventDefault();
        this.state.numero_text = ev.currentTarget.dataset.name;
        this.state.number_id   = parseInt(ev.currentTarget.dataset.id);
        this.state.sugerencias = [];
        await this.loadSocios();
    }
}

ConsultarAcompanantes.template = "lottery_portal.ConsultarAcompanantes";
registry.category("public_components").add(
    "lottery_portal.ConsultarAcompanantes",
    ConsultarAcompanantes
);
