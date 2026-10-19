/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";

// Cada cuánto se vuelve a pedir el día cuando se está mirando "hoy".
const REFRESCO_MS = 60000;

/**
 * Portada: resultados de todas las loterías habilitadas para la web en una
 * fecha (hoy por defecto), agrupados por país y turno, con el buscador por
 * fecha integrado. Quiniela Uruguaya llega como una sola lotería con sus 20
 * premios y la Tómbola.
 */
export class BuscadorPublico extends Component {
    setup() {
        this.state = useState({
            data: null,
            fecha: "",
            pais: "todos",
            cargando: false,
            error: false,
        });
        this.timer = null;

        onWillStart(() => this.cargar(""));
        onMounted(() => {
            this.timer = setInterval(() => {
                if (this.state.data && this.state.data.es_hoy && !document.hidden) {
                    this.cargar(this.state.fecha, true);
                }
            }, REFRESCO_MS);
        });
        onWillUnmount(() => clearInterval(this.timer));
    }

    /** Pide un día al servidor. `silencioso` no muestra el "cargando". */
    async cargar(fecha, silencioso = false) {
        if (!silencioso) {
            this.state.cargando = true;
        }
        try {
            const data = await jsonrpc("/salidas/dia", { fecha: fecha || false });
            this.state.data = data;
            this.state.fecha = data.fecha;
            this.state.error = false;
            // Si el país elegido no tiene loterías ese día, vuelve a "todos".
            if (
                this.state.pais !== "todos" &&
                !data.paises.some((p) => p.codigo === this.state.pais)
            ) {
                this.state.pais = "todos";
            }
        } catch (e) {
            if (!silencioso) {
                this.state.error = true;
            }
        } finally {
            this.state.cargando = false;
        }
    }

    get paises() {
        const todos = (this.state.data && this.state.data.paises) || [];
        return this.state.pais === "todos"
            ? todos
            : todos.filter((p) => p.codigo === this.state.pais);
    }

    get esHoy() {
        return !!(this.state.data && this.state.data.es_hoy);
    }

    onFecha(ev) {
        if (ev.target.value) {
            this.cargar(ev.target.value);
        }
    }

    /** Mueve la fecha `dias` días (±1) a partir de la que se está viendo. */
    mover(dias) {
        const [a, m, d] = this.state.fecha.split("-").map(Number);
        const f = new Date(a, m - 1, d + dias);
        const iso = [
            f.getFullYear(),
            String(f.getMonth() + 1).padStart(2, "0"),
            String(f.getDate()).padStart(2, "0"),
        ].join("-");
        this.cargar(iso);
    }

    irAHoy() {
        this.cargar("");
    }

    setPais(codigo) {
        this.state.pais = codigo;
    }

    /** Filas de una lista repartida en 2 columnas (20 → 10 + 10). */
    filas(n) {
        return Math.max(1, Math.ceil(n / 2));
    }

    /** Hay dato para mostrar: el 0 es una centena / bola extra válida. */
    tiene(valor) {
        return valor !== null && valor !== undefined && valor !== "" && valor !== "-";
    }

    /** Fondo de la bola con el color del turno (o el violeta de la marca). */
    bolaStyle(color) {
        const c = color || "#7B2FF7";
        return `background: radial-gradient(circle at 35% 30%, color-mix(in srgb, ${c} 55%, white), ${c} 70%);`;
    }
}

BuscadorPublico.template = "lottery_portal.BuscadorPublico";

registry.category("public_components").add(
    "lottery_portal.BuscadorPublico",
    BuscadorPublico
);
