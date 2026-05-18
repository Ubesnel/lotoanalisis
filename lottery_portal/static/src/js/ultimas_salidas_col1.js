/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class UltimasSalidasCol1 extends Component {

    setup() {
        this.state = useState({
            salidas: [],
            loading: true,
        });

        onWillStart(async () => {
            const data = await jsonrpc("/lottery/ultimas_salidas_col1", {});
            this.state.salidas = data || [];
            this.state.loading = false;
        });
    }
}

UltimasSalidasCol1.template = "lottery_portal.UltimasSalidasCol1";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasCol1",
    UltimasSalidasCol1
);
