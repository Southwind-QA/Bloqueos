-- ============================================================================
--  La propuesta de liberacion tambien viaja al sitio
--
--  El sitio mostraba por que un lote estaba bloqueado, pero no el argumento que
--  lo levanta: quien iba a firmar veia "CANDIDATO A LIBERAR" sin poder leer que
--  lo dejo candidato. Firmar asi es un acto a ciegas, y firmar es justo el paso
--  que no puede serlo.
--
--  Es el mismo texto que ya estaba en el Excel, columna
--  PROPUESTA DE LIBERACION (no libera): las propuestas separadas por ||.
-- ============================================================================
set search_path = bloqueos, public;

alter table lote add column if not exists propuesta text;

comment on column lote.propuesta is
  'Que haria falta para liberar, criterio por criterio. No libera nada por si '
  'sola: la firma es de Calidad.';
