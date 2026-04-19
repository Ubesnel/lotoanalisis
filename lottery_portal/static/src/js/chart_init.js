/** @odoo-module **/

if (typeof Chart !== 'undefined' && typeof ChartDataLabels !== 'undefined') {
    if (!Chart.registry.plugins.get('datalabels')) {
        Chart.register(ChartDataLabels);
    }
}
