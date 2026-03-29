/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class TopAtrasosTerminales extends Component {
    setup() {
        this.state = useState({
            type_terminal: "general",
            groups_terminales: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top_atrasos_terminales", {
            type: this.state.type_terminal,
        });
        this.state.groups_terminales = result;
    }

    async onChangeTypeTerminales(ev) {
        this.state.type_terminal = ev.target.value;
        await this.loadData();
    }

}

TopAtrasosTerminales.template = "lottery_portal.TopAtrasosTerminales";

registry.category("public_components").add("lottery_portal.TopAtrasosTerminales",TopAtrasosTerminales);