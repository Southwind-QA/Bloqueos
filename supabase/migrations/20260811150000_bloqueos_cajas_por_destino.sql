-- ============================================================================
--  Reparto de cajas por destino dentro del mismo lote
--
--  El destino del lote se resuelve hacia lo estricto: si un cliente es de EE.UU.,
--  el lote entero queda marcado. Eso es correcto para decidir si el criterio de
--  listeria aplica, y no cambia.
--
--  Lo que faltaba es el reparto. Firmar "Nacional" sobre un lote con cajas a
--  EE.UU. no liberaba nada y no habia forma de saberlo antes de firmar. Hoy hay
--  28 lotes con cajas de distinto destino en el mismo lote (13.234 cajas); 21
--  estan bloqueados o candidatos, con 12.043 cajas: 10.688 a EE.UU. y 1.355 sin
--  destino restringido.
--
--  Se puede separar, y esta es la diferencia con la letra de batch de ahumado:
--  Fishken NO registra la letra, pero SI registra el cliente caja por caja.
--
--  No cambia ningun veredicto -la huella de criterios no se toca- solo hace
--  visible el reparto para que quien firma sepa a cuantas cajas alcanza.
-- ============================================================================
set search_path = bloqueos, public;

alter table lote add column if not exists cajas_por_destino text;
alter table lote add column if not exists solo_destino boolean not null default false;

comment on column lote.cajas_por_destino is
  'Reparto de cajas del lote por destino (EE.UU., Costa Rica, sin restriccion). '
  'El estado del lote se resuelve hacia lo estricto; esto dice a cuantas cajas '
  'alcanzaria una firma acotada a un mercado. El cliente viene por caja de Fishken.';

--  Lo decide el MOTOR, no el navegador: la consulta de packing list necesita saber
--  si un bloqueo depende del destino, y derivar criterios en JavaScript seria tener
--  la norma escrita en dos lugares. Es verdadero solo si lo unico vigente es
--  listeria (de laboratorio o heredada de la materia prima), la linea no es
--  refrigerada -ahi se exige siempre- no hay nada declarado abierto, y el lote esta
--  marcado por destino EE.UU. o Costa Rica. Hoy: 5 lotes, 2.621 cajas.
comment on column lote.solo_destino is
  'El bloqueo depende solo del destino: un despacho a un mercado sin restriccion de '
  'listeria no lo arrastra. NO libera nada por si solo, lo firma Calidad.';

create index if not exists lote_solo_destino_idx on lote (solo_destino) where solo_destino;
