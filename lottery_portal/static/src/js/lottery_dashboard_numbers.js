/** @odoo-module **/

import { Component, onWillStart, useState, useRef, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { Tooltip } from "@web/core/tooltip/tooltip";

export class LotteryDashboardNumbers extends Component {
    setup() {
        const root = useRef("root");
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        this.state = useState({
            loading: true,
            kpis: {},
            top_numbers: [],
            bottom_numbers: [],
            top_numbers_by_week_day: [],
            top_numbers_by_week: [],
            bottom_numbers_by_week_day: [],
            bottom_numbers_by_week: [],
            day: daysMap[todayIndex],
            day_menos: daysMap[todayIndex],
            week: this.getCurrentWeek(),
            week_menos: this.getCurrentWeek(),
            numero_text: '',
            number_id: null,
            sugerencias: [],
            socios_posteriores: [],
            socios_anteriores: [],
        });

        onWillStart(async () => {
            await this.loadData();
            await this.loadDataTopNumbersWeekDay();
            await this.loadDataTopNumbersWeek();
            await this.loadDataBottomNumbersWeekDay();
            await this.loadDataBottomNumbersWeek();
        });

        const initTooltips = () => {
            const el = root.el;
            if (!el) return;
            el.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((node) => {
            if (node._tooltip) {
                node._tooltip.dispose();
            }
            node._tooltip = new Tooltip(node);
            });
        };

        onMounted(initTooltips);
        onPatched(initTooltips);
    }


    async loadData() {
        const data = await jsonrpc("/estadisticas-numeros/dashboard_data", {});
        this.state.kpis = data.kpis;
        this.state.top_numbers = data.top_numbers;
        this.state.bottom_numbers = data.bottom_numbers;
        this.state.loading = false;
    }

    async loadDataTopNumbersWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/top-number-week-day", {
            day: this.state.day
        });
        this.state.top_numbers_by_week_day = data.top_numbers_by_week_day;
    }

    async loadDataBottomNumbersWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-number-week-day", {
            day: this.state.day_menos
        });
        this.state.bottom_numbers_by_week_day = data.bottom_numbers_by_week_day;
    }

    async loadDataTopNumbersWeek() {
        const data = await jsonrpc("/estadisticas-numeros/top-number-week", {
        week: this.state.week,
        });
        this.state.top_numbers_by_week = data.top_numbers_by_week;
    }

    async loadDataBottomNumbersWeek() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-number-week", {
        week: this.state.week_menos,
        });
        this.state.bottom_numbers_by_week = data.bottom_numbers_by_week;
    }

    getCurrentWeek() {
        const today = new Date().getDate();
        if (today >= 1 && today <= 7) return 'sem_1';
        if (today >= 8 && today <= 14) return 'sem_2';
        if (today >= 15 && today <= 21) return 'sem_3';
        if (today >= 22 && today <= 28) return 'sem_4';
        return 'sem_5';
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

    async onTopNumbersWeekDay(ev) {
        this.state.day = ev.target.value;
        await this.loadDataTopNumbersWeekDay();
    }

    async onTopNumbersWeek(ev) {
        this.state.week = ev.target.value;
        await this.loadDataTopNumbersWeek();
    }

    async onBottomNumbersWeekDay(ev) {
        this.state.day_menos = ev.target.value;
        await this.loadDataBottomNumbersWeekDay();
    }

    async onBottomNumbersWeek(ev) {
        this.state.week_menos = ev.target.value;
        await this.loadDataBottomNumbersWeek();
    }

    async onBuscarNumero(ev) {
        const term = ev.target.value;
        this.state.numero_text = term;
        if (!term) {
            this.state.sugerencias = [];
            this.state.socios_posteriores = [];
            this.state.socios_anteriores = [];
            return;
        }
        const data = await jsonrpc("/estadisticas-numeros/search_number", {
            term: term
        });
        this.state.sugerencias = data;
    }

    seleccionarNumero(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.numero_text = name;
        this.state.number_id = parseInt(id);
        this.state.sugerencias = [];
        this.buscar_por_numero();
        }

    async buscar_por_numero() {
        const data = await jsonrpc("/estadisticas-numeros/numeros-socios", {
            number_id: this.state.number_id
        });
        this.state.socios_posteriores = data.salidas_numeros_despues_numero;
        this.state.socios_anteriores = data.salidas_numeros_antes_numero;
    }
}

LotteryDashboardNumbers.template = "lottery_portal.LotteryDashboardNumbers";

registry.category("public_components").add("lottery_portal.LotteryDashboardNumbers", LotteryDashboardNumbers);