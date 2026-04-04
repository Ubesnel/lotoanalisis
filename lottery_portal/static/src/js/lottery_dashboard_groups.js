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
            get_top_3_pintas: [],
            month_index: monthsMap[monthIndex],
            day_index: daysMap[todayIndex],
            openGroups: {},
            groupNumbers: {},
            group_type_atraso: "general",
            group_type_atraso_pinta: "general",
            openGroupsAnalysis: {},
            openGroupsAnalysisPinta: {},
        });

        onWillStart(async () => {
            await this.loadTop6GroupsData();
            await this.loadTop3GroupsDataPinta();

        });
    }

    async loadTop6GroupsData() {
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data", {
            group_type: this.state.group_type_atraso,
            day: this.state.day_index
        });
        this.state.top_6_groups_info = data.top_6_groups_info;
    }

    async loadTop3GroupsDataPinta() {
        const data = await jsonrpc("/estadisticas-grupos/dashboard_data_pintas", {
            group_type: this.state.group_type_atraso_pinta,
            day: this.state.day_index
        });
        this.state.get_top_3_pintas = data.get_top_3_pintas;

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

    async onChangeGroupTypeAtraso(ev) {
        this.state.group_type_atraso = ev.target.value;
        await this.loadTop6GroupsData();
    }

    async onChangeGroupTypeAtrasoPinta(ev) {
        this.state.group_type_atraso_pinta = ev.target.value;
        await this.loadTop3GroupsDataPinta();
    }

    async toggleGroupsAnalysis(groupId) {
        this.state.openGroupsAnalysis[groupId] = !this.state.openGroupsAnalysis[groupId];
        this.render();
    }

    async toggleGroupsAnalysisPinta(groupId) {
        this.state.openGroupsAnalysisPinta[groupId] = !this.state.openGroupsAnalysisPinta[groupId];
        this.render();
    }
}

LotteryDashboardGroups.template = "lottery_portal.LotteryDashboardGroups";

registry.category("public_components").add("lottery_portal.LotteryDashboardGroups", LotteryDashboardGroups);