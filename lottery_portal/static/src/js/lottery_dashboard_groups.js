/** @odoo-module **/

import { Component, onWillStart, onMounted, useState, useRef} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class LotteryDashboardGroups extends Component {
    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        const monthsMap = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12};
        const monthIndex = new Date().getMonth();
        const fecha = new Date().getDate();
        const week = Math.ceil(fecha / 7);
        this.state = useState({
            top_6_groups_info: [],
            get_top_3_pintas: [],
            month_index: monthsMap[monthIndex],
            day_index: daysMap[todayIndex],
            week_index: week,
            openGroups: {},
            groupNumbers: {},
            group_type_atraso: "general",
            group_type_atraso_pinta: "general",
            openGroupsAnalysis: {},
            openGroupsAnalysisPinta: {},
            analysisGroups: {},
            analysisGroupsPintas: {},
            mesActual: "",
            data_general: {},
            data_general_pinta: {},
            select_group_id: null,
            grupo_text: '',
            sugerencias_grupos: [],
            select_pinta_id: null,
            pinta_text: '',
            sugerencias_pintas: [],
        });
        this.canvasRef = useRef("chartCanvas");
        this.canvasRefPintas = useRef("chartCanvasPintas");

        onWillStart(async () => {
            await this.loadTop6GroupsData();
            await this.loadTop3GroupsDataPinta();
            await this.getMonthText();

        });

        onMounted(() => {
            this.chartCanvas = this.canvasRef.el;
            this.chartCanvasPintas = this.canvasRefPintas.el;
        });
    }

    async loadTop6GroupsData() {
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data", {
            group_type: this.state.group_type_atraso,
            day: this.state.day_index,
            week: this.state.week_index,
            month: this.state.month_index
        });
        this.state.top_6_groups_info = data.top_6_groups_info;
        this.state.analysisGroups = data.groups_analysis;
    }

    async loadTop3GroupsDataPinta() {
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data_pintas", {
            group_type: this.state.group_type_atraso_pinta,
            day: this.state.day_index,
            week: this.state.week_index,
            month: this.state.month_index
        });
        this.state.get_top_3_pintas = data.get_top_3_pintas;
        this.state.analysisGroupsPintas = data.groups_analysis;

    }

    async loadDataGeneralChart(select_group_id) {
        const result = await jsonrpc("/lottery/get_data_chart_general", {
            group_id: select_group_id,
        });
        this.state.data_general = result;
        this.renderChart();
    }

    async loadDataGeneralChartPinta(select_pinta_id) {
        const result = await jsonrpc("/lottery/get_data_chart_general_pinta", {
            group_id: select_pinta_id,
        });
        this.state.data_general_pinta = result;
        this.renderChartPinta();
    }


    renderChart() {
                if (!this.canvasRef.el) {
                    console.log("canvas no listo");
                    return;
                }

                const ctx = this.canvasRef.el.getContext("2d");

                const data = this.state.data_general;

                if (!data || !Object.keys(data).length) {
                    console.log("sin data");
                    return;
                }

                const labels = ["21-40", "41-50", "51-60", "61-70", "+70"];
                const values = [
                    data.r_21_40 || 0,
                    data.r_41_50 || 0,
                    data.r_51_60 || 0,
                    data.r_61_70 || 0,
                    data.r_70_plus || 0,
                ];

                if (this.chart) {
                    this.chart.destroy();
                }

                this.chart = new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels,
                        datasets: [{
                            label: "Cantidad de veces que se ha atrasado en el intervalo",
                            data: values,
                            backgroundColor: [
                                "#4cd964",
                                "#4cd964",
                                "orange",
                                "#ff4d4d",
                                "#ff4d4d",
                            ],
                            borderRadius: 6,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 0
                                }
                            },
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });
    }

    renderChartPinta() {
                if (!this.canvasRefPintas.el) {
                    console.log("canvas no listo");
                    return;
                }

                const ctx = this.canvasRefPintas.el.getContext("2d");

                const data = this.state.data_general_pinta;

                if (!data || !Object.keys(data).length) {
                    console.log("sin data");
                    return;
                }

                const labels = ["10-20", "21-30", "31-35", "36-40", "+40"];
                const values = [
                    data.r_10_20 || 0,
                    data.r_21_30 || 0,
                    data.r_31_35 || 0,
                    data.r_36_40 || 0,
                    data.r_40_plus || 0,
                ];

                if (this.chart_pintas) {
                    this.chart_pintas.destroy();
                }

                this.chart_pintas = new Chart(ctx, {
                    type: "bar",
                    data: {
                        labels,
                        datasets: [{
                            label: "Cantidad de veces que se ha atrasado en el intervalo",
                            data: values,
                            backgroundColor: [
                                "#4cd964",
                                "#4cd964",
                                "orange",
                                "#ff4d4d",
                                "#ff4d4d",
                            ],
                            borderRadius: 6,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: false
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 0
                                }
                            },
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
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

    async onChangeGroupTypeAtraso(ev) {
        this.state.group_type_atraso = ev.target.value;
        await this.loadTop6GroupsData();
    }

    async onChangeGroupTypeAtrasoPinta(ev) {
        this.state.group_type_atraso_pinta = ev.target.value;
        await this.loadTop3GroupsDataPinta();
    }

    async toggleGroupsAnalysis(groupId) {
        this.state.openGroupsAnalysis[groupId] = !this.state.openGroupsAnalysis[groupId];
        this.render();
    }

    async toggleGroupsAnalysisPinta(groupId) {
        this.state.openGroupsAnalysisPinta[groupId] = !this.state.openGroupsAnalysisPinta[groupId];
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
            this.state.data_general = {};
            return;
        }
        const data = await jsonrpc("/estadisticas-grupos/search_grupos", {
            term: term
        });
        this.state.sugerencias_grupos = data;
    }

    async onBuscarPinta(ev) {
        const term = ev.target.value;
        this.state.pinta_text = term;
        if (!term) {
            this.state.data_general_pinta = {};
            return;
        }
        const data = await jsonrpc("/estadisticas-grupos/search_pintas", {
            term: term
        });
        this.state.sugerencias_pintas = data;
    }

    seleccionarGrupo(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.grupo_text = name;
        this.state.select_grupo_id = parseInt(id);
        this.state.sugerencias_grupos = [];
        this.loadDataGeneralChart(parseInt(id));
        }

    seleccionarPinta(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.pinta_text = name;
        this.state.select_pinta_id = parseInt(id);
        this.state.sugerencias_pintas = [];
        this.loadDataGeneralChartPinta(parseInt(id));
        }
}

LotteryDashboardGroups.template = "lottery_portal.LotteryDashboardGroups";

registry.category("public_components").add("lottery_portal.LotteryDashboardGroups", LotteryDashboardGroups);