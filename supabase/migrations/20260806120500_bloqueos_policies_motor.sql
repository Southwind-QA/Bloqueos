-- ============================================================================
--  Politicas RLS para el rol del motor
--
--  Sintoma: el cargador no encontraba la version de criterios aunque estaba
--  insertada, y tampoco habria podido escribir en las tablas derivadas.
--
--  Causa: RLS se aplica a TODOS los roles, no solo a los de la API. La politica
--  de lectura de 002 exige auth.uid() no nulo, y motor_bloqueos no viene de la
--  API: su auth.uid() es nulo, asi que veia cero filas. Los GRANT estaban bien;
--  faltaban las policies.
--
--  Se resuelve con policies explicitas y no con BYPASSRLS, por dos razones:
--  BYPASSRLS necesita superusuario y en Supabase no lo hay, y ademas dejar por
--  escrito a que puede llegar el motor es justamente lo que queremos auditar.
--
--  La separacion derivado/declarado sigue intacta y ahora en dos capas:
--    GRANT  -> el motor no tiene INSERT/UPDATE/DELETE sobre lo declarado
--    RLS    -> sobre lo declarado solo se le concede SELECT
-- ============================================================================

set search_path = bloqueos, public;

create or replace function bloqueos.es_motor() returns boolean
language sql stable as $$
  select current_user = 'motor_bloqueos'
$$;

-- --------------------------------------------- derivado: lectura y escritura
do $$
declare t text;
begin
  foreach t in array array['lote','batch','muestra','stock_lote'] loop
    execute format($f$
      create policy "%1$s_motor" on %1$I for all
      using (bloqueos.es_motor()) with check (bloqueos.es_motor())
    $f$, t);
  end loop;
end $$;

-- ------------------------------------------- bitacora propia del motor
create policy "corrida_motor" on corrida for all
  using (es_motor()) with check (es_motor());

create policy "cambio_estado_motor" on cambio_estado for all
  using (es_motor()) with check (es_motor());

-- ------------------------------------------- declarado: SOLO lectura
-- El motor necesita leerlas para evaluar, y nada mas. Sin policy de insert,
-- update ni delete, y ademas sin el GRANT correspondiente.
create policy "criterio_version_motor_lee" on criterio_version for select
  using (es_motor());

create policy "detencion_motor_lee" on detencion for select
  using (es_motor());

create policy "decision_motor_lee" on decision for select
  using (es_motor());

create policy "usuario_motor_lee" on usuario for select
  using (es_motor());
