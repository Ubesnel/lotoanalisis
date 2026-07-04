/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class TopAtrasos extends Component {
    setup() {
        this._cache = {};
        this.state = useState({
            type_atraso: "general",
            numbers_atrasos: [],
        });

        this.loadData();
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        await ensureSorteoLoaded();
        const result = await jsonrpc("/lottery/top10_atrasos_all", { sorteo_id: sorteoState.sorteoId });
        this._cache = result;
        this.state.numbers_atrasos = result[this.state.type_atraso] || [];
    }

    onChangeType(ev) {
        this.state.type_atraso = ev.target.value;
        this.state.numbers_atrasos = this._cache[ev.target.value] || [];
    }

}

TopAtrasos.template = "lottery_portal.TopAtrasos";

registry.category("public_components").add("lottery_portal.TopAtrasos",TopAtrasos);