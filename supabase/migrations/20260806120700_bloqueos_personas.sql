-- ============================================================================
--  Lista de personas autorizadas y alta automatica
--
--  usuario.id referencia auth.users, asi que una persona solo puede tener fila
--  despues de existir como cuenta. En vez de crear las cuentas e ir linkeando
--  a mano -catorce veces, con el RUT copiado a ojo-, se declara la lista y un
--  trigger crea el vinculo cuando cada uno entra por primera vez.
--
--  La lista es ademas el control de acceso: sin fila en usuario, actual()
--  devuelve nulo y todas las policies dan falso. Alguien que se registre por su
--  cuenta con otro correo queda autenticado pero sin ver absolutamente nada.
--
--  puede_firmar queda en false para todos a proposito. El rol dice a que area
--  pertenece la persona; la atribucion para liberar producto es otra cosa y la
--  decide Calidad, no una migracion. Al final del archivo esta como concederla.
-- ============================================================================

set search_path = bloqueos, public;

create table if not exists persona_autorizada (
  correo        text primary key check (correo = lower(correo)),
  rut           text not null unique check (rut ~ '^[0-9]{7,8}-[0-9kK]$'),
  nombre        text not null,
  rol           rol_usuario not null default 'consulta',
  puede_firmar  boolean not null default false,
  activo        boolean not null default true,
  creado        timestamptz not null default now()
);
alter table persona_autorizada enable row level security;
create policy "persona_lectura" on persona_autorizada for select
  using (tiene_rol(array['admin']::rol_usuario[]) or es_motor());
create policy "persona_admin" on persona_autorizada for all
  using (tiene_rol(array['admin']::rol_usuario[]))
  with check (tiene_rol(array['admin']::rol_usuario[]));

insert into persona_autorizada (correo, rut, nombre, rol) values
  ('valeria@southwind.cl',            '8038148-4',   'Valeria Auda',                   'consulta'),
  ('laboratorio@southwind.cl',        '13452585-1',  'Tania Elvira Brito',             'calidad'),
  ('calidad@southwind.cl',            '14009315-7',  'Carolina Ivonne Bustos',         'admin'),
  ('mejoracontinua@southwind.cl',     '18762928-4',  'Matias Antonio Chamorro',        'calidad'),
  ('despacho@southwind.cl',           '16125939-k',  'Paulina Jeanette Contreras',     'consulta'),
  ('jefecalidad@southwind.cl',        '18409122-4',  'Alejandra Denisse Diaz',         'calidad'),
  ('lduran@southwind.cl',             '16487218-1',  'Loreto Veronica Duran',          'consulta'),
  ('afernandez@southwind.cl',         '13851849-3',  'Maria De Los Angeles Fernandez', 'consulta'),
  ('ejohansen@southwind.cl',          '12449359-5',  'Erich Johansen',                 'consulta'),
  ('jefeplanta@southwind.cl',         '10578822-3',  'Jose Alberto Quesille',          'consulta'),
  ('despacho2@southwind.cl',          '24171417-9',  'Martin Quesquen',                'consulta'),
  ('jsaez@southwind.cl',              '20073719-9',  'Jose Miguel Saez',               'consulta'),
  ('controlrecepcion@southwind.cl',   '17254373-1',  'David Fernando Santibanez',      'calidad'),
  ('documentacion@southwind.cl',      '16784918-0',  'Camilo Singer',                  'admin')
on conflict (correo) do nothing;

-- ------------------------------------------------------------- alta automatica
create or replace function bloqueos.alta_usuario() returns trigger
language plpgsql security definer set search_path = bloqueos, public as $$
declare p bloqueos.persona_autorizada;
begin
  select * into p from bloqueos.persona_autorizada
   where correo = lower(new.email) and activo;
  if not found then
    return new;   -- no autorizado: queda con cuenta pero sin acceso a nada
  end if;
  insert into bloqueos.usuario (id, rut, nombre, rol, puede_firmar)
  values (new.id, p.rut, p.nombre, p.rol, p.puede_firmar)
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists alta_usuario_trg on auth.users;
create trigger alta_usuario_trg after insert on auth.users
  for each row execute function bloqueos.alta_usuario();

-- Las cuentas que ya existian no pasaron por el trigger.
insert into usuario (id, rut, nombre, rol, puede_firmar)
select u.id, p.rut, p.nombre, p.rol, p.puede_firmar
  from auth.users u
  join persona_autorizada p on p.correo = lower(u.email)
 where p.activo
on conflict (id) do nothing;

-- ============================================================================
--  PASO MANUAL: quien puede firmar una liberacion
--
--  No es lo mismo que el rol. Un rol calidad puede registrar una detencion sin
--  tener atribucion para liberar producto. Decidan ustedes y ejecuten:
--
--    update bloqueos.persona_autorizada set puede_firmar = true
--     where correo in ('jefecalidad@southwind.cl', 'calidad@southwind.cl');
--
--    update bloqueos.usuario u set puede_firmar = p.puede_firmar
--      from bloqueos.persona_autorizada p
--     where p.rut = u.rut;
--
--  Las dos sentencias: la primera fija la lista, la segunda la aplica a quienes
--  ya tienen cuenta creada.
-- ============================================================================
