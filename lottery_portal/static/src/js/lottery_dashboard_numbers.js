/** @odoo-module **/

import { Component, onWillStart, useState} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { Tooltip } from "@web/core/tooltip/tooltip";

export class LotteryDashboardNumbers extends Component {
    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        const monthsMap = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12};
        const monthIndex = new Date().getMonth();
        this.state = useState({
            loading: true,
            kpis: {},
            top_numbers: [],
            top_repeticiones: [],
            top_pegados: [],
            bottom_numbers: [],
            remaining_numbers: [],
            top_numbers_by_week_day: [],
            top_numbers_by_week: [],
            bottom_numbers_by_week_day: [],
            bottom_numbers_by_week: [],
            top_centena_by_week_day: [],
            top_centena_by_week: [],
            bottom_centena_by_week_day: [],
            bottom_centena_by_week: [],
            top_bola_extra_by_week_day: [],
            top_bola_extra_by_week: [],
            bottom_bola_extra_by_week_day: [],
            bottom_bola_extra_by_week: [],
            day: daysMap[todayIndex],
            day_menos: daysMap[todayIndex],
            day_menos_centena: daysMap[todayIndex],
            day_menos_bola_extra: daysMap[todayIndex],
            day_centena: daysMap[todayIndex],
            day_bola_extra: daysMap[todayIndex],
            week: this.getCurrentWeek(),
            week_centena: this.getCurrentWeek(),
            week_bola_extra: this.getCurrentWeek(),
            week_menos: this.getCurrentWeek(),
            week_menos_centena: this.getCurrentWeek(),
            week_menos_bola_extra: this.getCurrentWeek(),
            numero_text: '',
            number_id: null,
            sugerencias: [],
            socios_posteriores: [],
            socios_anteriores: [],
            month_index: monthsMap[monthIndex],
            showAllRepeticiones: false,
            showAllPegados: false,
        });

        onWillStart(async () => {
            await this.loadData();
            await this.loadDataTopNumbersWeekDay();
            await this.loadDataTopNumbersWeek();
            await this.loadDataBottomNumbersWeekDay();
            await this.loadDataBottomNumbersWeek();
            await this.loadDataTopCentenaWeekDay();
            await this.loadDataTopCentenaWeek();
            await this.loadDataBottomCentenaWeekDay();
            await this.loadDataBottomCentenaWeek();
            await this.loadDataTopBolaExtraWeekDay();
            await this.loadDataTopBolaExtraWeek();
            await this.loadDataBottomBolaExtraWeekDay();
            await this.loadDataBottomBolaExtraWeek();
            await this.loadDataTopRepeticiones();
            await this.loadDataTopPegados();
        });
    }

    async loadData() {
        const data = await jsonrpc("/estadisticas-numeros/dashboard_data", {
            month: this.state.month_index
        });
        this.state.kpis = data.kpis;
        this.state.top_numbers = data.top_numbers;
        this.state.bottom_numbers = data.bottom_numbers;
        this.state.remaining_numbers = data.remaining_numbers;
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

    async loadDataTopCentenaWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/top-centena-week-day", {
            day: this.state.day_centena, field: 'hundreds_id'
        });
        this.state.top_centena_by_week_day = data.top_info_by_week_day;
    }

    async loadDataBottomCentenaWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-centena-week-day", {
            day: this.state.day_menos_centena, field: 'hundreds_id'
        });
        this.state.bottom_centena_by_week_day = data.bottom_info_by_week_day;
    }

    async loadDataTopCentenaWeek() {
        const data = await jsonrpc("/estadisticas-numeros/top-centena-week", {
        week: this.state.week_centena, field: 'hundreds_id'
        });
        this.state.top_centena_by_week = data.top_info_by_week;
    }

    async loadDataBottomCentenaWeek() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-centena-week", {
        week: this.state.week_menos_centena, field: 'hundreds_id'
        });
        this.state.bottom_centena_by_week = data.bottom_info_by_week;
    }

    async loadDataTopBolaExtraWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/top-centena-week-day", {
            day: this.state.day_bola_extra, field: 'fireball_id'
        });
        this.state.top_bola_extra_by_week_day = data.top_info_by_week_day;
    }

    async loadDataBottomBolaExtraWeekDay() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-centena-week-day", {
            day: this.state.day_menos_bola_extra, field: 'fireball_id'
        });
        this.state.bottom_bola_extra_by_week_day = data.bottom_info_by_week_day;
    }

    async loadDataTopBolaExtraWeek() {
        const data = await jsonrpc("/estadisticas-numeros/top-centena-week", {
        week: this.state.week_bola_extra, field: 'fireball_id'
        });
        this.state.top_bola_extra_by_week = data.top_info_by_week;
    }

    async loadDataBottomBolaExtraWeek() {
        const data = await jsonrpc("/estadisticas-numeros/bottom-centena-week", {
        week: this.state.week_menos_bola_extra, field: 'fireball_id'
        });
        this.state.bottom_bola_extra_by_week = data.bottom_info_by_week;
    }

    async loadDataTopRepeticiones() {
        const data = await jsonrpc("/estadisticas-numeros/top-repeticiones", {});
        this.state.top_repeticiones = data.top_repeticiones;
    }

    async loadDataTopPegados() {
        const data = await jsonrpc("/estadisticas-numeros/top-pegados", {});
        this.state.top_pegados = data.top_pegados;
    }

    toggleRepeticiones() {
        this.state.showAllRepeticiones = !this.state.showAllRepeticiones;
    }

    togglePegados() {
        this.state.showAllPegados = !this.state.showAllPegados;
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

    getBallHotIdx(i) {
        if (i < 5) return "ball-red";
        if (i < 10) return "ball-blue";
        return "ball-green";
    }

    getBallColdIdx(i) {
        if (i < 5) return "ball-azul-analitico";
        if (i < 10) return "ball-cian";
        return "ball-grisaceo";
    }

    getBallHotIdx4(i) {
        if (i === 0) return "ball-red";
        if (i < 3) return "ball-blue";
        return "ball-green";
    }

    getBallColdIdx4(i) {
        if (i === 0) return "ball-azul-analitico";
        if (i < 3) return "ball-cian";
        return "ball-grisaceo";
    }

    getBallIdx10(i) {
        if (i < 3) return "ball-red";
        if (i < 7) return "ball-blue";
        return "ball-green";
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

    async onTopCentenaWeekDay(ev) {
        this.state.day_centena = ev.target.value;
        await this.loadDataTopCentenaWeekDay();
    }

    async onTopCentenaWeek(ev) {
        this.state.week_centena = ev.target.value;
        await this.loadDataTopCentenaWeek();
    }

    async onBottomCentenaWeekDay(ev) {
        this.state.day_menos_centena = ev.target.value;
        await this.loadDataBottomCentenaWeekDay();
    }

    async onBottomCentenaWeek(ev) {
        this.state.week_menos_centena = ev.target.value;
        await this.loadDataBottomCentenaWeek();
    }

    async onTopBolaExtraWeekDay(ev) {
        this.state.day_bola_extra = ev.target.value;
        await this.loadDataTopBolaExtraWeekDay();
    }

    async onTopBolaExtraWeek(ev) {
        this.state.week_bola_extra = ev.target.value;
        await this.loadDataTopBolaExtraWeek();
    }

    async onBottomBolaExtraWeekDay(ev) {
        this.state.day_menos_bola_extra = ev.target.value;
        await this.loadDataBottomBolaExtraWeekDay();
    }

    async onBottomBolaExtraWeek(ev) {
        this.state.week_menos_bola_extra = ev.target.value;
        await this.loadDataBottomBolaExtraWeek();
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