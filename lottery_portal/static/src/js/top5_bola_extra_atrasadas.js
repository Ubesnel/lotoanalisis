/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class Top5BolaExtraAtrasadas extends Component {
    setup() {
        this.state = useState({
            type: "general",
            centenas: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top5_bola_extra", {
            type: this.state.type,
        });
        this.state.centenas = result;
    }

    async onOnchangeTop5BolaExtra(ev) {
        this.state.type = ev.target.value;
        await this.loadData();
    }

}

Top5BolaExtraAtrasadas.template = "lottery_portal.Top5BolaExtraAtrasadas";

registry.category("public_components").add("lottery_portal.Top5BolaExtraAtrasadas",Top5BolaExtraAtrasadas);