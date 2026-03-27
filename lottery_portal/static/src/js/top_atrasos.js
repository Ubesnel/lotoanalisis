/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class TopAtrasos extends Component {
    setup() {
        this.state = useState({
            type: "general",
            numbers: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top10_atrasos", {
            type: this.state.type,
        });
        this.state.numbers = result;
    }

    async onChangeType(ev) {
        this.state.type = ev.target.value;
        await this.loadData();
    }

}

TopAtrasos.template = "lottery_portal.TopAtrasos";

registry.category("public_components").add("lottery_portal.TopAtrasos",TopAtrasos);