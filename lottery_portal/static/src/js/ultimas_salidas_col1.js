/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

function todayStr() {
    const d = new Date();
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const yyyy = d.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
}

export class UltimasSalidasCol1 extends Component {

    setup() {
        this.state = useState({
            salidas: [],
            loading: true,
        });

        onWillStart(async () => {
            const data = await jsonrpc("/lottery/ultimas_salidas_col1", {});
            const hoy = todayStr();
            this.state.salidas = (data || []).filter(s => s.fecha !== hoy);
            this.state.loading = false;
        });
    }
}

UltimasSalidasCol1.template = "lottery_portal.UltimasSalidasCol1";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasCol1",
    UltimasSalidasCol1
);
