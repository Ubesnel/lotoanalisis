/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, useState, useRef} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";


export class LotteryDashboardPintas extends Component {
    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        const monthsMap = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12};
        const monthIndex = new Date().getMonth();
        const fecha = new Date().getDate();
        const week = Math.ceil(fecha / 7);
        this.state = useState({
            top_6_groups_info: [],
            top_6_groups_info_tarde: [],
            top_6_groups_info_noche: [],
            month_index: monthsMap[monthIndex],
            day_index: daysMap[todayIndex],
            week_index: week,
            openGroups: {},
            groupNumbers: {},
            openGroupsAnalysis: {},
            analysisGroups: {},
            analysisGroupsTarde: {},
            analysisGroupsNoche: {},
            mesActual: "",
            data_general: null,
            select_group_id: null,
            grupo_text: '',
            sugerencias_grupos: [],
            data_tarde: null,
            select_group_tarde_id: null,
            grupo_text_tarde: '',
            sugerencias_grupos_tarde: [],
            data_noche: null,
            select_group_noche_id: null,
            grupo_text_noche: '',
            sugerencias_grupos_noche: [],
        });
        this.canvasRef = useRef("chartCanvas");
        this.canvasRefTarde = useRef("chartCanvasTarde");
        this.canvasRefNoche = useRef("chartCanvasNoche");

        this._pendingCharts = { general: false, tarde: false, noche: false };

        onPatched(() => {
            if (this._pendingCharts.general && this.canvasRef.el) {
                this._pendingCharts.general = false;
                this.renderChart();
            }
            if (this._pendingCharts.tarde && this.canvasRefTarde.el) {
                this._pendingCharts.tarde = false;
                this.renderChartTarde();
            }
            if (this._pendingCharts.noche && this.canvasRefNoche.el) {
                this._pendingCharts.noche = false;
                this.renderChartNoche();
            }
        });

        onWillStart(async () => {
            await this.loadTop6GroupsData();
            await this.getMonthText();

        });

        onMounted(() => {
            this.chartCanvas = this.canvasRef.el;
            this.chartCanvasTarde = this.canvasRefTarde.el;
            this.chartCanvasNoche = this.canvasRefNoche.el;
        });
    }

    async loadTop6GroupsData() {
        const data = await jsonrpc("/estadisticas-pintas/dashboard_data", {
            day: this.state.day_index,
            week: this.state.week_index,
            month: this.state.month_index
        });
        this.state.top_6_groups_info = data.get_top_3_pintas;
        this.state.top_6_groups_info_tarde = data.get_top_3_pintas_tarde;
        this.state.top_6_groups_info_noche = data.get_top_3_pintas_noche;
        this.state.analysisGroups = data.groups_analysis;
        this.state.analysisGroupsTarde = data.groups_analysis_tarde;
        this.state.analysisGroupsNoche = data.groups_analysis_noche;
    }

    async loadDataGeneralChart(select_group_id) {
        const result = await jsonrpc("/lottery/get_data_chart_general_pinta", {
            group_id: select_group_id,
        });
        this._pendingCharts.general = true;
        this.state.data_general = result;
    }

    async loadDataGeneralChartTarde(select_group_tarde_id) {
        const result = await jsonrpc("/lottery/get_data_chart_tarde_pinta", {
            group_id: select_group_tarde_id,
        });
        this._pendingCharts.tarde = true;
        this.state.data_tarde = result;
    }

    async loadDataGeneralChartNoche(select_group_noche_id) {
        const result = await jsonrpc("/lottery/get_data_chart_noche_pinta", {
            group_id: select_group_noche_id,
        });
        this._pendingCharts.noche = true;
        this.state.data_noche = result;
    }

    _buildChartOptions(tooltipBg, labelColor) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'nearest', intersect: false, axis: 'x' },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: tooltipBg,
                    titleColor: "#fff",
                    bodyColor: "rgba(255,255,255,0.85)",
                    padding: 10,
                    cornerRadius: 8,
                    callbacks: {
                        title: (items) => `Intervalo: ${items[0].label}`,
                        label: (ctx) => ` ${ctx.parsed.y} veces`
                    }
                },
                datalabels: {
                    anchor: 'end',
                    align: 'top',
                    offset: 3,
                    clamp: true,
                    clip: false,
                    formatter: (value) => value > 0 ? value : '',
                    color: labelColor,
                    font: { weight: 'bold', size: 12 },
                    backgroundColor: "rgba(255,255,255,0.75)",
                    borderRadius: 4,
                    padding: { top: 2, bottom: 2, left: 5, right: 5 }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    border: { display: false },
                    ticks: { maxRotation: 0, autoSkip: false, font: { size: 11, weight: '600' }, color: labelColor }
                },
                y: {
                    beginAtZero: true,
                    grace: '25%',
                    grid: { color: 'rgba(0,0,0,0.04)' },
                    border: { display: false },
                    ticks: { padding: 4, font: { size: 10 }, color: '#bbb' }
                }
            },
            animation: { duration: 900, easing: 'easeOutCubic' }
        };
    }

    renderChart() {
                if (!this.canvasRef.el) return;
                const ctx = this.canvasRef.el.getContext("2d");
                const data = this.state.data_general;
                if (!data || !Object.keys(data).length) return;
                if (this.chart) this.chart.destroy();

                const labels = ["10-20", "21-30", "31-40", "41-45", "+45"];
                const values = [
                    data.r_10_20 || 0,
                    data.r_21_30 || 0,
                    data.r_31_40 || 0,
                    data.r_41_45 || 0,
                    data.r_45_plus || 0,
                ];
                const h = this.canvasRef.el.getBoundingClientRect().height || 250;
                const grad = ctx.createLinearGradient(0, 0, 0, h);
                grad.addColorStop(0, "rgba(140,108,168,0.85)");
                grad.addColorStop(1, "rgba(111,74,142,0.25)");
                this.chart = new Chart(ctx, {
                    type: "bar",
                    data: { labels, datasets: [{ label: "Atrasos", data: values, backgroundColor: grad, borderColor: "#6f4a8e", borderWidth: 1.5, borderRadius: 8, borderSkipped: false }] },
                    options: this._buildChartOptions("rgba(74,44,110,0.92)", "#6f4a8e")
                });
    }

    renderChartTarde() {
                if (!this.canvasRefTarde.el) return;
                const ctx = this.canvasRefTarde.el.getContext("2d");
                const data = this.state.data_tarde;
                if (!data || !Object.keys(data).length) return;
                if (this.chart_tarde) this.chart_tarde.destroy();

                const labels = ["10-20", "21-30", "31-40", "41-45", "+45"];
                const values = [
                    data.r_10_20 || 0,
                    data.r_21_30 || 0,
                    data.r_31_40 || 0,
                    data.r_41_45 || 0,
                    data.r_45_plus || 0,
                ];
                const h = this.canvasRefTarde.el.getBoundingClientRect().height || 250;
                const grad = ctx.createLinearGradient(0, 0, 0, h);
                grad.addColorStop(0, "rgba(245,158,11,0.85)");
                grad.addColorStop(1, "rgba(217,119,6,0.25)");
                this.chart_tarde = new Chart(ctx, {
                    type: "bar",
                    data: { labels, datasets: [{ label: "Atrasos", data: values, backgroundColor: grad, borderColor: "#d97706", borderWidth: 1.5, borderRadius: 8, borderSkipped: false }] },
                    options: this._buildChartOptions("rgba(180,90,0,0.92)", "#b45309")
                });
    }

    renderChartNoche() {
                if (!this.canvasRefNoche.el) return;
                const ctx = this.canvasRefNoche.el.getContext("2d");
                const data = this.state.data_noche;
                if (!data || !Object.keys(data).length) return;
                if (this.chart_noche) this.chart_noche.destroy();

                const labels = ["10-20", "21-30", "31-40", "41-45", "+45"];
                const values = [
                    data.r_10_20 || 0,
                    data.r_21_30 || 0,
                    data.r_31_40 || 0,
                    data.r_41_45 || 0,
                    data.r_45_plus || 0,
                ];
                const h = this.canvasRefNoche.el.getBoundingClientRect().height || 250;
                const grad = ctx.createLinearGradient(0, 0, 0, h);
                grad.addColorStop(0, "rgba(45,90,142,0.85)");
                grad.addColorStop(1, "rgba(30,58,95,0.25)");
                this.chart_noche = new Chart(ctx, {
                    type: "bar",
                    data: { labels, datasets: [{ label: "Atrasos", data: values, backgroundColor: grad, borderColor: "#1e3a5f", borderWidth: 1.5, borderRadius: 8, borderSkipped: false }] },
                    options: this._buildChartOptions("rgba(20,40,70,0.92)", "#1e3a5f")
                });
    }

    async toggleGroupNumber(type, groupId, groupOrden) {
        const key = `${type}_${groupId}`;
        this.state.openGroups[key] = !this.state.openGroups[key];
        if (this.state.groupNumbers[key]) {
            return;
        }
        const result = await jsonrpc('/lottery/get_group_numbers', {
            group_id: groupId,
            orden: groupOrden,
            day: this.state.day_index
        });
        this.state.groupNumbers[key] = result;
    }

    async toggleGroupsAnalysis(type,groupId) {
        const key = `${type}_${groupId}`;
        this.state.openGroupsAnalysis[key] = !this.state.openGroupsAnalysis[key];
        this.render();
    }

    async getMonthText() {
        const result = await jsonrpc("/lottery/get_month_text", {
            month: this.state.month_index
        });
        this.state.mesActual = result;
        }

    async onBuscarGrupo(ev) {
        const term = ev.target.value;
        this.state.grupo_text = term;

        if (!term) {
            // 🔥 limpiar todo
                this.state.select_group_id = null;
                this.state.data_general = null;
                this.state.sugerencias_grupos = [];
                // opcional: destruir chart si existe
                if (this.chart) {
                    this.chart.destroy();
                    this.chart = null;
                }
                return;
            }

        const data = await jsonrpc("/estadisticas-grupos/search_pintas", {
            term: term
        });
        this.state.sugerencias_grupos = data;
    }
    async onBuscarGrupoTarde(ev) {
        const term = ev.target.value;
        this.state.grupo_text_tarde = term;

        if (!term) {
            // 🔥 limpiar todo
                this.state.select_group_tarde_id = null;
                this.state.data_tarde = null;
                this.state.sugerencias_grupos_tarde = [];
                // opcional: destruir chart si existe
                if (this.chart_tarde) {
                    this.chart_tarde.destroy();
                    this.chart_tarde = null;
                }
                return;
            }

        const data = await jsonrpc("/estadisticas-grupos/search_pintas", {
            term: term
        });
        this.state.sugerencias_grupos_tarde = data;
    }

    async onBuscarGrupoNoche(ev) {
        const term = ev.target.value;
        this.state.grupo_text_noche = term;

        if (!term) {
            // 🔥 limpiar todo
                this.state.select_group_noche_id = null;
                this.state.data_noche = null;
                this.state.sugerencias_grupos_noche = [];
                // opcional: destruir chart si existe
                if (this.chart_noche) {
                    this.chart_noche.destroy();
                    this.chart_noche = null;
                }
                return;
            }

        const data = await jsonrpc("/estadisticas-grupos/search_pintas", {
            term: term
        });
        this.state.sugerencias_grupos_noche = data;
    }


    seleccionarGrupo(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.grupo_text = name;
        this.state.select_group_id = parseInt(id);
        this.state.sugerencias_grupos = [];
        this.loadDataGeneralChart(parseInt(id));
        }

    seleccionarGrupoTarde(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.grupo_text_tarde = name;
        this.state.select_group_tarde_id = parseInt(id);
        this.state.sugerencias_grupos_tarde = [];
        this.loadDataGeneralChartTarde(parseInt(id));
        }
    seleccionarGrupoNoche(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.grupo_text_noche = name;
        this.state.select_group_noche_id = parseInt(id);
        this.state.sugerencias_grupos_noche = [];
        this.loadDataGeneralChartNoche(parseInt(id));
        }
}

LotteryDashboardPintas.template = "lottery_portal.LotteryDashboardPintas";

registry.category("public_components").add("lottery_portal.LotteryDashboardPintas", LotteryDashboardPintas);