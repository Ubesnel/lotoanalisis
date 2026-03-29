/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class LotteryDashboardNumbers extends Component {
    setup() {
        this.state = useState({
            loading: true,
            kpis: {},
            top_numbers: [],
            bottom_numbers: [],
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const data = await jsonrpc("/estadisticas-numeros/dashboard_data", {});
        this.state.kpis = data.kpis;
        this.state.top_numbers = data.top_numbers;
        this.state.bottom_numbers = data.bottom_numbers;
        this.state.loading = false;
    }

    getBallClass(rank) {
        if (rank <= 10) return "ball-red";
        if (rank <= 20) return "ball-blue";
        return "ball-green";
    }

    getBallFriosClass(rank) {
        if (rank <= 10) return "ball-azul-analitico";
        if (rank <= 20) return "ball-cian";
        return "ball-grisaceo";
    }
}

LotteryDashboardNumbers.template = "lottery_portal.LotteryDashboardNumbers";

registry.category("public_components").add("lottery_portal.LotteryDashboardNumbers", LotteryDashboardNumbers);