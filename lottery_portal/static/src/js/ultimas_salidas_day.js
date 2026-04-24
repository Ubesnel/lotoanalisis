/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class UltimasSalidasDay extends Component {

    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};

        this._cache = {};
        this.state = useState({
            day_us: daysMap[todayIndex],
            ultimas_salidas: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/ultimas_salidas_by_day_all", {});
        this._cache = result;
        this.state.ultimas_salidas = result[this.state.day_us] || [];
    }

    onChangeUltimasSalidas(ev) {
        this.state.day_us = ev.target.value;
        this.state.ultimas_salidas = this._cache[ev.target.value] || [];
    }
}

UltimasSalidasDay.template = "lottery_portal.UltimasSalidasDay";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasDay",
    UltimasSalidasDay
);