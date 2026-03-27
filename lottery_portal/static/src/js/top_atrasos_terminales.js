/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class TopAtrasosTerminales extends Component {
    setup() {
        this.state = useState({
            type: "general",
            groups: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top_atrasos_terminales", {
            type: this.state.type,
        });
        this.state.groups = result;
    }

    async onChangeTypeTerminales(ev) {
        this.state.type = ev.target.value;
        await this.loadData();
    }

}

TopAtrasosTerminales.template = "lottery_portal.TopAtrasosTerminales";

registry.category("public_components").add("lottery_portal.TopAtrasosTerminales",TopAtrasosTerminales);