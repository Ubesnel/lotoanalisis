/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

function todayStr() {
    const d = new Date();
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
}

export class UltimasSalidasConsecutivas extends Component {

    setup() {
        this.state = useState({
            salidas: [],
            loading: true,
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        const data = await jsonrpc("/lottery/ultimas_salidas_consecutivas", { sorteo_id: sorteoState.sorteoId });
        const hoy = todayStr();
        this.state.salidas = (data || []).filter(s => s.fecha !== hoy);
        this.state.loading = false;
    }
}

UltimasSalidasConsecutivas.template = "lottery_portal.UltimasSalidasConsecutivas";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasConsecutivas",
    UltimasSalidasConsecutivas
);
