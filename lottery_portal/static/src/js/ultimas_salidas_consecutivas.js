/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class UltimasSalidasConsecutivas extends Component {

    setup() {
        this.state = useState({
            salidas: [],
            loading: true,
        });

        onWillStart(async () => {
            const data = await jsonrpc("/lottery/ultimas_salidas_consecutivas", {});
            this.state.salidas = data || [];
            this.state.loading = false;
        });
    }
}

UltimasSalidasConsecutivas.template = "lottery_portal.UltimasSalidasConsecutivas";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasConsecutivas",
    UltimasSalidasConsecutivas
);
