/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class TopAtrasosLineas extends Component {
    setup() {
        this.state = useState({
            type_line: "general",
            groups_lines: [],
        });

        this.loadData();
    }

    async loadData() {
        const result = await jsonrpc("/lottery/top_atrasos_lineas", {
            type: this.state.type_line,
        });
        this.state.groups_lines = result;
    }

    async onChangeTypeLineas(ev) {
        this.state.type_line = ev.target.value;
        await this.loadData();
    }

}

TopAtrasosLineas.template = "lottery_portal.TopAtrasosLineas";

registry.category("public_components").add("lottery_portal.TopAtrasosLineas",TopAtrasosLineas);