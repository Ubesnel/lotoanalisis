/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { sorteoState, ensureSorteoLoaded, setSorteo } from "./sorteo_state";

export class SorteoSelector extends Component {
    setup() {
        this.state = useState(sorteoState);
        onWillStart(async () => {
            await ensureSorteoLoaded();
        });
    }

    onChange(ev) {
        setSorteo(ev.target.value);
    }
}

SorteoSelector.template = "lottery_portal.SorteoSelector";

registry.category("public_components").add("lottery_portal.SorteoSelector", SorteoSelector);
