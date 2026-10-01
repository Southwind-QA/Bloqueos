-- ============================================================================
--  Nueva version de criterios: lo declarado se cierra por unidad, el criterio
--  de la base se lee, y los lotes de recorte tienen veredicto
--
--  Tres hallazgos sobre el motor, corregidos juntos el 30/09/2026 por indicacion
--  de Calidad. Ninguno vino de resultados nuevos.
--
--  1. Lotes de recorte y despunte mensual. CAL-PRO-07 los escribe [B][@] + sigla
--     + anio + juliano: SW26098 tiene 7 caracteres, y el piso de 8 (min_lote) los
--     descartaba como si fueran correlativos del laboratorio. SW26107*16V,
--     rebanado en frio con listeria en 1 de 3, no tenia veredicto. Se reconoce
--     esa forma y solo esa (config.LOTE_CORTO, juliano 001-366); el piso no baja
--     para el resto y '099', '107', '058*24J', 'NN' y 2420S0W siguen fuera. Un
--     lote corto solo se empareja por igualdad.
--
--  2. Texto, sin efecto en la huella: una propuesta resumia como "conforme en
--     LISTERIA" muestras entre las que habia una PRESENCIA no exigible por
--     destino. Ahora la nombra con unidad y fecha.
--
--  3. Cierre de lo declarado contra el laboratorio, por unidad.
--     detencion.criterios es criterio[] y psycopg lo entrega como texto
--     '{LISTERIA,RAM}': el motor no lo reconocia y ninguna detencion de la base
--     se podia cerrar. Se lee como arreglo, lista, JSON o texto; un criterio
--     desconocido deja la detencion vigente. Y como arreglar solo la lectura las
--     habria cerrado con un conforme de otra unidad (el error R1), detencion,
--     detencion historica y materia prima se cierran con la regla por unidad:
--     cada unidad alcanzada con resultados al dia del evento o antes necesita su
--     propia muestra posterior que mida el criterio; ninguna muestra del lote ni
--     del alcance lo incumple desde el dia del evento; el lote evaluado tiene
--     muestra posterior propia; una traza con sufijo solo la cierra esa unidad, y
--     cada traza de la detencion historica se cierra por separado. Una firma
--     sobre un batch o una unidad deja de liberar el lote que la contiene.
--
--  Efecto medido sobre la foto de la corrida 130 (30/09/2026 16:08), main
--  e534e63 contra la rama, mismos datos y sin tocar la base:
--      47 CANDIDATO A LIBERAR -> BLOQUEADO  (27 con stock, 4.440 cajas)
--         35 traza declarada sin muestras propias      (23 con stock, 4.058 cajas)
--          4 unidad previa sin re-muestreo propio       ( 3 con stock,   179 cajas)
--          6 la unica muestra "posterior" era del dia del evento (1, 203 cajas)
--          2 PRESENCIA posterior en una unidad hermana alcanzada (sin stock)
--      SW26107 entra al universo como BLOQUEADO (sin stock); 11 unidades de
--      recorte nuevas en el veredicto por unidad (1 bloqueada, 10 conformes).
--      Ningun lote pasa a LIBERADO ni a CANDIDATO. Candidatos con stock: de 95 a
--      68. Las 29 detenciones abiertas de la base siguen bloqueando; 23 tienen
--      ahora propuesta LIBERABLE, que solo es texto: las cierra una persona.
--
--  APLICAR ANTES del merge a main, como postgres en el SQL Editor. Si el codigo
--  nuevo corre sin esta version registrada, cargar_supabase.py aborta por huella.
-- ============================================================================

set search_path = bloqueos, public;

