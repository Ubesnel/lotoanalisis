/** @odoo-module **/

import { Component, onWillStart, onMounted, useState, useRef} from "@odoo/owl";
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
        });
        this.canvasRef = useRef("chartCanvas");

        onWillStart(async () => {
            await this.loadTop6GroupsData();
            await this.getMonthText();

        });

        onMounted(() => {
            this.chartCanvas = this.canvasRef.el;
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
        this.state.data_general = result;
        setTimeout(() => {
        if (this.canvasRef.el) {
            this.renderChart();
            }
        }, 0);
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

                const labels = ["10-20", "21-30", "31-40", "41-45", "+45"];
                const values = [
                    data.r_10_20 || 0,
                    data.r_21_30 || 0,
                    data.r_31_40 || 0,
                    data.r_41_45 || 0,
                    data.r_45_plus || 0,
                ];

                if (this.chart) {
                    this.chart.destroy();
                }
            this.chart = new Chart(ctx, {
                        type: "line",
                        data: {
        labels,
        datasets: [{
            label: "Atrasos",
            data: values,

            // línea
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            borderColor: "#8c6ca8",
            backgroundColor: "rgba(128, 90, 213, 0.15)",

            // puntos (clave para mobile)
            pointRadius: 6,
            pointHoverRadius: 9,
            pointHitRadius: 20, // 🔥 hace fácil tocar en celular
            pointBackgroundColor: "#8c6ca8",
            pointBorderColor: "#fff",
            pointBorderWidth: 2
        }],
    },
                        options: {
        responsive: true,
        maintainAspectRatio: false,

        // 🔥 UX móvil
        interaction: {
            mode: 'nearest',
            intersect: false,
            axis: 'x'
        },

        plugins: {
            legend: {
                display: false
            },

            tooltip: {
                enabled: true,
                backgroundColor: "#222",
                padding: 10,
                cornerRadius: 6,
                callbacks: {
                    title: (items) => `Intervalo: ${items[0].label}`,
                    label: (ctx) => ` ${ctx.parsed.y} veces`
                }
            },

            // 🔥 labels siempre visibles (clave)
            datalabels: {
                anchor: 'end',
                align: 'top',
                offset: 6,
                clamp: true,
                clip: false,

                formatter: (value) => value > 0 ? value : '',

                color: "#8c6ca8",

                font: (ctx) => {
                    const v = ctx.dataset.data[ctx.dataIndex];
                    return {
                        weight: 'bold',
                        size: 13
                    };
                }
            }
        },

        scales: {
            x: {
                grid: {
                    display: false
                },
                ticks: {
                    maxRotation: 0,
                    autoSkip: false,
                    font: {
                        size: 11
                    }
                }
            },

            y: {
                beginAtZero: true,
                grace: '50%',
                grid: {
                    color: 'rgba(0,0,0,0.05)',
                    drawBorder: false
                },

                ticks: {
                    padding: 6,
                    font: {
                        size: 11
                    }
                }

            }
        },
        animation: {
            duration: 800,
            easing: 'easeOutQuart'
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

    seleccionarGrupo(ev) {
        const id = ev.currentTarget.dataset.id;
        const name = ev.currentTarget.dataset.name;
        this.state.grupo_text = name;
        this.state.select_group_id = parseInt(id);
        this.state.sugerencias_grupos = [];
        this.loadDataGeneralChart(parseInt(id));
        }
}

LotteryDashboardPintas.template = "lottery_portal.LotteryDashboardPintas";

registry.category("public_components").add("lottery_portal.LotteryDashboardPintas", LotteryDashboardPintas);