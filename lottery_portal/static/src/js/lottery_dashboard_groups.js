/** @odoo-module **/

import { Component, onWillStart, onMounted, onPatched, useState, useRef} from "@odoo/owl";
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
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data", {
            day: this.state.day_index,
            week: this.state.week_index,
            month: this.state.month_index
        });
        this.state.top_6_groups_info = data.top_6_groups_info;
        this.state.top_6_groups_info_tarde = data.top_6_groups_info_tarde;
        this.state.top_6_groups_info_noche = data.top_6_groups_info_noche;
        this.state.analysisGroups = data.groups_analysis;
        this.state.analysisGroupsTarde = data.groups_analysis_tarde;
        this.state.analysisGroupsNoche = data.groups_analysis_noche;
    }

    async loadDataGeneralChart(select_group_id) {
        const result = await jsonrpc("/lottery/get_data_chart_general", {
            group_id: select_group_id,
        });
        this._pendingCharts.general = true;
        this.state.data_general = result;
    }

    async loadDataGeneralChartTarde(select_group_tarde_id) {
        const result = await jsonrpc("/lottery/get_data_chart_tarde", {
            group_id: select_group_tarde_id,
        });
        this._pendingCharts.tarde = true;
        this.state.data_tarde = result;
    }

    async loadDataGeneralChartNoche(select_group_noche_id) {
        const result = await jsonrpc("/lottery/get_data_chart_noche", {
            group_id: select_group_noche_id,
        });
        this._pendingCharts.noche = true;
        this.state.data_noche = result;
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

    renderChartTarde() {
                if (!this.canvasRefTarde.el) {
                    console.log("canvas no listo");
                    return;
                }

                const ctx = this.canvasRefTarde.el.getContext("2d");

                const data = this.state.data_tarde;

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

                if (this.chart_tarde) {
                    this.chart_tarde.destroy();
                }
            this.chart_tarde = new Chart(ctx, {
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
            borderColor: "#f59e0b",
            backgroundColor: "rgba(255, 219, 187, 1)",

            // puntos (clave para mobile)
            pointRadius: 6,
            pointHoverRadius: 9,
            pointHitRadius: 20, // 🔥 hace fácil tocar en celular
            pointBackgroundColor: "#f59e0b",
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

                color: "#f59e0b",

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

    renderChartNoche() {
                if (!this.canvasRefNoche.el) {
                    console.log("canvas no listo");
                    return;
                }

                const ctx = this.canvasRefNoche.el.getContext("2d");

                const data = this.state.data_noche;

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

                if (this.chart_noche) {
                    this.chart_noche.destroy();
                }
            this.chart_noche = new Chart(ctx, {
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
            borderColor: "#1e3a5f",
            backgroundColor: "rgba(186, 196, 209, 1)",

            // puntos (clave para mobile)
            pointRadius: 6,
            pointHoverRadius: 9,
            pointHitRadius: 20, // 🔥 hace fácil tocar en celular
            pointBackgroundColor: "#1e3a5f",
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

                color: "#1e3a5f",

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
        const data = await jsonrpc("/estadisticas-grupos/search_grupos", {
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
        const data = await jsonrpc("/estadisticas-grupos/search_grupos", {
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
        const data = await jsonrpc("/estadisticas-grupos/search_grupos", {
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

LotteryDashboardGroups.template = "lottery_portal.LotteryDashboardGroups";

registry.category("public_components").add("lottery_portal.LotteryDashboardGroups", LotteryDashboardGroups);