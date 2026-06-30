/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class UltimosResultados extends Component {
    setup() {
        this.state = useState({
            afternoon: false,
            evening: false,
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        const data = await jsonrpc("/lottery/ultimos-resultados", { sorteo_id: sorteoState.sorteoId });
        this.state.afternoon = data.afternoon || false;
        this.state.evening = data.evening || false;
    }
}

UltimosResultados.template = "lottery_portal.UltimosResultados";

registry.category("public_components").add(
    "lottery_portal.UltimosResultados",
    UltimosResultados
);
