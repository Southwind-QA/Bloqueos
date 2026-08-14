-- ============================================================================
--  Cuarto origen: la materia prima
--
--  Si la materia prima estaba bloqueada, lo que se elaboro con ella tambien lo
--  esta. El laboratorio registra la MP por LOTE ORIGEN + PROVEEDOR y deja el
--  LOTE SW vacio, asi que esas muestras nunca entraban al cruce; el PRO-REG-46
--  (ingreso de MP por proveedor) es lo unico que las enlaza con el producto.
--
--  A la materia prima solo le aplican listeria y RAM: no trae nitrito ni WPS
--  (0 de 509 muestras), asi que el binomio no tiene nada que evaluar ahi.
--
--  El bloqueo NO se levanta con una muestra posterior de la misma materia prima.
--  Una materia prima desviada no se vuelve a analizar -si fue por listeria, nunca-,
--  y ademas el codigo es el LOTE DEL PROVEEDOR: cubre varios pallets y varias
--  recepciones, asi que una muestra posterior conforme con el mismo codigo es OTRA
--  unidad. Es la trampa de la letra de batch otra vez.
--
--  Lo unico que lo cierra es el resultado propio del producto elaborado en el mismo
--  criterio que fallo, o una decision firmada. Y ese resultado conforme tampoco
--  libera solo: el proceso es lo que controla lo que traia la materia prima, y esa
--  lectura la firma Calidad. El argumento queda escrito en la propuesta para que
--  quien firme no tenga que ir a buscarlo.
--
--  Cobertura: el PRO-REG-46 existe solo para 2026 y cubre 9 proveedores. De los
--  354 lotes de MP del laboratorio, 245 no figuran en el y por lo tanto su
--  bloqueo no se puede arrastrar a ningun producto. El motor lo declara en
--  consola y en la hoja FUENTES: un cruce parcial que no se declara se lee como
--  cobertura total.
-- ============================================================================
set search_path = bloqueos, public;

alter table lote add column if not exists motivo_mp  text;
alter table lote add column if not exists mp_bloquea boolean not null default false;

create index if not exists lote_mp_bloquea_idx on lote (mp_bloquea) where mp_bloquea;

comment on column lote.motivo_mp is
  'Materias primas no conformes con las que se elaboro el lote, via PRO-REG-46';
