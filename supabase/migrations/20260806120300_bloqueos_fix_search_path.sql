-- ============================================================================
--  Corrige la resolucion de nombres dentro de las funciones
--
--  Sintoma: leer bloqueos.usuario como `authenticated` fallaba con
--    ERROR 42883: function actual() does not exist
--    CONTEXT: SQL function "tiene_rol" during inlining
--
--  Causa: tiene_rol() y puede_firmar() llamaban a actual() sin calificar el
--  esquema y sin fijar search_path. Como `authenticated` no tiene bloqueos en
--  su search_path, la funcion no se resolvia. La policy usuario_admin es
--  `for all`, asi que tambien se evalua en un SELECT y arrastraba el error.
--
--  Se arregla de las dos formas a la vez, porque una sola no basta en todos
--  los caminos: se califica el esquema Y se fija el search_path.
-- ============================================================================

create or replace function bloqueos.actual() returns bloqueos.usuario
language sql stable security definer set search_path = bloqueos, public as $$
  select * from bloqueos.usuario where id = auth.uid() and activo
$$;

create or replace function bloqueos.tiene_rol(r bloqueos.rol_usuario[])
returns boolean
language sql stable security definer set search_path = bloqueos, public as $$
  select coalesce((select rol = any(r) from bloqueos.actual()), false)
$$;

create or replace function bloqueos.puede_firmar() returns boolean
language sql stable security definer set search_path = bloqueos, public as $$
  select coalesce((select puede_firmar and rol in ('calidad','admin')
                   from bloqueos.actual()), false)
$$;

-- Mismo problema latente: el trigger resolvia criterio_version sin calificar.
-- No habia fallado porque todavia no se inserta ninguna decision.
create or replace function bloqueos.decision_criterio_vigente() returns trigger
language plpgsql set search_path = bloqueos, public as $$
begin
  if not exists (select 1 from bloqueos.criterio_version v
                 where v.id = new.criterio_ver and v.hasta is null) then
    raise exception 'La decision debe referirse a la version de criterios vigente';
  end if;
  return new;
end $$;

-- Las funciones son security definer: las ejecuta su dueño, no quien llama.
-- Hay que poder invocarlas desde la API.
grant execute on function bloqueos.actual(),
                          bloqueos.tiene_rol(bloqueos.rol_usuario[]),
                          bloqueos.puede_firmar()
  to anon, authenticated;
