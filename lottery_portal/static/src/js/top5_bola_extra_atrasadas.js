/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class Top5BolaExtraAtrasadas extends Component {
    setup() {
        this._cache = {};
        this.state = useState({
            type_be: "general",
            bolas_extras: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top5_bola_extra_all", {});
        this._cache = result;
        this.state.bolas_extras = result[this.state.type_be] || [];
    }

    onOnchangeTop5BolaExtra(ev) {
        this.state.type_be = ev.target.value;
        this.state.bolas_extras = this._cache[ev.target.value] || [];
    }

}

Top5BolaExtraAtrasadas.template = "lottery_portal.Top5BolaExtraAtrasadas";

registry.category("public_components").add("lottery_portal.Top5BolaExtraAtrasadas",Top5BolaExtraAtrasadas);