update criterio_version set hasta = now()
where hasta is null
  and huella <> 'listeria=refrigerada+congelada(EEUU|CostaRica); ram promedio de '
                 'replicas>500000 o alguna replica incontable (sobre el techo del metodo); '
                 'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si (nitrito>=85 '
                 'y wps>3.5) o nitrito>100; vigencia=ultimo resultado que cubre el criterio, '
                 'dentro de la misma unidad de laboratorio (lote con su sufijo *SSD; sin '
                 'sufijo es unidad propia); detencion historica=bloquea por su motivo hasta '
                 'liberacion declarada; vida util transcurrida=se cierra con RAM conforme '
                 'posterior; materia prima=no caduca por muestra posterior del mismo lote de '
                 'proveedor; cierre contra laboratorio de detencion, detencion historica y '
                 'materia prima=por unidad (cada unidad alcanzada con resultados al dia del '
                 'evento o antes necesita muestra posterior propia que mida el criterio; '
                 'ninguna posterior lo incumple; detencion con sufijo solo la cierra esa '
                 'unidad); firma sobre un batch o una unidad no libera el lote; lote=codigo de '
                 '8 o mas caracteres, o recorte/despunte [B][@]+sigla+anio+juliano';

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); ram promedio de '
  'replicas>500000 o alguna replica incontable (sobre el techo del metodo); '
  'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si (nitrito>=85 '
  'y wps>3.5) o nitrito>100; vigencia=ultimo resultado que cubre el criterio, '
  'dentro de la misma unidad de laboratorio (lote con su sufijo *SSD; sin '
  'sufijo es unidad propia); detencion historica=bloquea por su motivo hasta '
  'liberacion declarada; vida util transcurrida=se cierra con RAM conforme '
  'posterior; materia prima=no caduca por muestra posterior del mismo lote de '
  'proveedor; cierre contra laboratorio de detencion, detencion historica y '
  'materia prima=por unidad (cada unidad alcanzada con resultados al dia del '
  'evento o antes necesita muestra posterior propia que mida el criterio; '
  'ninguna posterior lo incumple; detencion con sufijo solo la cierra esa '
  'unidad); firma sobre un batch o una unidad no libera el lote; lote=codigo de '
  '8 o mas caracteres, o recorte/despunte [B][@]+sigla+anio+juliano',
  jsonb_build_object(
    'lim_ram', 500000,
    'ram_sobre', 'promedio de las replicas RAM1-RAM5 de la muestra; lo no numerico no '
                 'entra y el promedio se redondea a entero (igual que southwind_inocuidad)',
    'ram_techo', 'una replica sobre el techo del metodo (incontable, >N, TNTC, INC, MNPC) '
                 'hace no conforme a la muestra sea cual sea el promedio; <N queda fuera '
                 'del promedio; vacio es sin dato',
    'lim_nitrito', 85,
    'nit_binomio', 100,
    'wps_min', 3.5,
    'min_lote', 8,
    'lote_corto', 'recorte y despunte mensual (CAL-PRO-07): [B][@] + sigla de dos letras + '
                  'anio (2) + juliano de proceso 001-366, 7 caracteres sin prefijo '
                  '(SW26098). Solo se empareja por igualdad; el piso de 8 no baja para el resto',
    'ram',      'toda linea',
    'nitrito',  'binomio con el WPS; solo linea refrigerada, mas bacon y wheel',
    'binomio',  'libera si (nitrito >= 85 ppm y WPS > 3,5%) o si nitrito > 100 ppm. '
                'Bajo 85 ppm bloquea aunque el WPS sobre. Sin WPS medido y con nitrito '
                'bajo 100 no se puede acreditar, asi que no libera',
    'listeria', 'linea refrigerada siempre; congelada solo con destino EE.UU. o Costa Rica',
    'vigencia', 'un criterio deja de estar vigente solo si un re-muestreo posterior de la '
                'MISMA unidad (lote con su sufijo *SSD) vuelve a medirlo y sale conforme. '
                'Un conforme de otra unidad no la cierra; una unidad no conforme deja no '
                'conforme al lote; una muestra sin sufijo es unidad aparte',
    'cierre_declarado', 'detencion, detencion historica y materia prima se cierran contra el '
                        'laboratorio solo si, para cada criterio de su motivo: hay muestra '
                        'posterior (estrictamente despues del dia del evento) que lo mide, en '
                        'el alcance y en el propio lote; ninguna muestra del alcance ni del lote '
                        'lo incumple desde el dia del evento; y cada unidad alcanzada con '
                        'resultados al dia del evento o antes, o sin fecha, tiene su propia '
                        'muestra posterior que lo mide. Una detencion sobre el lote base alcanza '
                        'a todas sus unidades; con sufijo, solo a esa. Cada traza de la '
                        'detencion historica se cierra por separado',
    'criterios_detencion', 'se leen como arreglo de Postgres, lista, JSON o texto, sin importar '
                           'mayusculas ni espacios; un criterio no reconocido o una detencion '
                           'sin criterio no se cierran contra laboratorio',
    'firma', 'una liberacion firmada alcanza a la clave sobre la que se firmo y a lo que esta '
             'contiene; una firma sobre un batch o una unidad no libera el lote',
    'sin_dato', 'si la linea o el destino no se pueden determinar, el criterio se aplica igual',
    'detencion_historica', 'una fila sin Estado en Bloqueo 2026.xlsm es un bloqueo vigente; se '
                           'cierra con liberacion declarada o con el cierre por unidad contra el '
                           'criterio de SU motivo',
    'vida_util', 'no es producto vencido: son los limites operacionales de tiempo en proceso. '
                 'Lo cierra un RAM conforme posterior a la detencion',
    'materia_prima', 'su incumplimiento no caduca por una muestra posterior del mismo lote: el '
                     'codigo es del proveedor y cubre varios pallets y varias recepciones. Lo '
                     'cierra el resultado propio del producto elaborado en el mismo criterio, '
                     'por unidad, o una decision firmada',
    'motivos_no_medibles', 'documentacion, reclamo de cliente y desvio de proceso no los levanta '
                           'ninguna muestra: solo una decision firmada'),
  'Cierre de lo declarado por unidad, lectura de detencion.criterios como arreglo, y '
  'lotes de recorte de 7 caracteres (SW26107*16V no tenia veredicto). Sobre la foto de '
  'la corrida 130: 47 candidatos a bloqueado (27 con stock, 4.440 cajas), SW26107 '
  'nuevo bloqueado, ninguno hacia liberado ni candidato. Decidido por Calidad el '
  '30/09/2026.'
