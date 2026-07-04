-- =========================================
-- REFRESH MATERIALIZED VIEWS - LOTTERY
-- =========================================

-- 🔹 Función principal
CREATE OR REPLACE FUNCTION refresh_all_lottery_matviews()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW lottery_number_groups_atrasos_mv;
    REFRESH MATERIALIZED VIEW lottery_top10_afternoon_mv;
    REFRESH MATERIALIZED VIEW lottery_top10_dia_semana_mv;
    REFRESH MATERIALIZED VIEW lottery_top10_evening_mv;
    REFRESH MATERIALIZED VIEW lottery_top10_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_dia_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_general_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_bola_extra_noche_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_centena_dia_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_centena_general_mv;
    REFRESH MATERIALIZED VIEW lottery_top5_centena_noche_mv;
    REFRESH MATERIALIZED VIEW lottery_top_atrasos_lineas_mv;
    REFRESH MATERIALIZED VIEW lottery_top_atrasos_terminales_mv;
    REFRESH MATERIALIZED VIEW lottery_ultima_salida_dia_semana_mv;
    REFRESH MATERIALIZED VIEW lottery_group_analysis_mv;
    REFRESH MATERIALIZED VIEW lottery_centena_weekday_mv;
    REFRESH MATERIALIZED VIEW lottery_centena_week_mv;
END;
$$ LANGUAGE plpgsql;


-- 🔹 El trigger que refrescaba TODAS las MVs en cada INSERT/UPDATE/DELETE de
--    lottery_output hacía que guardar una salida tardara ~9-15 segundos.
--    El refresh ahora corre fuera del request del usuario, en el cron
--    cron_recompute_pending_stats (y cron_refresh_materialized_views como
--    red de seguridad). Los DROP limpian bases donde el trigger ya existía.
DROP TRIGGER IF EXISTS trg_refresh_lottery ON lottery_output;
DROP FUNCTION IF EXISTS trg_refresh_lottery_matviews();
