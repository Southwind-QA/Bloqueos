-- ============================================================================
--  Nueva version de criterios: vigencia por unidad, y RAM sobre el promedio
--
--  Dos cambios de norma, en una sola version porque entran en el mismo commit.
--  Ninguno vino de resultados nuevos. Decididos el 30/09/2026 por Calidad.
--
--  1. La vigencia de un incumplimiento se decide en la UNIDAD de laboratorio, el
--     lote con su sufijo *SSD, y no en el lote base. resume() agrupaba por el
--     codigo sin sufijo, asi que cualquier conforme posterior del mismo lote base
--     contaba como re-muestreo de la unidad que fallo. @2VQ2629250H*37V dio
--     listeria en 1 de 5 y lo "cubrio" *39W, que es otro producto de otro dia;
--     @2VQ26292461D*37W lo cubrio *38W, de otro juliano. Cada unidad lleva su
--     propio lote juliano: un conforme de otra unidad no la cierra, y si una
--     unidad del lote queda no conforme, el lote queda no conforme en ese
--     criterio. Una muestra sin sufijo es una unidad aparte: no cierra a una con
--     sufijo ni la cierra una con sufijo. Aplica a listeria, RAM y nitrito; el
--     error iba hacia liberar en los tres.
--
--  2. RAM: 500.000 UFC/g sobre el PROMEDIO de las replicas de la muestra, que es
--     la especificacion vigente del SSCA y la que aplica el dashboard de
--     inocuidad (parsers/reg08.py). Hasta hoy se exigia 100.000 a cada replica, y
--     los dos sistemas daban veredictos distintos sobre la misma fila. El promedio
--     se calcula igual que alla: lo que no es numero ("<10", "incontable", vacio)
--     no entra, y se redondea a entero antes de comparar.
--
--  Efecto medido sobre la foto del 30/09/2026 13:12 (misma entrada, codigo de
--  main contra la rama), 398 lotes en stock:
--      R1 solo: 8 candidatos con stock pasan a BLOQUEADO (2.663 cajas).
--      Con los dos cambios juntos:
--        6 CANDIDATO A LIBERAR -> BLOQUEADO      2.165 cajas  (R1: 2 listeria, 4 nitrito)
--        2 CANDIDATO A LIBERAR -> LIBERADO         498 cajas  (RAM: el fallo ya no es fallo)
--        2 BLOQUEADO -> LIBERADO                   404 cajas  (RAM)
--        3 BLOQUEADO -> CANDIDATO A LIBERAR        199 cajas  (RAM; queda la detencion
--                                                              historica o la MP, que ya
--                                                              tienen con que cerrarse)
--       16 siguen BLOQUEADO con otras causas     6.960 cajas
--      Candidatos con stock: de 100 a 95. Ninguno queda con una unidad no conforme.
--      55 muestras de producto terminado fallaban solo por una replica > 100.000
--      con promedio <= 500.000; 94 siguen sobre 500.000.
--
--  Ademas lote.unidades_no_conformes lleva, por lote, cada unidad que sigue no
--  conforme con su criterio y la fecha de la falla. Lo muestra en rojo el dialogo
--  de firma. Es nullable a proposito: mientras cargue el codigo anterior queda en
--  null y el sitio cae a la tabla de unidades.
--
--  APLICAR ANTES del merge a main, como postgres en el SQL Editor. Si el codigo
--  nuevo corre sin esta version registrada, cargar_supabase.py aborta por huella.
-- ============================================================================

set search_path = bloqueos, public;

alter table lote add column if not exists unidades_no_conformes jsonb;

comment on column lote.unidades_no_conformes is
  'Unidades de laboratorio (lote con sufijo *SSD) que siguen NO CONFORMES, con '
  'criterio y fecha de la falla: [{unidad, criterio, fecha, detalle}]. Lo calcula '
  'el motor con la misma regla que decide el estado del lote; el dialogo de firma '
  'lo muestra en rojo. No bloquea la firma: la decision es de Calidad.';

update criterio_version set hasta = now()
where hasta is null
  and huella <> 'listeria=refrigerada+congelada(EEUU|CostaRica); '
                'ram promedio de replicas>500000; '
                'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                '(nitrito>=85 y wps>3.5) o nitrito>100; '
                'vigencia=ultimo resultado que cubre el criterio, dentro de la misma '
                'unidad de laboratorio (lote con su sufijo *SSD; sin sufijo es unidad '
                'propia); '
                'detencion historica=bloquea por su motivo hasta liberacion declarada; '
                'vida util transcurrida=se cierra con RAM conforme posterior; '
                'materia prima=no caduca por muestra posterior del mismo lote de proveedor';

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); '
  'ram promedio de replicas>500000; '
  'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
  '(nitrito>=85 y wps>3.5) o nitrito>100; '
  'vigencia=ultimo resultado que cubre el criterio, dentro de la misma '
  'unidad de laboratorio (lote con su sufijo *SSD; sin sufijo es unidad '
  'propia); '
  'detencion historica=bloquea por su motivo hasta liberacion declarada; '
  'vida util transcurrida=se cierra con RAM conforme posterior; '
  'materia prima=no caduca por muestra posterior del mismo lote de proveedor',
  jsonb_build_object(
    'lim_ram', 500000,
    'ram_sobre', 'promedio de las replicas RAM1-RAM5 de la muestra; lo no numerico no '
                 'entra y el promedio se redondea a entero (igual que southwind_inocuidad)',
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
    'vigencia', 'un criterio deja de estar vigente solo si un re-muestreo posterior de la '
                'MISMA unidad (lote con su sufijo *SSD) vuelve a medirlo y sale conforme. '
                'Un conforme de otra unidad no la cierra; una unidad no conforme deja no '
                'conforme al lote; una muestra sin sufijo es unidad aparte',
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
  'Vigencia por unidad de laboratorio (R1: 8 candidatos con stock, 2.663 cajas, a '
  'bloqueado) y RAM 500.000 UFC/g sobre el promedio de replicas (especificacion SSCA, '
  'igual que el dashboard de inocuidad). Juntos: 6 lotes a bloqueado (2.165 cajas), '
  '4 a liberado (902), 3 a candidato (199). Decidido por Calidad el 30/09/2026.'
where not exists (
  select 1 from criterio_version
  where hasta is null
    and huella = 'listeria=refrigerada+congelada(EEUU|CostaRica); '
                 'ram promedio de replicas>500000; '
                 'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                 '(nitrito>=85 y wps>3.5) o nitrito>100; '
                 'vigencia=ultimo resultado que cubre el criterio, dentro de la misma '
                 'unidad de laboratorio (lote con su sufijo *SSD; sin sufijo es unidad '
                 'propia); '
                 'detencion historica=bloquea por su motivo hasta liberacion declarada; '
                 'vida util transcurrida=se cierra con RAM conforme posterior; '
                 'materia prima=no caduca por muestra posterior del mismo lote de proveedor');
