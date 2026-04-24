/** @odoo-module **/

import { Component, onWillStart, useState} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

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
            bottom_numbers: [],
            remaining_numbers: [],
            top_repeticiones: [],
            top_pegados: [],
            // Por día
            day: daysMap[todayIndex],
            top_numbers_by_week_day: [],
            bottom_numbers_by_week_day: [],
            top_centena_by_week_day: [],
            bottom_centena_by_week_day: [],
            top_bola_extra_by_week_day: [],
            bottom_bola_extra_by_week_day: [],
            // Por semana
            week: this.getCurrentWeek(),
            top_numbers_by_week: [],
            bottom_numbers_by_week: [],
            top_centena_by_week: [],
            bottom_centena_by_week: [],
            top_bola_extra_by_week: [],
            bottom_bola_extra_by_week: [],
            // Acompañantes
            numero_text: '',
            number_id: null,
            sugerencias: [],
            socios_posteriores: [],
            socios_anteriores: [],
            month_index: monthsMap[monthIndex],
            showAllCalientes: false,
            showAllIntermedios: false,
            showAllFrios: false,
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

            const d = this.state.day;
            this.state.top_numbers_by_week_day        = numWeekDay.top[d]              || [];
            this.state.bottom_numbers_by_week_day     = numWeekDay.bottom[d]           || [];
            this.state.top_centena_by_week_day        = centenaWeekDay.top_centena[d]  || [];
            this.state.bottom_centena_by_week_day     = centenaWeekDay.bottom_centena[d] || [];
            this.state.top_bola_extra_by_week_day     = centenaWeekDay.top_bola[d]     || [];
            this.state.bottom_bola_extra_by_week_day  = centenaWeekDay.bottom_bola[d]  || [];

            const w = this.state.week;
            this.state.top_numbers_by_week        = numWeek.top[w]              || [];
            this.state.bottom_numbers_by_week     = numWeek.bottom[w]           || [];
            this.state.top_centena_by_week        = centenaWeek.top_centena[w]  || [];
            this.state.bottom_centena_by_week     = centenaWeek.bottom_centena[w] || [];
            this.state.top_bola_extra_by_week     = centenaWeek.top_bola[w]     || [];
            this.state.bottom_bola_extra_by_week  = centenaWeek.bottom_bola[w]  || [];

            this.state.top_repeticiones = repData.top_repeticiones;
            this.state.top_pegados      = pegData.top_pegados;
        });
    }

    onChangeDia(ev) {
        const d = ev.target.value;
        this.state.day = d;
        this.state.top_numbers_by_week_day        = this._numWeekDay.top[d]              || [];
        this.state.bottom_numbers_by_week_day     = this._numWeekDay.bottom[d]           || [];
        this.state.top_centena_by_week_day        = this._centenaWeekDay.top_centena[d]  || [];
        this.state.bottom_centena_by_week_day     = this._centenaWeekDay.bottom_centena[d] || [];
        this.state.top_bola_extra_by_week_day     = this._centenaWeekDay.top_bola[d]     || [];
        this.state.bottom_bola_extra_by_week_day  = this._centenaWeekDay.bottom_bola[d]  || [];
    }

    onChangeSemana(ev) {
        const w = ev.target.value;
        this.state.week = w;
        this.state.top_numbers_by_week        = this._numWeek.top[w]              || [];
        this.state.bottom_numbers_by_week     = this._numWeek.bottom[w]           || [];
        this.state.top_centena_by_week        = this._centenaWeek.top_centena[w]  || [];
        this.state.bottom_centena_by_week     = this._centenaWeek.bottom_centena[w] || [];
        this.state.top_bola_extra_by_week     = this._centenaWeek.top_bola[w]     || [];
        this.state.bottom_bola_extra_by_week  = this._centenaWeek.bottom_bola[w]  || [];
    }

    toggleCalientes()    { this.state.showAllCalientes    = !this.state.showAllCalientes; }
    toggleIntermedios()  { this.state.showAllIntermedios  = !this.state.showAllIntermedios; }
    toggleFrios()        { this.state.showAllFrios        = !this.state.showAllFrios; }
    toggleRepeticiones() { this.state.showAllRepeticiones = !this.state.showAllRepeticiones; }
    togglePegados()      { this.state.showAllPegados      = !this.state.showAllPegados; }

    getCurrentWeek() {
        const today = new Date().getDate();
        if (today <= 7)  return 'sem_1';
        if (today <= 14) return 'sem_2';
        if (today <= 21) return 'sem_3';
        if (today <= 28) return 'sem_4';
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
        if (i < 5)  return "ball-red";
        if (i < 10) return "ball-blue";
        return "ball-green";
    }

    getBallColdIdx(i) {
        if (i < 5)  return "ball-azul-analitico";
        if (i < 10) return "ball-cian";
        return "ball-grisaceo";
    }

    getBallHotIdx4(i) {
        if (i === 0) return "ball-red";
        if (i < 3)   return "ball-blue";
        return "ball-green";
    }

    getBallColdIdx4(i) {
        if (i === 0) return "ball-azul-analitico";
        if (i < 3)   return "ball-cian";
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
        this.state.sugerencias = await jsonrpc("/estadisticas-numeros/search_number", { term });
    }

    seleccionarNumero(ev) {
        this.state.numero_text = ev.currentTarget.dataset.name;
        this.state.number_id   = parseInt(ev.currentTarget.dataset.id);
        this.state.sugerencias = [];
        this.buscar_por_numero();
    }

    async buscar_por_numero() {
        const data = await jsonrpc("/estadisticas-numeros/numeros-socios", { number_id: this.state.number_id });
        this.state.socios_posteriores = data.salidas_numeros_despues_numero;
        this.state.socios_anteriores  = data.salidas_numeros_antes_numero;
    }
}

LotteryDashboardNumbers.template = "lottery_portal.LotteryDashboardNumbers";
registry.category("public_components").add("lottery_portal.LotteryDashboardNumbers", LotteryDashboardNumbers);
