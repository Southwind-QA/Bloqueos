-- ============================================================================
--  Binomio WPS / nitrito
--
--  Lo que controla Listeria en el ahumado no es el nitrito solo ni la sal sola,
--  sino los dos juntos. El LAB-REG-08 ya mide el WPS (sal en fase acuosa) en su
--  bloque fisicoquimico; hasta ahora el motor solo leia el nitrito.
--
--      WPS         nitrito < 85    85 <= nitrito <= 100    nitrito > 100
--      > 3,5       BLOQUEA         libera                  libera
--      3 a 3,5     BLOQUEA         BLOQUEA                 libera
--      < 3         BLOQUEA         BLOQUEA                 libera
--
--  Es decir: libera si (nitrito >= 85 y WPS > 3,5) o nitrito > 100. Escrito asi,
--  el caso sin WPS medido se resuelve solo y hacia el lado correcto: con nitrito
--  bajo 100 no se puede acreditar el binomio, asi que no libera.
-- ============================================================================
set search_path = bloqueos, public;

alter table lote  add column if not exists wps numeric;
alter table batch add column if not exists wps numeric;

comment on column lote.wps  is 'Sal en fase acuosa (%), minimo de las muestras del lote';
comment on column batch.wps is 'Sal en fase acuosa (%), promedio del batch';