where not exists (
  select 1 from criterio_version
  where hasta is null
    and huella = 'listeria=refrigerada+congelada(EEUU|CostaRica); ram promedio de '
                'replicas>500000 o alguna replica incontable (sobre el techo del metodo); '
                'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si (nitrito>=85 '
                'y wps>3.5) o nitrito>100; vigencia=ultimo resultado que cubre el criterio, '
                'dentro de la misma unidad de laboratorio (lote con su sufijo *SSD; sin '
                'sufijo es unidad propia); detencion historica=bloquea por su motivo hasta '
                'liberacion declarada; vida util transcurrida=se cierra con RAM conforme '
                'posterior; materia prima=no caduca por muestra posterior del mismo lote de '
                'proveedor; cierre contra laboratorio de detencion, detencion historica y '
                'materia prima=por unidad (cada unidad alcanzada con resultados al dia del '
                'evento o antes necesita muestra posterior propia que mida el criterio; '
                'ninguna posterior lo incumple; detencion con sufijo solo la cierra esa '
                'unidad); firma sobre un batch o una unidad no libera el lote; lote=codigo de '
                '8 o mas caracteres, o recorte/despunte [B][@]+sigla+anio+juliano');

-- Verificacion: tiene que quedar exactamente una version vigente, y ser esta.
select id, desde, hasta, length(huella) as largo,
       huella like '%cierre contra laboratorio de detencion%por unidad%' as es_la_nueva,
       count(*) over () as vigentes
from criterio_version
where hasta is null;
