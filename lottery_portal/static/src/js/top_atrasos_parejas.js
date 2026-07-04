/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class TopAtrasosParejas extends Component {
    setup() {
        this._cache = {};
        this.state = useState({
            type_pareja: "general",
            groups_parejas: [],
        });

        this.loadData();
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        await ensureSorteoLoaded();
        const result = await jsonrpc("/lottery/top_atrasos_parejas_all", { sorteo_id: sorteoState.sorteoId });
        this._cache = result;
        this.state.groups_parejas = result[this.state.type_pareja] || [];
    }

    onChangeTypeParejas(ev) {
        this.state.type_pareja = ev.target.value;
        this.state.groups_parejas = this._cache[ev.target.value] || [];
    }

}

TopAtrasosParejas.template = "lottery_portal.TopAtrasosParejas";

registry.category("public_components").add("lottery_portal.TopAtrasosParejas",TopAtrasosParejas);