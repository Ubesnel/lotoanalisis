/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

export class NumerosCalientes extends Component {
    setup() {
        this.state = useState({
            turn: "afternoon",
            data: { afternoon: { numbers: [], centenas: [], bola_extra: [] },
                    evening:   { numbers: [], centenas: [], bola_extra: [] } },
            loading: true,
        });

        onWillStart(async () => {
            const data = await jsonrpc("/lottery/calientes-all", {});
            this.state.data = data || this.state.data;
            this.state.turn = data?.last_turn === "afternoon" ? "evening" : "afternoon";
            this.state.loading = false;
        });
    }

    get current()        { return this.state.data[this.state.turn]; }
    get numbers()        { return this.current.numbers         || []; }
    get centenas()       { return this.current.centenas        || []; }
    get bolaExtra()      { return this.current.bola_extra      || []; }
    get numbersCold()    { return this.current.numbers_cold    || []; }
    get centenasCold()   { return this.current.centenas_cold   || []; }
    get bolaExtraCold()  { return this.current.bola_extra_cold || []; }
    get nextDraw()       { return this.current.next_draw       || ''; }

    onChangeTurn(ev) { this.state.turn = ev.target.value; }
}

NumerosCalientes.template = "lottery_portal.NumerosCalientes";
registry.category("public_components").add("lottery_portal.NumerosCalientes", NumerosCalientes);
