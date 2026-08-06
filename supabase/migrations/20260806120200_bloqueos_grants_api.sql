-- ============================================================================
--  Permisos para la API (PostgREST)
--
--  RLS decide QUE FILAS ve cada usuario, pero antes Postgres tiene que dejarlo
--  siquiera tocar la tabla. En el esquema `public` Supabase ya trae esos GRANT;
--  en un esquema nuevo no, asi que sin este archivo el frontend recibe
--  "permission denied for schema bloqueos" aunque las policies esten bien.
--
--  Los dos mecanismos son complementarios y ninguno reemplaza al otro:
--    GRANT  -> puede tocar la tabla
--    RLS    -> que filas, y si puede escribir
-- ============================================================================

set search_path = bloqueos, public;

-- anon entra al esquema pero no lee nada: la policy de lectura exige
-- auth.uid() no nulo. Se le da usage igual para que un request sin sesion
-- devuelva vacio en vez de un error de esquema inexistente.
grant usage on schema bloqueos to anon, authenticated;

-- Lectura: todo lo que la policy permita.
grant select on all tables in schema bloqueos to authenticated;

-- Escritura: solo sobre lo declarado, y filtrada por las policies de 002.
-- Lo derivado no se toca desde la API: lo reescribe el motor con su propio rol.
grant insert on detencion, decision, criterio_version to authenticated;
grant update on detencion to authenticated;
grant insert, update on usuario to authenticated;

-- Las claves bigserial necesitan la secuencia.
grant usage, select on all sequences in schema bloqueos to authenticated;

-- Una decision no se edita ni se borra: corregir es insertar una que anule.
-- Se repite aqui porque el revoke de 002 corria antes de que existiera el grant.
revoke update, delete on decision from authenticated, anon;
revoke insert, update, delete on auditoria from authenticated, anon;

-- Tablas futuras del esquema heredan el mismo criterio.
alter default privileges in schema bloqueos
  grant select on tables to authenticated;
alter default privileges in schema bloqueos
  grant usage, select on sequences to authenticated;
