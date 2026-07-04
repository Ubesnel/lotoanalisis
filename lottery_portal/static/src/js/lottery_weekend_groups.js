/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class LotteryWeekendGroups extends Component {
    setup() {
        this._cache = { line: {}, terminal: {} };
        this.state = useState({
            turn: "general",
            data: { line: {}, terminal: {} },
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        const data = await jsonrpc("/lottery/weekend-groups", { sorteo_id: sorteoState.sorteoId });
        this._cache = data || this._cache;
        this.state.data = this._cache;
    }

    get lines()     { return this.state.data.line?.[this.state.turn]     || []; }
    get terminals() { return this.state.data.terminal?.[this.state.turn] || []; }

    onChangeTurn(ev) { this.state.turn = ev.target.value; }
}

LotteryWeekendGroups.template = "lottery_portal.LotteryWeekendGroups";
registry.category("public_components").add("lottery_portal.LotteryWeekendGroups", LotteryWeekendGroups);
