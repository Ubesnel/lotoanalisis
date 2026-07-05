/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class GruposPorDia extends Component {
    setup() {
        const todayIndex = new Date().getDay();
        const daysMap    = { 0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa" };
        const dayNames   = { lu: "Lunes", ma: "Martes", mi: "Miércoles", ju: "Jueves",
                             vi: "Viernes", sa: "Sábado", do: "Domingo" };
        const day = daysMap[todayIndex];

        this.state = useState({
            day,
            dayName: dayNames[day],
            groups:    [],
            lines:     [],
            terminals: [],
            openNums:  {},
            loading:   true,
            prob:              null,
            probLoading:       false,
            showProbLineas:    false,
            showProbTerminales: false,
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => {
            this.state.prob = null;
            this.state.showProbLineas = false;
            this.state.showProbTerminales = false;
            this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        const data = await jsonrpc("/grupos-por-dia/dashboard_data", {
            day:       this.state.day,
            sorteo_id: sorteoState.sorteoId,
        });
        this.state.groups    = data.groups    || [];
        this.state.lines     = data.lines     || [];
        this.state.terminals = data.terminals || [];
        this.state.loading   = false;
    }

    toggleNums(key) {
        this.state.openNums[key] = !this.state.openNums[key];
    }

    async _ensureProbLoaded() {
        if (this.state.prob || this.state.probLoading) {
            return;
        }
        this.state.probLoading = true;
        try {
            this.state.prob = await jsonrpc("/grupos-por-dia/probables", {
                sorteo_id: sorteoState.sorteoId,
            });
        } finally {
            this.state.probLoading = false;
        }
    }

    async consultarProbLineas() {
        this.state.showProbLineas = !this.state.showProbLineas;
        if (this.state.showProbLineas) {
            await this._ensureProbLoaded();
        }
    }

    async consultarProbTerminales() {
        this.state.showProbTerminales = !this.state.showProbTerminales;
        if (this.state.showProbTerminales) {
            await this._ensureProbLoaded();
        }
    }

    imgUrl(num) {
        return `/lottery_portal/static/src/img/numeros/${num}.png`;
    }
}

GruposPorDia.template = "lottery_portal.GruposPorDia";
registry.category("public_components").add("lottery_portal.GruposPorDia", GruposPorDia);
