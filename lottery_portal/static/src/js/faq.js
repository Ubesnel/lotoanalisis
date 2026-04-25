/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class WebsiteFAQ extends Component {

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            openId: null,
            search: "",
            faqs: [],
            categories: [],
            openCategoryId: null,
        });

        onWillStart(async () => {
            const result = await this.rpc("/faq/data", {});
            this.state.faqs = result.faqs;
            this.state.categories = result.categories;
        });
    }

    toggle(ev) {
        const id = parseInt(ev.currentTarget.dataset.id);
        this.state.openId =
            this.state.openId === id ? null : id;
    }

    toggleCategory(ev) {
        const id = parseInt(ev.currentTarget.dataset.id);
        this.state.openCategoryId =
            this.state.openCategoryId === id ? null : id;

        this.state.openId = null;
    }

    cleanAnswer(answer) {
        return (answer || '').replace(/^R\/\s*/i, '');
    }

    get groupedFaqs() {
        const search = this.state.search.toLowerCase();
        const grouped = {};
        const catMap = Object.fromEntries(this.state.categories.map(c => [c.id, c]));

        for (const faq of this.state.faqs) {
            if (search && !faq.question.toLowerCase().includes(search)) continue;
            const cat = faq.category_id || [0, "Sin categoría"];
            if (!grouped[cat[0]]) {
                grouped[cat[0]] = {
                    id: cat[0],
                    name: cat[1],
                    icon: catMap[cat[0]]?.icon || 'fa-folder',
                    faqs: [],
                };
            }
            grouped[cat[0]].faqs.push(faq);
        }

        return Object.values(grouped);
    }
}

WebsiteFAQ.template = "lottery_portal.WebsiteFAQ";

registry.category("public_components").add(
    "lottery_portal.WebsiteFAQ",
    WebsiteFAQ
);