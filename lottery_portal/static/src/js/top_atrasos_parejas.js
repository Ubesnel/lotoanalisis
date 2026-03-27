/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class TopAtrasosParejas extends Component {
    setup() {
        this.state = useState({
            type: "general",
            groups: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top_atrasos_parejas", {
            type: this.state.type,
        });
        this.state.groups = result;
    }

    async onChangeTypeParejas(ev) {
        this.state.type = ev.target.value;
        await this.loadData();
    }

}

TopAtrasosParejas.template = "lottery_portal.TopAtrasosParejas";

registry.category("public_components").add("lottery_portal.TopAtrasosParejas",TopAtrasosParejas);