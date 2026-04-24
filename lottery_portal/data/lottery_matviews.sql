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


-- 🔹 Función del trigger
CREATE OR REPLACE FUNCTION trg_refresh_lottery_matviews()
RETURNS trigger AS $$
BEGIN
    -- Evita ejecuciones múltiples en cascada
    IF pg_trigger_depth() > 1 THEN
        RETURN NULL;
    END IF;

    PERFORM refresh_all_lottery_matviews();
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;


-- 🔹 Trigger
DROP TRIGGER IF EXISTS trg_refresh_lottery ON lottery_output;

CREATE TRIGGER trg_refresh_lottery
AFTER INSERT OR UPDATE OR DELETE
ON lottery_output
FOR EACH STATEMENT
EXECUTE FUNCTION trg_refresh_lottery_matviews();
