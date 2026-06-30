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
        });

        onWillStart(async () => {
            await ensureSorteoLoaded();
            await this.loadData();
        });
        onSorteoChange(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        const data = await jsonrpc("/lottery/calientes-all", { sorteo_id: sorteoState.sorteoId });
        this.state.data = data || this.state.data;
        this.state.turn = data?.last_turn === "afternoon" ? "evening" : "afternoon";
        this.state.loading = false;
    }

    get current()                { return this.state.data[this.state.turn]; }
    get numbers()                { return this.current.numbers              || []; }
    get centenas()               { return this.current.centenas             || []; }
    get bolaExtra()              { return this.current.bola_extra           || []; }
    get numbersCold()            { return this.current.numbers_cold         || []; }
    get centenasCold()           { return this.current.centenas_cold        || []; }
    get bolaExtraCold()          { return this.current.bola_extra_cold      || []; }
    get numbersRemaining()       { return this.current.numbers_remaining    || []; }
    get centenasRemaining()      { return this.current.centenas_remaining   || []; }
    get bolaExtraRemaining()     { return this.current.bola_extra_remaining || []; }
    get nextDraw()               { return this.current.next_draw            || ''; }

    onChangeTurn(ev)  { this.state.turn = ev.target.value; }
    toggleHot()       { this.state.showHot       = !this.state.showHot;       }
    toggleCold()      { this.state.showCold      = !this.state.showCold;      }
    toggleRemaining() { this.state.showRemaining = !this.state.showRemaining; }
}

NumerosCalientes.template = "lottery_portal.NumerosCalientes";
registry.category("public_components").add("lottery_portal.NumerosCalientes", NumerosCalientes);
