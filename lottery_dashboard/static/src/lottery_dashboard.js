/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, onMounted, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const REFRESCO_MS = 60000;

function esOscuro() {
    const rgb = getComputedStyle(document.body).backgroundColor.match(/\d+/g) || [255, 255, 255];
    const [r, g, b] = rgb.map(Number);
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
}

function paleta() {
    const dark = esOscuro();
    return dark
        ? {
              s1: "#3987e5", s2: "#d95926", s3: "#199e70", s4: "#c98500",
              s1Fuerte: "#8ab8f2", s1Suave: "#24497a",
              texto: "#c3c2b7", grilla: "rgba(255,255,255,0.08)", superficie: "#1a1a19",
          }
        : {
              s1: "#2a78d6", s2: "#eb6834", s3: "#1baf7a", s4: "#eda100",
              s1Fuerte: "#164a8a", s1Suave: "#a9c8ef",
              texto: "#52514e", grilla: "rgba(0,0,0,0.06)", superficie: "#fcfcfb",
          };
}

function baseOpciones(p, extra = {}) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: "index", intersect: false },
        plugins: {
            legend: { display: false, labels: { color: p.texto, boxWidth: 10, boxHeight: 10 } },
            tooltip: { padding: 8 },
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: p.texto }, border: { display: false } },
            y: {
                beginAtZero: true,
                grid: { color: p.grilla },
                ticks: { color: p.texto, precision: 0 },
                border: { display: false },
            },
        },
        ...extra,
    };
}

/** Lienzo de Chart.js: recrea el gráfico cuando cambia `config`. */
class DashChart extends Component {
    static template = "lottery_dashboard.Chart";
    static props = { config: Object, height: { type: Number, optional: true } };

    setup() {
        this.canvas = useRef("canvas");
        this.chart = null;
        useEffect(
            () => {
                this.chart = new window.Chart(this.canvas.el, this.props.config);
                return () => this.chart && this.chart.destroy();
            },
            () => [this.props.config]
        );
    }
}

