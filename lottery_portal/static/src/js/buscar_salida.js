/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";

export class SalidasBuscador extends Component {
    setup() {
        this.state = useState({
            fecha: '',
            resultados: null,
        });
    }
    async buscar_salida() {
        if (!this.state.fecha) {
            this.state.resultados = null;
            return;
        }
        const data = await jsonrpc("/salidas/buscar", {
            fecha: this.state.fecha,
        });

        this.state.resultados = data;
    }
}

SalidasBuscador.template = "lottery_portal.SalidasBuscador";

registry.category("public_components").add(
    "lottery_portal.SalidasBuscador",
    SalidasBuscador
);

