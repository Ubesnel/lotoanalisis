/** @odoo-module **/

import { Component, onWillStart, useState} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";
import { Tooltip } from "@web/core/tooltip/tooltip";

export class LotteryDashboardGroups extends Component {
    setup() {
        const todayIndex = new Date().getDay();
        const daysMap = {0: "do", 1: "lu", 2: "ma", 3: "mi", 4: "ju", 5: "vi", 6: "sa"};
        const monthsMap = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12};
        const monthIndex = new Date().getMonth();
        this.state = useState({
            top_6_groups_info: [],
            top_6_groups_info_afternoon: [],
            top_6_groups_info_evening: [],
            month_index: monthsMap[monthIndex],
            day_index: daysMap[todayIndex],
            openGroups: {},
            groupNumbers: {},
        });

        onWillStart(async () => {
            await this.loadTop6GroupsData();

        });
    }

    async loadTop6GroupsData() {
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data", {});
        this.state.top_6_groups_info = data.top_6_groups_info;
        this.state.top_6_groups_info_afternoon = data.top_6_groups_info_afternoon;
        this.state.top_6_groups_info_evening = data.top_6_groups_info_evening;

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
}

LotteryDashboardGroups.template = "lottery_portal.LotteryDashboardGroups";

registry.category("public_components").add("lottery_portal.LotteryDashboardGroups", LotteryDashboardGroups);