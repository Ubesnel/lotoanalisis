/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class TopAtrasosLineas extends Component {
    setup() {
        this._cache = {};
        this.state = useState({
            type_line: "general",
            groups_lines: [],
        });

        this.loadData();
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        await ensureSorteoLoaded();
        const result = await jsonrpc("/lottery/top_atrasos_lineas_all", { sorteo_id: sorteoState.sorteoId });
        this._cache = result;
        this.state.groups_lines = result[this.state.type_line] || [];
    }

    onChangeTypeLineas(ev) {
        this.state.type_line = ev.target.value;
        this.state.groups_lines = this._cache[ev.target.value] || [];
    }

}

TopAtrasosLineas.template = "lottery_portal.TopAtrasosLineas";

registry.category("public_components").add("lottery_portal.TopAtrasosLineas",TopAtrasosLineas);