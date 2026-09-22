-- ============================================================================
--  Lectura para el asistente
--
--  Sintoma: `select count(*) from bloqueos.detencion` devolvia 0 al rol
--  asistente_app, con el GRANT puesto y sin ningun error. Con el rol del motor
--  la misma consulta devolvia 17.
--
--  Causa: la de siempre en este esquema, y ya esta escrita en
--  20260806120500 -"GRANT y RLS son capas distintas; hay que resolver las dos"-.
--  Las policies de lectura exigen auth.uid() no nulo o es_motor(), y
--  asistente_app no es ninguna de las dos: veia las tablas vacias.
--
--  Por que esto vive en Bloqueos y no en el repo del asistente: **bloqueos
--  decide quien puede leer bloqueos.** Si la policy que abre la puerta la
--  escribiera el que entra, la puerta no seria una puerta. Es la misma razon por
--  la que el motor tiene su archivo de policies aca y no en el cargador.
--
--  Y por que importa mas que un permiso cualquiera: un boletin que lee cero
--  detenciones no dice "no puedo leer", dice "no hay nada pendiente". El error
--  se degrada hacia tranquilizar, que es la unica direccion que este proyecto no
--  se permite.
--
--  Se aplica en el SQL Editor como postgres, SIN RLS.
-- ============================================================================
set search_path = bloqueos, public;

create or replace function bloqueos.es_asistente() returns boolean
language sql stable as $$
  select current_user = 'asistente_app'
$$;

-- Solo las tres tablas que el asistente lee de verdad: corrida y cambio_estado
-- para contar corridas y transiciones, detencion para cruzar los correos de
-- Supervisor de Calidad contra lo registrado.
--
-- El GRANT original abarcaba las 12 tablas del esquema, que era mas de lo
-- necesario. Se acota: sin policy igual verian cero filas, pero un permiso que
-- sobra es un permiso que alguien va a usar sin darse cuenta.
revoke select on all tables in schema bloqueos from asistente_app;
alter default privileges in schema bloqueos
  revoke select on tables from asistente_app;

grant select on corrida, cambio_estado, detencion to asistente_app;

do $$
declare t text;
begin
  foreach t in array array['corrida', 'cambio_estado', 'detencion'] loop
    execute format($f$
      drop policy if exists "%1$s_asistente" on %1$I;
      create policy "%1$s_asistente" on %1$I for select
      using (bloqueos.es_asistente())
    $f$, t);
  end loop;
end $$;

comment on function bloqueos.es_asistente() is
  'El asistente solo LEE, y solo tres tablas. No tiene ni puede tener INSERT, '
  'UPDATE ni DELETE en este esquema: una corrida suya no puede tocar una '
  'detencion ni una firma.';
