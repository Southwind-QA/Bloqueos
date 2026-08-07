-- ============================================================================
--  Nueva version de criterios: binomio WPS / nitrito
--
--  Cambia la norma, no los resultados. El criterio anterior miraba el nitrito
--  solo (bloquea bajo 85 ppm); ahora decide junto con la sal en fase acuosa.
--
--  Efecto medido en la corrida del 07/08/2026: 36 transiciones, y solo tres
--  lotes con stock cambian de estado. Ninguno se libera: la regla es mas
--  estricta, no mas permisiva.
--      2AS2613148   LIBERADO -> BLOQUEADO   (89 cajas, nitrito 92,2 / WPS 3,49)
--      @2CK2654161  LIBERADO -> BLOQUEADO   (729 cajas, nitrito 92,6 / WPS 3,36)
--      @2CK2642134  CANDIDATO -> BLOQUEADO  (18 cajas, nitrito 86,7 / WPS 3,36)
--
--  Los tres son el caso que antes pasaba inadvertido: nitrito SOBRE el limite
--  viejo de 85 ppm, pero sin el WPS que lo acompanie.
-- ============================================================================

set search_path = bloqueos, public;

update criterio_version set hasta = now()
where hasta is null
  and huella <> 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                '(nitrito>=85 y wps>3.5) o nitrito>100; '
                'vigencia=ultimo resultado que cubre el criterio; '
                'registro operativo=bloquea por su motivo hasta liberacion declarada';

insert into criterio_version (huella, parametros, motivo)
select
  'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
  'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
  '(nitrito>=85 y wps>3.5) o nitrito>100; '
  'vigencia=ultimo resultado que cubre el criterio; '
  'registro operativo=bloquea por su motivo hasta liberacion declarada',
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
    'registro_operativo', 'una fila sin Estado en Bloqueo 2026.xlsm es un bloqueo vigente; '
                          'se cierra con liberacion declarada o con una muestra posterior a la '
                          'fecha de bloqueo que mida el criterio de SU motivo y salga conforme',
    'motivos_no_medibles', 'documentacion, reclamo de cliente y desvio de proceso no los levanta '
                           'ninguna muestra: solo una decision firmada'),
  'El nitrito pasa a decidir junto con el WPS. Tres lotes con stock cambian de '
  'estado, todos hacia bloqueado: tenian nitrito sobre 85 ppm pero WPS bajo 3,5%.'
where not exists (
  select 1 from criterio_version
  where hasta is null
    and huella = 'listeria=refrigerada+congelada(EEUU|CostaRica); ram>100000; '
                 'binomio wps/nitrito en refrigerada y en bacon/wheel: libera si '
                 '(nitrito>=85 y wps>3.5) o nitrito>100; '
                 'vigencia=ultimo resultado que cubre el criterio; '
                 'registro operativo=bloquea por su motivo hasta liberacion declarada');
