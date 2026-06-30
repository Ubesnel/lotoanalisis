/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class UltimasSalidasDay extends Component {

    setup() {
        const todayIndex = new Date().getDay();
        const daysMap   = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        const labelsMap = {
            0: "Domingo", 1: "Lunes", 2: "Martes", 3: "Miércoles",
            4: "Jueves",  5: "Viernes", 6: "Sábado",
        };

        this.todayKey = daysMap[todayIndex];

        this.state = useState({
            day_label:      labelsMap[todayIndex],
            ultimas_salidas: [],
        });

        this.loadData();
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        await ensureSorteoLoaded();
        const result = await jsonrpc("/lottery/ultimas_salidas_by_day", { day: this.todayKey, sorteo_id: sorteoState.sorteoId });
        this.state.ultimas_salidas = result || [];
    }
}

UltimasSalidasDay.template = "lottery_portal.UltimasSalidasDay";

registry.category("public_components").add(
    "lottery_portal.UltimasSalidasDay",
    UltimasSalidasDay
);