/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class Top5CentenasAtrasadas extends Component {
    setup() {
        this.state = useState({
            type: "general",
            centenas: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top5_centenas", {
            type: this.state.type,
        });
        this.state.centenas = result;
    }

    async onOnchangeTop5Centena(ev) {
        this.state.type = ev.target.value;
        await this.loadData();
    }

}

Top5CentenasAtrasadas.template = "lottery_portal.Top5CentenasAtrasadas";

registry.category("public_components").add("lottery_portal.Top5CentenasAtrasadas",Top5CentenasAtrasadas);