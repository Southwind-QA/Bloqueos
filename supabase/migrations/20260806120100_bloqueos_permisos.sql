-- ============================================================================
--  Permisos y auditoria
--
--  La regla que este archivo hace cumplir en la base, no en el frontend:
--
--    * el motor de criterios reescribe lo derivado y NO puede tocar lo declarado
--    * una persona consulta ve todo pero no escribe nada
--    * firmar exige rol calidad Y atribucion explicita (puede_firmar)
--    * las decisiones no se editan ni se borran: corregir es insertar
--
--  Se aplica con RLS para que valga aunque alguien manipule el navegador o
--  llame a la API directo.
-- ============================================================================

set search_path = bloqueos, public;

-- ---------------------------------------------------------------- quien soy
create or replace function actual() returns usuario
language sql stable security definer set search_path = bloqueos, public as $$
  select * from usuario where id = auth.uid() and activo
$$;

create or replace function tiene_rol(r rol_usuario[]) returns boolean
language sql stable as $$
  select coalesce((select rol = any(r) from actual()), false)
$$;

create or replace function puede_firmar() returns boolean
language sql stable as $$
  select coalesce((select puede_firmar and rol in ('calidad','admin') from actual()), false)
$$;

-- ------------------------------------------------------------------- lectura
do $$
declare t text;
begin
  foreach t in array array['lote','batch','muestra','stock_lote','detencion',
                           'decision','criterio_version','corrida','cambio_estado','usuario']
  loop
    execute format('alter table %I enable row level security', t);
    execute format($f$
      create policy "%1$s_lectura" on %1$I for select
      using (auth.uid() is not null)
    $f$, t);
  end loop;
end $$;

-- ------------------------------------------------------- derivado: solo el job
-- El motor corre con un rol de servicio propio. Nadie mas escribe aca, y el
-- job no aparece en ninguna policy de las tablas declaradas.
-- El motor NO usa service_role: esa clave salta RLS y podria escribir sobre lo
-- declarado. Usa un rol propio, sin login hasta que se le asigne credencial:
--
--   alter role motor_bloqueos login password '<clave>';
--
-- Ese paso se hace una vez, a mano, fuera del repositorio.
create role motor_bloqueos nologin;
grant usage on schema bloqueos to motor_bloqueos;
grant select, insert, update, delete on lote, batch, muestra, stock_lote
  to motor_bloqueos;
grant select, insert on corrida, cambio_estado to motor_bloqueos;
grant select on criterio_version, detencion, decision to motor_bloqueos;
grant usage on all sequences in schema bloqueos to motor_bloqueos;

comment on role motor_bloqueos is
  'Rol del motor de criterios. Lee lo declarado y reescribe lo derivado. '
  'Sin permiso de escritura sobre detencion, decision ni criterio_version: '
  'una corrida mala no puede borrar una decision firmada.';

-- --------------------------------------------------- declarado: solo personas
create policy "detencion_alta" on detencion for insert
  with check (tiene_rol(array['calidad','admin']::rol_usuario[]));

-- Una detencion se corrige mientras nadie la haya cerrado.
create policy "detencion_edicion" on detencion for update
  using (tiene_rol(array['calidad','admin']::rol_usuario[]) and estado = 'ABIERTA')
  with check (tiene_rol(array['calidad','admin']::rol_usuario[]));

-- Firmar exige atribucion, y solo a nombre propio.
create policy "decision_firma" on decision for insert
  with check (puede_firmar() and firmado_por = auth.uid());

-- Append-only de verdad: sin update ni delete, ni siquiera para admin.
revoke update, delete on decision from authenticated;

create policy "criterio_alta" on criterio_version for insert
  with check (tiene_rol(array['admin']::rol_usuario[]));

create policy "usuario_admin" on usuario for all
  using (tiene_rol(array['admin']::rol_usuario[]))
  with check (tiene_rol(array['admin']::rol_usuario[]));

-- ----------------------------------------------------------------- auditoria
create table auditoria (
  id        bigserial primary key,
  momento   timestamptz not null default now(),
  actor     uuid,
  tabla     text not null,
  accion    text not null,
  clave     text,
  antes     jsonb,
  despues   jsonb
);
alter table auditoria enable row level security;
create policy "auditoria_lectura" on auditoria for select
  using (tiene_rol(array['calidad','admin']::rol_usuario[]));
revoke insert, update, delete on auditoria from authenticated;

create or replace function registrar_auditoria() returns trigger
language plpgsql security definer set search_path = bloqueos, public as $$
begin
  insert into auditoria (actor, tabla, accion, clave, antes, despues)
  values (auth.uid(), tg_table_name, tg_op,
          coalesce(new.id::text, old.id::text),
          case when tg_op = 'INSERT' then null else to_jsonb(old) end,
          case when tg_op = 'DELETE' then null else to_jsonb(new) end);
  return coalesce(new, old);
end $$;

create trigger aud_detencion after insert or update or delete on detencion
  for each row execute function registrar_auditoria();
create trigger aud_decision after insert or update or delete on decision
  for each row execute function registrar_auditoria();
create trigger aud_criterio after insert or update or delete on criterio_version
  for each row execute function registrar_auditoria();
create trigger aud_usuario after insert or update or delete on usuario
  for each row execute function registrar_auditoria();

-- ------------------------------------------------------- coherencia mínima
-- Una liberacion firmada tiene que apuntar a la version de criterios vigente
-- al momento de firmar. Sin esto, "por que se libero" queda a medias.
create or replace function decision_criterio_vigente() returns trigger
language plpgsql as $$
begin
  if not exists (select 1 from criterio_version v
                 where v.id = new.criterio_ver and v.hasta is null) then
    raise exception 'La decision debe referirse a la version de criterios vigente';
  end if;
  return new;
end $$;

create trigger chk_decision_criterio before insert on decision
  for each row execute function decision_criterio_vigente();
