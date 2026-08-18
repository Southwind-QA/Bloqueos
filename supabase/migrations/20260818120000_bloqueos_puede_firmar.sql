-- ============================================================================
--  Quien puede firmar una liberacion
--
--  Es el paso manual que la migracion de personas dejo anotado y sin ejecutar:
--  puede_firmar quedo en false para todos a proposito, porque la atribucion para
--  liberar producto no la decide una migracion. La decidio Calidad, y son cuatro.
--
--  No es lo mismo que el rol. El rol dice a que area pertenece la persona; esto
--  dice quien puede poner su nombre en una liberacion. Por eso David Santibanez
--  y Alejandra Diaz tienen rol calidad y no aparecen aca: registran detenciones,
--  no firman liberaciones.
--
--  Hasta que esto corra, la tabla decision esta vacia y el sitio le responde
--  "Tu cuenta no puede firmar liberaciones" a todo el mundo, con 159 lotes
--  candidatos -unas 20.000 cajas- esperando una firma que nadie puede dar.
-- ============================================================================
set search_path = bloqueos, public;

update persona_autorizada set puede_firmar = true
 where correo in ('laboratorio@southwind.cl',        -- Tania Brito
                  'mejoracontinua@southwind.cl',     -- Matias Chamorro
                  'calidad@southwind.cl',            -- Carolina Bustos
                  'documentacion@southwind.cl');     -- Camilo Singer

--  La lista es lo que lee el trigger de alta cuando alguien entra por primera
--  vez. Quien ya tiene cuenta creada no vuelve a pasar por ahi, asi que hay que
--  aplicarselo a mano. Se propaga en los dos sentidos -true y false- para que
--  quitar la atribucion en la lista tambien la quite a quien ya entro; si solo
--  propagara los true, revocar no revocaria nada.
update usuario u set puede_firmar = p.puede_firmar
  from persona_autorizada p
 where p.rut = u.rut
   and u.puede_firmar is distinct from p.puede_firmar;

--  Verificacion. Tienen que salir cuatro filas, y las mismas cuatro en las dos
--  consultas: si usuario trae menos, es que esas personas todavia no han
--  entrado nunca al sitio y el trigger se los dara al crear la cuenta.
select correo, nombre, rol, puede_firmar
  from persona_autorizada where puede_firmar order by nombre;
select u.nombre, u.rol, u.puede_firmar
  from usuario u where u.puede_firmar order by u.nombre;
