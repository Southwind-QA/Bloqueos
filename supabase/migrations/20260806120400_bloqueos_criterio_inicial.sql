-- ============================================================================
--  Registra la version inicial de criterios y completa los permisos del motor
--
--  El cargador fallaba con "permission denied for table criterio_version"
--  intentando crear la version si no existia. Estaba mal planteado: la version
--  de criterios es DECLARADA. Que el motor pudiera escribirla significaria que
--  una corrida puede cambiar la norma contra la que se evalua, que es
--  exactamente lo que el diseño evita.
--
--  Se registra aqui, como acto del administrador que aplica la migracion, y el
--  motor solo la lee.
-- ============================================================================

set search_path = bloqueos, public;

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
  'nitrito<85 en refrigerada y en bacon/wheel; '
  'vigencia=ultimo resultado que cubre el criterio',
  jsonb_build_object(
    'lim_ram', 100000,
    'lim_nitrito', 85,
    'min_lote', 8,
    'ram',      'toda linea',
    'nitrito',  'linea refrigerada, mas bacon y wheel (congelados que se venden refrigerados)',
    'listeria', 'linea refrigerada siempre; congelada solo con destino EE.UU. o Costa Rica',
    'vigencia', 'un criterio deja de estar vigente solo si un re-muestreo posterior vuelve a medirlo',
    'sin_dato', 'si la linea o el destino no se pueden determinar, el criterio se aplica igual'),
  'Version inicial: criterios vigentes al migrar desde las planillas'
where not exists (select 1 from criterio_version where hasta is null);

-- El motor cierra su propia corrida cuando termina. corrida es su bitacora de
-- ejecucion, no una decision de nadie, asi que puede actualizarla.
grant update on corrida to motor_bloqueos;
