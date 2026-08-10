-- ============================================================================
--  Una firma puede cubrir solo parte: unos mercados, o unos criterios
--
--  Dos cosas que la firma completa no sabia expresar:
--
--  1. MERCADOS. Un lote congelado con destino EE.UU. exige listeria; el mismo
--     producto a mercado nacional no. Liberar para Nacional no es liberar para
--     Echo Falls, y hasta ahora firmar liberaba para todo.
--
--  2. TRATAMIENTO. Las altas presiones hidrostaticas no son un tramite: es un
--     proceso letal que se le aplica a un despacho completo. Liberar por APH no
--     es "el laboratorio dio conforme", es "el producto paso por el proceso", y
--     levanta lo que el tratamiento efectivamente corrige -listeria y RAM- pero
--     no lo fisicoquimico: un nitrito bajo sigue bajo despues del APH.
--
--  ruta agrupa los lotes que viajaron juntos, que es como se opera: se manda un
--  despacho a APH, no un lote suelto.
-- ============================================================================
set search_path = bloqueos, public;

alter table decision add column if not exists tratamiento text;
alter table decision add column if not exists ruta        text;

alter table decision drop constraint if exists decision_tratamiento_ok;
alter table decision add constraint decision_tratamiento_ok
  check (tratamiento is null or tratamiento in ('APH'));

create index if not exists decision_ruta_idx on decision (ruta) where ruta is not null;

comment on column decision.tratamiento is
  'Proceso que justifica la liberacion, si lo hubo. APH levanta LISTERIA y RAM, '
  'no lo fisicoquimico.';
comment on column decision.ruta is
  'Identifica el despacho que se trato junto. Los lotes de una misma ruta se '
  'firman en bloque.';
comment on column decision.mercados is
  'Para que mercados vale la firma. Vacio = todos. Si no incluye el destino del '
  'lote, el lote sigue bloqueado para ese destino.';

-- El lote necesita arrastrar el alcance para que la consulta lo respete.
alter table lote add column if not exists mercados_firmados text[];
alter table lote add column if not exists tratamiento       text;
