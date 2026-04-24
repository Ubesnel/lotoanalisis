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
            const [
                mainData,
                numWeekDay,
                numWeek,
                centenaWeekDay,
                centenaWeek,
                repData,
                pegData,
            ] = await Promise.all([
                jsonrpc("/estadisticas-numeros/dashboard_data", { month: this.state.month_index }),
                jsonrpc("/estadisticas-numeros/numbers-week-day-all", {}),
                jsonrpc("/estadisticas-numeros/numbers-week-all", {}),
                jsonrpc("/estadisticas-numeros/centena-week-day-all", {}),
                jsonrpc("/estadisticas-numeros/centena-week-all", {}),
                jsonrpc("/estadisticas-numeros/top-repeticiones", {}),
                jsonrpc("/estadisticas-numeros/top-pegados", {}),
            ]);

            this.state.kpis = mainData.kpis;
            this.state.top_numbers = mainData.top_numbers;
            this.state.bottom_numbers = mainData.bottom_numbers;
            this.state.remaining_numbers = mainData.remaining_numbers;
            this.state.loading = false;

            this._numWeekDay = numWeekDay;
            this._numWeek = numWeek;
            this._centenaWeekDay = centenaWeekDay;
            this._centenaWeek = centenaWeek;

            this.state.top_numbers_by_week_day = numWeekDay.top[this.state.day] || [];
            this.state.bottom_numbers_by_week_day = numWeekDay.bottom[this.state.day_menos] || [];
            this.state.top_numbers_by_week = numWeek.top[this.state.week] || [];
            this.state.bottom_numbers_by_week = numWeek.bottom[this.state.week_menos] || [];
            this.state.top_centena_by_week_day = centenaWeekDay.top_centena[this.state.day_centena] || [];
            this.state.bottom_centena_by_week_day = centenaWeekDay.bottom_centena[this.state.day_menos_centena] || [];
            this.state.top_centena_by_week = centenaWeek.top_centena[this.state.week_centena] || [];
            this.state.bottom_centena_by_week = centenaWeek.bottom_centena[this.state.week_menos_centena] || [];
            this.state.top_bola_extra_by_week_day = centenaWeekDay.top_bola[this.state.day_bola_extra] || [];
            this.state.bottom_bola_extra_by_week_day = centenaWeekDay.bottom_bola[this.state.day_menos_bola_extra] || [];
            this.state.top_bola_extra_by_week = centenaWeek.top_bola[this.state.week_bola_extra] || [];
            this.state.bottom_bola_extra_by_week = centenaWeek.bottom_bola[this.state.week_menos_bola_extra] || [];

            this.state.top_repeticiones = repData.top_repeticiones;
            this.state.top_pegados = pegData.top_pegados;
        });
    }

    onTopNumbersWeekDay(ev) {
        this.state.day = ev.target.value;
        this.state.top_numbers_by_week_day = this._numWeekDay.top[ev.target.value] || [];
    }

    onBottomNumbersWeekDay(ev) {
        this.state.day_menos = ev.target.value;
        this.state.bottom_numbers_by_week_day = this._numWeekDay.bottom[ev.target.value] || [];
    }

    onTopNumbersWeek(ev) {
        this.state.week = ev.target.value;
        this.state.top_numbers_by_week = this._numWeek.top[ev.target.value] || [];
    }

    onBottomNumbersWeek(ev) {
        this.state.week_menos = ev.target.value;
        this.state.bottom_numbers_by_week = this._numWeek.bottom[ev.target.value] || [];
    }

    onTopCentenaWeekDay(ev) {
        this.state.day_centena = ev.target.value;
        this.state.top_centena_by_week_day = this._centenaWeekDay.top_centena[ev.target.value] || [];
    }

    onBottomCentenaWeekDay(ev) {
        this.state.day_menos_centena = ev.target.value;
        this.state.bottom_centena_by_week_day = this._centenaWeekDay.bottom_centena[ev.target.value] || [];
    }

    onTopCentenaWeek(ev) {
        this.state.week_centena = ev.target.value;
        this.state.top_centena_by_week = this._centenaWeek.top_centena[ev.target.value] || [];
    }

    onBottomCentenaWeek(ev) {
        this.state.week_menos_centena = ev.target.value;
        this.state.bottom_centena_by_week = this._centenaWeek.bottom_centena[ev.target.value] || [];
    }

    onTopBolaExtraWeekDay(ev) {
        this.state.day_bola_extra = ev.target.value;
        this.state.top_bola_extra_by_week_day = this._centenaWeekDay.top_bola[ev.target.value] || [];
    }

    onBottomBolaExtraWeekDay(ev) {
        this.state.day_menos_bola_extra = ev.target.value;
        this.state.bottom_bola_extra_by_week_day = this._centenaWeekDay.bottom_bola[ev.target.value] || [];
    }

    onTopBolaExtraWeek(ev) {
        this.state.week_bola_extra = ev.target.value;
        this.state.top_bola_extra_by_week = this._centenaWeek.top_bola[ev.target.value] || [];
    }

    onBottomBolaExtraWeek(ev) {
        this.state.week_menos_bola_extra = ev.target.value;
        this.state.bottom_bola_extra_by_week = this._centenaWeek.bottom_bola[ev.target.value] || [];
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

    getTotalSalidasMes(numbers) {
        return numbers.reduce((sum, n) => sum + (n.salidas_mes_anio || 0), 0);
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