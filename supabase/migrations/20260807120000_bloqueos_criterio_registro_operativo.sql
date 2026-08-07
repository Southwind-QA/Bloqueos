-- ============================================================================
--  Nueva version de criterios: el registro operativo bloquea por su motivo
--
--  Cambia la norma, no los resultados: Bloqueo 2026.xlsm pasa a ser un tercer
--  origen de bloqueo. En esa hoja la columna Estado se escribe UNICAMENTE al
--  liberar, asi que una fila sin estado es un bloqueo vigente; hasta ahora esas
--  2.591 filas quedaban fuera del cruce.
--
--  Efecto medido en la corrida del 07/08/2026: 17.680 cajas salen de LIBERADO.
--  De ellas 7.475 quedan CANDIDATO A LIBERAR porque el laboratorio si trajo el
--  argumento; el resto sigue bloqueado. 11.551 de las cajas afectadas estaban
--  declaradas por presencia de listeria.
--
--  Se registra aqui, y no en el motor, por lo mismo que la version inicial: si
--  una corrida pudiera cambiar la norma contra la que se evalua, el historial
--  dejaria de distinguir "cambio el resultado" de "cambiamos la regla".
-- ============================================================================

set search_path = bloqueos, public;

-- Cierra la vigente. El motor lee la que tiene hasta is null.
update criterio_version set hasta = now()
where hasta is null
  and huella <> 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                'nitrito<85 en refrigerada y en bacon/wheel; '
                'vigencia=ultimo resultado que cubre el criterio; '
                'registro operativo=bloquea por su motivo hasta liberacion declarada';

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
  'nitrito<85 en refrigerada y en bacon/wheel; '
  'vigencia=ultimo resultado que cubre el criterio; '
  'registro operativo=bloquea por su motivo hasta liberacion declarada',
  jsonb_build_object(
    'lim_ram', 100000,
    'lim_nitrito', 85,
    'min_lote', 8,
    'ram',      'toda linea',
    'nitrito',  'linea refrigerada, mas bacon y wheel (congelados que se venden refrigerados)',
    'listeria', 'linea refrigerada siempre; congelada solo con destino EE.UU. o Costa Rica',
    'vigencia', 'un criterio deja de estar vigente solo si un re-muestreo posterior vuelve a medirlo',
    'sin_dato', 'si la linea o el destino no se pueden determinar, el criterio se aplica igual',
    'registro_operativo', 'una fila sin Estado en Bloqueo 2026.xlsm es un bloqueo vigente; '
                          'se cierra con liberacion declarada o con una muestra posterior a la '
                          'fecha de bloqueo que mida el criterio de SU motivo y salga conforme',
    'motivos_no_medibles', 'documentacion, reclamo de cliente y desvio de proceso no los levanta '
                           'ninguna muestra: solo una decision firmada'),
  'Incorpora el registro operativo como tercer origen de bloqueo. Las filas sin '
  'Estado son bloqueos vigentes: 420 filas liberadas tienen fecha de liberacion y '
  'las 2.591 sin estado ninguna, sin excepcion.'
where not exists (
  select 1 from criterio_version
  where hasta is null
    and huella = 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                 'nitrito<85 en refrigerada y en bacon/wheel; '
                 'vigencia=ultimo resultado que cubre el criterio; '
                 'registro operativo=bloquea por su motivo hasta liberacion declarada');
