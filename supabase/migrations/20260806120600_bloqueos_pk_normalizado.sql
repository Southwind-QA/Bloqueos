-- ============================================================================
--  La clave primaria es el codigo normalizado, no la etiqueta visible
--
--  Sintoma: la carga fallaba con
--    duplicate key value violates unique constraint "lote_pkey"
--
--  Causa: puse como clave la columna `lote`, que es la etiqueta que se muestra.
--  No es unica: 38 de 545 filas la repiten. Ocurre con los lotes que solo
--  existen en laboratorio, donde la etiqueta sale de una muestra emparentada y
--  puede ser la del lote padre. `normalizado` -el codigo con @ y B, sin el
--  sufijo de semana- si es unico y es la clave con la que el motor cruza todo.
--
--  La etiqueta queda como columna: sirve para mostrar, no para identificar.
-- ============================================================================

set search_path = bloqueos, public;

alter table lote  drop constraint lote_pkey;
alter table batch drop constraint batch_pkey;

alter table lote  add constraint lote_pkey  primary key (normalizado);
alter table batch add constraint batch_pkey primary key (normalizado);

create index if not exists lote_etiqueta_idx  on lote  (lote);
create index if not exists batch_etiqueta_idx on batch (batch);

comment on column lote.lote is
  'Etiqueta para mostrar. NO es unica: dos lotes distintos pueden compartirla. '
  'Para identificar, unir por normalizado.';
comment on column batch.batch is
  'Etiqueta para mostrar. Para identificar, unir por normalizado.';
