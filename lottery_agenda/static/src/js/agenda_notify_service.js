/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Arma los avisos del calendario apenas se abre Odoo.
 *
 * El servicio de avisos de Odoo 17 (calendarNotification) no pide las
 * alarmas al cargar la página: las recibe solo cuando el servidor las manda
 * por el bus (al crear o modificar un evento con alarma) y después encadena
 * una tras otra. Una pestaña abierta más tarde, recargada, o que perdió la
 * conexión con la PC dormida, se queda sin avisos hasta el próximo evento
 * nuevo: en la práctica, hasta la medianoche, cuando la agenda crea los del
 * día siguiente.
 *
 * Acá se le pide al servidor que mande las próximas alarmas por el bus al
 * abrir la página y cada vez que el bus se reconecta. Las muestra el mismo
 * servicio de Odoo, sin duplicar su lógica.
 */
export const lotteryAgendaNotifyService = {
    dependencies: ["bus_service", "rpc", "calendarNotification"],

    start(env, { bus_service, rpc }) {
        const pedir = () =>
            rpc("/lottery_agenda/calendar_notify", {}, { silent: true }).catch(() => {});
        pedir();
        bus_service.addEventListener("reconnect", pedir);
    },
};

registry.category("services").add("lotteryAgendaNotify", lotteryAgendaNotifyService);
