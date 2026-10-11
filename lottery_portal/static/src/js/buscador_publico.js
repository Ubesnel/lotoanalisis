/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";
import { registry } from "@web/core/registry";

export class BuscadorPublico extends Component {
    setup() {
        this.state = useState({
            sorteos: [],
            sorteoId: null,
            fecha: '',
            resultados: null,
            cargando: false,
            // Últimas salidas del sorteo: se muestran mientras no se elige fecha.
            ultimas: [],
        });

        onWillStart(async () => {
            try {
                const data = await jsonrpc("/lottery/sorteos-publicos", {});
                this.state.sorteos = data.sorteos || [];
                this.state.sorteoId = data.default_id || null;
            } catch (e) {
                this.state.sorteos = [];
            }
            await this.cargarUltimas();
            await this.precargarFecha();
        });
    }

    /**
     * Arranca con la fecha de la última salida registrada ya elegida, así el
     * input nunca queda vacío mostrando resultados. Si el sorteo todavía no
     * tiene salidas, queda vacío y no se muestra nada.
     */
    async precargarFecha() {
        const ultima = this.state.ultimas[this.state.ultimas.length - 1];
        await this.consultar(ultima ? ultima.fecha_iso : '');
    }

    async cargarUltimas() {
        if (!this.state.sorteoId) {
            this.state.ultimas = [];
            return;
        }
        try {
            this.state.ultimas = await jsonrpc("/salidas/ultimas", {
                sorteo_id: this.state.sorteoId,
                limit: 2,
            }) || [];
        } catch (e) {
            this.state.ultimas = [];
        }
    }

    async onSorteoChange(ev) {
        this.state.sorteoId = parseInt(ev.target.value) || null;
        this.state.fecha = '';
        this.state.resultados = null;
        await this.cargarUltimas();
        await this.precargarFecha();
    }

    /**
     * Hay dato para mostrar. Ojo: el 0 es una centena / bola extra válida;
     * solo "-" (o vacío) significa que esa salida no la tiene.
     */
    tiene(valor) {
        return valor !== null && valor !== undefined && valor !== false && valor !== "-" && valor !== "";
    }

    /**
     * Salidas de la fecha elegida, una por turno y ya en orden del día: el
     * servidor las devuelve con la misma forma que las últimas salidas.
     */
    get resultadosLista() {
        return this.state.resultados || [];
    }

    async buscarSalida(ev) {
        await this.consultar(ev.target.value);
    }

    async consultar(fecha) {
        this.state.fecha = fecha || '';
        if (!this.state.fecha || !this.state.sorteoId) {
            this.state.resultados = null;
            return;
        }
        this.state.cargando = true;
        try {
            const data = await jsonrpc("/salidas/buscar", {
                fecha: this.state.fecha,
                sorteo_id: this.state.sorteoId,
            });
            this.state.resultados = data;
        } catch (e) {
            this.state.resultados = null;
        } finally {
            this.state.cargando = false;
        }
    }
}

BuscadorPublico.template = "lottery_portal.BuscadorPublico";

registry.category("public_components").add(
    "lottery_portal.BuscadorPublico",
    BuscadorPublico
);
