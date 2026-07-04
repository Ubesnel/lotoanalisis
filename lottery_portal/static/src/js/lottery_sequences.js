/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class LotteryGroupSequences extends Component {
    setup() {
        this._cache = { line: [], terminal: [] };
        this.state = useState({
            turn: "general",
            data: { line: [], terminal: [] },
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        const data = await jsonrpc("/lottery/group-sequences", { sorteo_id: sorteoState.sorteoId });
        this._cache = data || this._cache;
        this.state.data = this._cache;
    }

    get lineRows()     { return this.state.data.line     || []; }
    get terminalRows() { return this.state.data.terminal || []; }

    topFor(row) { return row[this.state.turn] || []; }

    onChangeTurn(ev) { this.state.turn = ev.target.value; }
}

LotteryGroupSequences.template = "lottery_portal.LotteryGroupSequences";
registry.category("public_components").add("lottery_portal.LotteryGroupSequences", LotteryGroupSequences);