export class LotteryDashboard extends Component {
    static template = "lottery_dashboard.Main";
    static components = { DashChart };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            date: null,
            periodo: "day",
            corridos: false,
            cargando: false,
            filtroTareas: "open",
            filtroPred: "all",
            repSel: null,
        });
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.cargar();
        });
        onMounted(() => {
            this.timer = setInterval(() => {
                if (this.state.data && this.state.data.es_hoy && !document.hidden) {
                    this.cargar();
                }
            }, REFRESCO_MS);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    async cargar() {
        this.state.cargando = true;
        try {
            const data = await this.orm.call("lottery.dashboard", "get_dashboard_data", [], {
                date: this.state.date,
                periodo: this.state.periodo,
                corridos: this.state.corridos,
            });
            this.charts = this.armarGraficos(data);
            this.state.date = data.date;
            this.state.data = data;
        } finally {
            this.state.cargando = false;
        }
    }

    // ── Navegación ──────────────────────────────────────────────────────

    moverDia(delta) {
        const d = luxon.DateTime.fromISO(this.state.date).plus({ days: delta });
        this.state.date = d.toISODate();
        this.cargar();
    }
    irHoy() {
        this.state.date = null;
        this.cargar();
    }
    onFecha(ev) {
        if (ev.target.value) {
            this.state.date = ev.target.value;
            this.cargar();
        }
    }
    setPeriodo(p) {
        this.state.periodo = p;
        this.cargar();
    }
    setFiltro(campo, valor) {
        this.state[campo] = valor;
    }
    toggleCorridos() {
        this.state.corridos = !this.state.corridos;
        this.cargar();
    }

    get fechaLarga() {
        const d = luxon.DateTime.fromISO(this.state.date);
        return `${DIAS[d.weekday % 7]} ${d.toFormat("dd/MM/yyyy")}`;
    }

    // ── Derivados para la plantilla ─────────────────────────────────────

    get tareasFiltradas() {
        const lista = this.state.data.tareas.lista;
        if (this.state.filtroTareas === "open") {
            return lista.filter((t) => t.state !== "done");
        }
        if (this.state.filtroTareas === "all") {
            return lista;
        }
        return lista.filter((t) => t.state === this.state.filtroTareas);
    }

    get filasPred() {
        const filas = this.state.data.predicciones.filas;
        if (this.state.filtroPred === "pending") {
            return filas.filter((f) => !f.completo);
        }
        return filas;
    }

    pct(n, total) {
        return total ? Math.round((n * 100) / total) : 0;
    }

    etiquetaPred(estado) {
        return { published: "Publicada", draft: "Borrador", missing: "Falta" }[estado];
    }

    iconoPred(estado) {
        return { published: "fa-check", draft: "fa-pencil", missing: "fa-times" }[estado];
    }

    donde(rep) {
        return rep.donde.map((x) => `${x.sorteo} ${x.turno}`.trim()).join("
");
    }

    digitos(lista) {
        return lista.length ? lista.join(" · ") : "—";
    }

    // ── Aperturas ───────────────────────────────────────────────────────

    irKpi(clave) {
        const fecha = this.state.date;
        const ahora = luxon.DateTime.utc().toFormat("yyyy-MM-dd HH:mm:ss");
        const destinos = {
            tareas: ["Tareas del día", "calendar.event", [["lottery_sorteo_id", "!=", false], ["lottery_date", "=", fecha]], "list,calendar"],
            normales: ["Predicciones normales", "lottery.prediction", [["date", "=", fecha]], "list"],
            premium: ["Predicciones Premium", "lottery.prediction.premium", [["date", "=", fecha]], "list"],
            pases: ["Premium activos", "lottery.premium.pass",
                [["state", "in", ["active", "grace", "canceled"]], ["is_test", "=", false],
                    "|", ["expiry_date", "=", false], ["expiry_date", ">", ahora]], "list"],
            consultas: ["Consultas a la API", "lottery.api.log", [], "list"],
        };
        const [name, res_model, domain, vistas] = destinos[clave];
        this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model,
            domain,
            views: vistas.split(",").map((v) => [false, v]).concat([[false, "form"]]),
            target: "current",
        });
    }

    abrirTarea(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "calendar.event",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    abrirPrediccion(model, id) {
        if (!id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    abrirAlerta(a) {
        const accion = {
            type: "ir.actions.act_window",
            res_model: a.model,
            name: a.titulo,
            target: "current",
        };
        if (a.res_id) {
            Object.assign(accion, { res_id: a.res_id, views: [[false, "form"]] });
        } else {
            Object.assign(accion, { domain: [["id", "in", a.ids]], views: [[false, "list"], [false, "form"]] });
        }
        this.action.doAction(accion);
    }

    abrirRegalo(id) {
        this.abrirPrediccion("lottery.premium.gift", id);
    }

    // ── Gráficos ────────────────────────────────────────────────────────

    barrasDigitos(serie, p, nombre) {
        const max = Math.max(...serie.valores);
        const min = Math.min(...serie.valores);
        const colores = serie.valores.map((v) =>
            max && v === max ? p.s1Fuerte : max && v === min ? p.s1Suave : p.s1
        );
        return {
            type: "bar",
            data: {
                labels: [...Array(10).keys()].map(String),
                datasets: [
                    {
                        label: nombre,
                        data: serie.valores,
                        backgroundColor: colores,
                        borderRadius: 4,
                        borderSkipped: "start",
                        maxBarThickness: 28,
                    },
                ],
            },
            options: baseOpciones(p, {
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { title: (it) => `${nombre} ${it[0].label}` } },
                },
            }),
        };
    }

    barrasHorizontales(items, p, etiqueta, color) {
        return {
            type: "bar",
            data: {
                labels: items.map((i) => i.name),
                datasets: [
                    {
                        label: etiqueta,
                        data: items.map((i) => i.count),
                        backgroundColor: color,
                        borderRadius: 4,
                        borderSkipped: "start",
                        maxBarThickness: 18,
                    },
                ],
            },
            options: baseOpciones(p, {
                indexAxis: "y",
                interaction: { mode: "nearest", axis: "y", intersect: false },
                scales: {
                    x: { beginAtZero: true, grid: { color: p.grilla }, ticks: { color: p.texto, precision: 0 }, border: { display: false } },
                    y: { grid: { display: false }, ticks: { color: p.texto }, border: { display: false } },
                },
            }),
        };
    }

    armarGraficos(data) {
        const p = paleta();
        const n = data.numeros;
        const r = data.regalos;
        const c = data.consultas;
        const charts = {
            lineas: this.barrasDigitos(n.lineas, p, "Línea"),
            terminales: this.barrasDigitos(n.terminales, p, "Terminal"),
            pintas: this.barrasDigitos(n.pintas, p, "Pinta"),
        };
        const apilado = (extra) =>
            baseOpciones(p, {
                plugins: {
                    legend: { display: true, position: "bottom", labels: { color: p.texto, boxWidth: 10, boxHeight: 10 } },
                },
                ...extra,
            });
        const seg = { borderColor: p.superficie, borderWidth: { right: 2, top: 2 }, borderSkipped: false };
        charts.regalosPais = {
            type: "bar",
            data: {
                labels: r.paises.map((x) => x.pais),
                datasets: [
                    { label: "Sin canjear", data: r.paises.map((x) => x.available), backgroundColor: p.s1, ...seg },
                    { label: "Canjeados", data: r.paises.map((x) => x.redeemed), backgroundColor: p.s3, ...seg },
                    { label: "Vencidos / anulados", data: r.paises.map((x) => x.expired), backgroundColor: p.s2, ...seg },
                ],
            },
            options: apilado({
                indexAxis: "y",
                interaction: { mode: "index", axis: "y", intersect: false },
                scales: {
                    x: { stacked: true, beginAtZero: true, grid: { color: p.grilla }, ticks: { color: p.texto, precision: 0 }, border: { display: false } },
                    y: { stacked: true, grid: { display: false }, ticks: { color: p.texto }, border: { display: false } },
                },
            }),
        };
        const seg2 = { borderColor: p.superficie, borderWidth: { top: 2 }, borderSkipped: false, maxBarThickness: 16 };
        charts.regalosRecientes = {
            type: "bar",
            data: {
                labels: r.recientes.dias.map((d) => d.slice(8, 10) + "/" + d.slice(5, 7)),
                datasets: [
                    { label: "Comprados", data: r.recientes.purchase, backgroundColor: p.s1, ...seg2 },
                    { label: "Cortesía", data: r.recientes.courtesy, backgroundColor: p.s2, ...seg2 },
                    { label: "Prueba gratis", data: r.recientes.trial, backgroundColor: p.s3, ...seg2 },
                ],
            },
            options: apilado({
                scales: {
                    x: { stacked: true, grid: { display: false }, ticks: { color: p.texto, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }, border: { display: false } },
                    y: { stacked: true, beginAtZero: true, grid: { color: p.grilla }, ticks: { color: p.texto, precision: 0 }, border: { display: false } },
                },
            }),
        };
        if (c.disponible) {
            charts.consultasSorteo = this.barrasHorizontales(c.sorteos, p, "Consultas", p.s1);
            charts.consultasPais = this.barrasHorizontales(c.paises, p, "Consultas", p.s1);
            charts.consultasHora = {
                type: "line",
                data: {
                    labels: [...Array(24).keys()].map((h) => String(h).padStart(2, "0")),
                    datasets: [
                        {
                            label: "Consultas",
                            data: c.por_hora,
                            borderColor: p.s1,
                            backgroundColor: p.s1 + "22",
                            fill: true,
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                        },
                    ],
                },
                options: baseOpciones(p, {
                    plugins: {
                        legend: { display: false },
                        tooltip: { callbacks: { title: (it) => `${it[0].label}:00 h` } },
                    },
                }),
            };
        }
        return charts;
    }
}

registry.category("actions").add("lottery_dashboard.main", LotteryDashboard);
