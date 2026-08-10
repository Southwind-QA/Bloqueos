-- ============================================================================
--  El batch tambien arrastra su bloqueo operativo
--
--  El registro operativo identifica el dia con el sufijo en el 64% de los casos,
--  asi que el bloqueo puede apuntar a UNA unidad y no al lote. Sin esta columna,
--  la tabla de batches mostraba "conforme" al lado de BLOQUEADO -porque solo
--  tenia el motivo de laboratorio- y no habia forma de saber que lo bloqueaba.
-- ============================================================================
set search_path = bloqueos, public;

alter table batch add column if not exists motivo_operativo text;

comment on column batch.motivo_operativo is
  'Bloqueo del registro operativo declarado sobre esta unidad. Cuando la traza '
  'trae el sufijo *NNL, alcanza solo a ese dia de produccion.';
