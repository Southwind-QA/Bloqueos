-- ============================================================================
--  DET-2026-010 y DET-2026-011: fecha del evento 2024 -> 2026 (tipeo)
--
--  Las dos detenciones son del lote 2CK26401251, de 2026, pero quedaron con
--  fecha_evento 28/04/2024. Esa fecha define desde cuando una muestra sirve para
--  liberar (comment on column detencion.fecha_evento), asi que con 2024 cualquier
--  muestra del lote contaba como posterior al evento: el error iba hacia liberar.
--  Corregido a 28/04/2026 por indicacion de Calidad (Camilo Singer, 01/10/2026).
--
--  Se corrige solo si el valor sigue siendo el erroneo, y se deja la huella del
--  cambio en `observacion`: detencion no tiene tabla de historial.
-- ============================================================================
set search_path = bloqueos, public;

update detencion
   set fecha_evento = date '2026-04-28',
       observacion  = concat_ws(' | ', nullif(observacion, ''),
                      'fecha_evento corregida de 2024-04-28 a 2026-04-28 el 01/10/2026 '
                      '(tipeo; el lote es de 2026). Indicacion de Calidad, C. Singer.')
 where id in ('DET-2026-010', 'DET-2026-011')
   and fecha_evento = date '2024-04-28';

select id, lote, fecha_evento, estado, right(coalesce(observacion, ''), 90) as observacion
  from detencion where id in ('DET-2026-010', 'DET-2026-011') order by id;
