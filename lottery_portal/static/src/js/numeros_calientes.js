/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { sorteoState, ensureSorteoLoaded, onSorteoChange } from "./sorteo_state";

export class NumerosCalientes extends Component {
    setup() {
        this.state = useState({
            turn: "afternoon",
            data: { afternoon: { numbers: [], centenas: [], bola_extra: [] },
                    evening:   { numbers: [], centenas: [], bola_extra: [] } },
            loading: true,
            showHot:       true,
            showCold:      true,
            showRemaining: true,
            imgView: "",   // "hot" | "cold" | "remaining" | ""
        });

        this.TURN_LABELS = { afternoon: "☀ Tarde", evening: "🌙 Noche" };

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        const res = await jsonrpc("/lottery/calientes-next", { sorteo_id: sorteoState.sorteoId });
        // Solo el próximo turno a jugarse (el opuesto al último registrado).
        this.state.turn = res?.turn || "afternoon";
        this.state.data = { [this.state.turn]: res?.data || {} };
        this.state.loading = false;
    }

    get turnLabel()   { return this.TURN_LABELS[this.state.turn] || ""; }
    get usesFireball() { return !!this.current.uses_fireball; }
    // Ausente = sorteo con centena (comportamiento histórico de Florida/NY).
    get usesHundreds() { return this.current.uses_hundreds !== false; }

    // Calcula rank (por score) + clase de color de cada ítem según su posición
    // en el ranking original, y luego los ordena de menor a mayor por valor.
    // Así se muestran ordenados numéricamente sin perder color ni ranking.
    _prep(list, clsFn) {
        return (list || [])
            .map((it, i) => ({ ...it, rank: i + 1, cls: clsFn(i) }))
            .sort((a, b) => Number(a.name) - Number(b.name));
    }

    get current()                { return this.state.data[this.state.turn]; }

    get numbers()          { return this._prep(this.current.numbers,           i => i < 10 ? 'nc-ball-hot'  : i < 20 ? 'nc-ball-warm' : 'nc-ball-cool'); }
    get numbersRemaining() { return this._prep(this.current.numbers_remaining, i => i < 10 ? 'nc-ball-rem1' : i < 20 ? 'nc-ball-rem2' : i < 30 ? 'nc-ball-rem3' : 'nc-ball-rem4'); }
    get numbersCold()      { return this._prep(this.current.numbers_cold,      i => i < 10 ? 'nc-ball-cold1': i < 20 ? 'nc-ball-cold2': 'nc-ball-cold3'); }

    // Bloques por posición en el ranking (score descendente): los primeros
    // fijos de 10, el último absorbe el resto (varía con los empates).
    // Dentro de cada bloque se muestran ordenados de menor a mayor.
    _blocks(list, ballCls, pipCls) {
        const max = ballCls.length;
        const blocks = ballCls.map(() => []);
        (list || []).forEach((it, i) => {
            const b = Math.min(Math.floor(i / 10), max - 1);
            blocks[b].push({ ...it, rank: i + 1, cls: ballCls[b] });
        });
        return blocks
            .map((nums, idx) => ({
                n: idx + 1,
                pip: pipCls[idx],
                numbers: nums.sort((a, b) => Number(a.name) - Number(b.name)),
            }))
            .filter(blk => blk.numbers.length);
    }

    get hotBlocks() {
        return this._blocks(this.current.numbers,
            ['nc-ball-hot', 'nc-ball-warm', 'nc-ball-cool'],
            ['nc-pip--hot', 'nc-pip--warm', 'nc-pip--cool']);
    }
    get coldBlocks() {
        return this._blocks(this.current.numbers_cold,
            ['nc-ball-cold1', 'nc-ball-cold2', 'nc-ball-cold3'],
            ['nc-pip--cold1', 'nc-pip--cold2', 'nc-pip--cold3']);
    }
    get remainingBlocks() {
        return this._blocks(this.current.numbers_remaining,
            ['nc-ball-rem1', 'nc-ball-rem2', 'nc-ball-rem3', 'nc-ball-rem4'],
            ['nc-pip--rem1', 'nc-pip--rem2', 'nc-pip--rem3', 'nc-pip--rem4']);
    }

    get centenas()         { return this._prep(this.current.centenas,          i => i === 0 ? 'nc-badge-ceb--hot' : i < 3 ? 'nc-badge-ceb--warm' : 'nc-badge-ceb--cool'); }
    get centenasRemaining(){ return this._prep(this.current.centenas_remaining,i => i === 0 ? 'nc-badge-ceb--rem1' : 'nc-badge-ceb--rem2'); }
    get centenasCold()     { return this._prep(this.current.centenas_cold,     i => i === 0 ? 'nc-badge-ceb--cold1': i < 3 ? 'nc-badge-ceb--cold2': 'nc-badge-ceb--cold3'); }

    get bolaExtra()         { return this._prep(this.current.bola_extra,          i => i === 0 ? 'nc-badge-ceb--hot' : i < 3 ? 'nc-badge-ceb--warm' : 'nc-badge-ceb--cool'); }
    get bolaExtraRemaining(){ return this._prep(this.current.bola_extra_remaining,i => i === 0 ? 'nc-badge-ceb--rem1' : 'nc-badge-ceb--rem2'); }
    get bolaExtraCold()     { return this._prep(this.current.bola_extra_cold,     i => i === 0 ? 'nc-badge-ceb--cold1': i < 3 ? 'nc-badge-ceb--cold2': 'nc-badge-ceb--cold3'); }

    get nextDraw()               { return this.current.next_draw            || ''; }

    toggleHot()       { this.state.showHot       = !this.state.showHot;       }
    toggleCold()      { this.state.showCold      = !this.state.showCold;      }
    toggleRemaining() { this.state.showRemaining = !this.state.showRemaining; }

    // ── Vista de imágenes ──
    get selectedImgNumbers() {
        if (this.state.imgView === "hot")       return this.numbers;
        if (this.state.imgView === "cold")      return this.numbersCold;
        if (this.state.imgView === "remaining") return this.numbersRemaining;
        return [];
    }

    get imageLines() {
        const grouped = {};
        for (const num of this.selectedImgNumbers) {
            const line = Math.floor(Number(num.name) / 10);
            if (!grouped[line]) grouped[line] = [];
            grouped[line].push(num);
        }
        return Object.keys(grouped)
            .sort((a, b) => Number(a) - Number(b))
            .map(line => ({
                line: Number(line),
                label: `Línea ${line} (${String(Number(line) * 10).padStart(2, '0')} al ${String(Number(line) * 10 + 9).padStart(2, '0')})`,
                numbers: grouped[line].sort((a, b) => Number(a.name) - Number(b.name)),
            }));
    }

    setImgView(ev) { this.state.imgView = ev.target.value; }
}

NumerosCalientes.template = "lottery_portal.NumerosCalientes";
registry.category("public_components").add("lottery_portal.NumerosCalientes", NumerosCalientes);
