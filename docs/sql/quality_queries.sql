-- Consultas de análisis y administración para tk_quality_control.
-- Ejecutar con: docker compose exec db psql -U odoo -d <base> -f /ruta/quality_queries.sql
-- o abrir una consola: docker compose exec db psql -U odoo -d <base>

-- ---------------------------------------------------------------------------
-- 1. Negocio
-- ---------------------------------------------------------------------------

-- Tasa de aprobación por proveedor en los últimos 90 días (usa la vista del módulo).
SELECT p.name AS proveedor,
       SUM(r.check_count) AS inspecciones,
       SUM(r.fail_count) AS fallidas,
       ROUND(AVG(r.pass_rate), 1) AS tasa_aprobacion
FROM tk_quality_report r
JOIN res_partner p ON p.id = r.supplier_id
WHERE r.date >= NOW() - INTERVAL '90 days'
GROUP BY p.name
ORDER BY tasa_aprobacion ASC, inspecciones DESC;

-- Costo de no conformidades abiertas por categoría de causa (6M).
SELECT COALESCE(a.cause_category, 'sin_analizar') AS causa,
       COUNT(*) AS alertas,
       ROUND(SUM(a.cost)::numeric, 2) AS costo
FROM tk_quality_alert a
WHERE a.is_closed IS NOT TRUE
GROUP BY a.cause_category
ORDER BY costo DESC;

-- Tiempo medio de cierre de alertas, por mes de cierre.
SELECT DATE_TRUNC('month', a.date_closed) AS mes,
       COUNT(*) AS cerradas,
       ROUND(AVG(EXTRACT(EPOCH FROM (a.date_closed - a.create_date)) / 86400)::numeric, 1) AS dias_promedio
FROM tk_quality_alert a
WHERE a.date_closed IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;

-- Recepciones con inspecciones pendientes (lo mismo que bloquea la validación).
SELECT sp.name AS recepcion, COUNT(c.id) AS pendientes
FROM stock_picking sp
JOIN tk_quality_check c ON c.picking_id = sp.id AND c.state = 'pending'
WHERE sp.state NOT IN ('done', 'cancel')
GROUP BY sp.name
ORDER BY pendientes DESC;

-- Integridad: inspecciones fallidas sin alerta registrada.
SELECT c.name, c.product_id, c.picking_id, c.production_id
FROM tk_quality_check c
LEFT JOIN tk_quality_alert a ON a.check_id = c.id
WHERE c.state = 'fail' AND a.id IS NULL;

-- ---------------------------------------------------------------------------
-- 2. Administración de PostgreSQL
-- ---------------------------------------------------------------------------

-- Tamaño de la base y de las tablas del módulo (datos + índices).
SELECT pg_size_pretty(pg_database_size(current_database())) AS base;

SELECT relname AS tabla,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_indexes_size(relid)) AS indices,
       n_live_tup AS filas_vivas,
       n_dead_tup AS filas_muertas
FROM pg_stat_user_tables
WHERE relname LIKE 'tk_quality_%'
ORDER BY pg_total_relation_size(relid) DESC;

-- Índices creados por el ORM (index=True / index="btree_not_null") y su uso.
SELECT s.relname AS tabla, s.indexrelname AS indice, s.idx_scan AS lecturas,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS tamano
FROM pg_stat_user_indexes s
WHERE s.relname LIKE 'tk_quality_%'
ORDER BY s.relname, s.idx_scan DESC;

-- Plan de ejecución de la consulta que hace la validación de una recepción.
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, state FROM tk_quality_check WHERE picking_id = 1;

-- Consultas activas que llevan más de 30 segundos.
SELECT pid, usename, state, NOW() - query_start AS duracion, LEFT(query, 120) AS consulta
FROM pg_stat_activity
WHERE state <> 'idle' AND NOW() - query_start > INTERVAL '30 seconds'
ORDER BY duracion DESC;

-- Bloqueos: quién espera a quién.
SELECT bloqueada.pid AS pid_bloqueado, LEFT(bloqueada.query, 80) AS consulta_bloqueada,
       bloqueante.pid AS pid_bloqueante, LEFT(bloqueante.query, 80) AS consulta_bloqueante
FROM pg_stat_activity bloqueada
JOIN pg_stat_activity bloqueante ON bloqueante.pid = ANY(pg_blocking_pids(bloqueada.pid));

-- Mantenimiento manual de las tablas del módulo.
VACUUM (ANALYZE) tk_quality_check;
VACUUM (ANALYZE) tk_quality_alert;
