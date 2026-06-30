/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class Top10ByDay extends Component {

    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};

        this._cache = {};
        this.state = useState({
            day: daysMap[todayIndex],
            numbers: [],
        });

        this.loadData();
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        await ensureSorteoLoaded();
        const result = await jsonrpc("/lottery/top10_by_day_all", { sorteo_id: sorteoState.sorteoId });
        this._cache = result;
        this.state.numbers = result[this.state.day] || [];
    }

    onChangeDay(ev) {
        this.state.day = ev.target.value;
        this.state.numbers = this._cache[ev.target.value] || [];
    }
}

Top10ByDay.template = "lottery_portal.Top10ByDay";

registry.category("public_components").add(
    "lottery_portal.Top10ByDay",
    Top10ByDay
);