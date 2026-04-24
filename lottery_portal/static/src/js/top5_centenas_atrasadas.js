/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class Top5CentenasAtrasadas extends Component {
    setup() {
        this._cache = {};
        this.state = useState({
            type_c: "general",
            centenas: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top5_centenas_all", {});
        this._cache = result;
        this.state.centenas = result[this.state.type_c] || [];
    }

    onOnchangeTop5Centena(ev) {
        this.state.type_c = ev.target.value;
        this.state.centenas = this._cache[ev.target.value] || [];
    }

}

Top5CentenasAtrasadas.template = "lottery_portal.Top5CentenasAtrasadas";

registry.category("public_components").add("lottery_portal.Top5CentenasAtrasadas",Top5CentenasAtrasadas);