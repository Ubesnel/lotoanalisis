/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class Top10ByDay extends Component {

    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};

        this.state = useState({
            day: daysMap[todayIndex],
            numbers: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top10_by_day", {
            day: this.state.day,
        });
        this.state.numbers = result;
    }

    async onChangeDay(ev) {
        this.state.day = ev.target.value;
        await this.loadData();
    }
}

Top10ByDay.template = "lottery_portal.Top10ByDay";

registry.category("public_components").add(
    "lottery_portal.Top10ByDay",
    Top10ByDay
);