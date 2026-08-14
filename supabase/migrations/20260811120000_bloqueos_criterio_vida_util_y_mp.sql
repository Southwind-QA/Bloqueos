-- ============================================================================
--  Nueva version de criterios: vida util transcurrida, y la vigencia de la MP
--
--  Tres cambios, todos de norma. Ninguno vino de resultados nuevos.
--
--  1. "Vida util transcurrida" pasa a cerrarse con RAM.
--     NO significa producto vencido: significa que se sobrepasaron los limites
--     operacionales de tiempo en proceso, y lo que esa demora pone en riesgo es
--     la carga microbiologica. El motor lo declaraba "no se mide en laboratorio"
--     justo del motivo que SOLO se cierra con laboratorio; varias de esas filas
--     lo dicen textualmente ("quedara PNC hasta el resultado del laboratorio").
--     140 filas del registro pasan de no medible a medible por RAM.
--
--  2. El incumplimiento de la materia prima ya NO caduca por una muestra
--     posterior del mismo lote. Ese codigo es del PROVEEDOR y cubre varios
--     pallets y varias recepciones, asi que una muestra posterior conforme es
--     OTRA unidad. Los cuatro casos que el motor leia como re-muestreo lo
--     prueban: 26050004 tiene las dos muestras del mismo dia (codigos 1292 P y
--     1293 A), y 26060014 dio P el 12/06 y A el 15/06 con dos recepciones
--     distintas en el PRO-REG-46 bajo el mismo lote. Ademas una materia prima
--     desviada por listeria no se re-muestrea nunca. Lo unico que lo cierra es
--     el resultado propio del producto elaborado, o una decision firmada.
--
--  3. Se registra el cambio de nombre de "registro operativo" a "detencion
--     historica", que quedo en el codigo el 10/08/2026 sin version nueva. Por
--     eso la carga a Postgres viene abortando desde entonces: la ultima corrida
--     que entro es la 9, de las 17:56 del 10/08, y el renombre es de las 18:03.
--     El sitio quedo mostrando "Registro operativo" siete minutos despues.
--
--  Efecto medido en la corrida del 11/08/2026:
--      1 lote pasa de BLOQUEADO a CANDIDATO A LIBERAR (274 cajas), por vida
--        util con RAM posterior conforme
--      0 lotes cambian por el criterio de materia prima. Los 9 que se sostenian
--        en el falso re-muestreo llegan al mismo veredicto por un camino valido:
--        3 son congelados sin destino restringido y 6 tienen analisis conformes
--        del producto terminado. Se cayo el argumento, no el producto.
--
--  El cambio 1 libera; el 2 no mueve nada hoy pero cierra un camino por el que
--  se habria liberado solo el proximo caso sin cobertura del terminado.
--
--  Lo que NO se movio y sigue siendo el cuello de botella: 2.109 de las 4.326
--  filas abiertas del xlsm no tienen FECHA BLOQUEO, y sin fecha no se puede
--  acreditar que una muestra sea posterior. De las 121 filas de vida util, 108
--  no tienen fecha: por eso el cambio 1 solo alcanzo a mover un lote.
-- ============================================================================

set search_path = bloqueos, public;

update criterio_version set hasta = now()
where hasta is null
  and huella <> 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                '(nitrito>=85 y wps>3.5) o nitrito>100; '
                'vigencia=ultimo resultado que cubre el criterio; '
                'detencion historica=bloquea por su motivo hasta liberacion declarada; '
                'vida util transcurrida=se cierra con RAM conforme posterior; '
                'materia prima=no caduca por muestra posterior del mismo lote de proveedor';

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
  'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
  '(nitrito>=85 y wps>3.5) o nitrito>100; '
  'vigencia=ultimo resultado que cubre el criterio; '
  'detencion historica=bloquea por su motivo hasta liberacion declarada; '
  'vida util transcurrida=se cierra con RAM conforme posterior; '
  'materia prima=no caduca por muestra posterior del mismo lote de proveedor',
  jsonb_build_object(
    'lim_ram', 100000,
    'lim_nitrito', 85,
    'nit_binomio', 100,
    'wps_min', 3.5,
    'min_lote', 8,
    'ram',      'toda linea',
    'nitrito',  'binomio con el WPS; solo linea refrigerada, mas bacon y wheel',
    'binomio',  'libera si (nitrito >= 85 ppm y WPS > 3,5%) o si nitrito > 100 ppm. '
                'Bajo 85 ppm bloquea aunque el WPS sobre. Sin WPS medido y con nitrito '
                'bajo 100 no se puede acreditar, asi que no libera',
    'listeria', 'linea refrigerada siempre; congelada solo con destino EE.UU. o Costa Rica',
    'vigencia', 'un criterio deja de estar vigente solo si un re-muestreo posterior vuelve a medirlo',
    'sin_dato', 'si la linea o el destino no se pueden determinar, el criterio se aplica igual',
    'detencion_historica', 'una fila sin Estado en Bloqueo 2026.xlsm es un bloqueo vigente; '
                           'se cierra con liberacion declarada o con una muestra posterior a la '
                           'fecha de bloqueo que mida el criterio de SU motivo y salga conforme',
    'vida_util', 'no es producto vencido: son los limites operacionales de tiempo en proceso. '
                 'Lo cierra un RAM conforme posterior a la detencion',
    'materia_prima', 'su incumplimiento no caduca por una muestra posterior del mismo lote: '
                     'el codigo es del proveedor y cubre varios pallets y varias recepciones, '
                     'asi que un conforme posterior es otra unidad. Lo cierra el resultado propio '
                     'del producto elaborado en el mismo criterio, o una decision firmada',
    'motivos_no_medibles', 'documentacion, reclamo de cliente y desvio de proceso no los levanta '
                           'ninguna muestra: solo una decision firmada'),
  'Vida util transcurrida se cierra con RAM (1 lote, 274 cajas, hacia candidato). '
  'La materia prima deja de caducar por muestras de otro pallet del mismo lote de '
  'proveedor (0 lotes cambian, pero se cierra una liberacion automatica falsa). '
  'Se registra tambien el renombre a detencion historica del 10/08/2026, que dejo '
  'la carga a Postgres abortando desde la corrida 9.'
where not exists (
  select 1 from criterio_version
  where hasta is null
    and huella = 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                 'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                 '(nitrito>=85 y wps>3.5) o nitrito>100; '
                 'vigencia=ultimo resultado que cubre el criterio; '
                 'detencion historica=bloquea por su motivo hasta liberacion declarada; '
                 'vida util transcurrida=se cierra con RAM conforme posterior; '
                 'materia prima=no caduca por muestra posterior del mismo lote de proveedor');
