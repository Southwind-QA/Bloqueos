# Contexto del proyecto — léeme primero

Documento de traspaso. Si retomas este trabajo sin haber estado en las conversaciones
anteriores, esto es lo que necesitas saber antes de tocar nada.

El [`README.md`](README.md) explica cómo funciona el código. Este archivo explica
**por qué está hecho así**, qué decisiones ya se tomaron, y qué sigue abierto.

---

## 1. Qué resuelve

Determinar qué producto está bloqueado y por qué, cruzando el stock de bodega con
los resultados de laboratorio y las detenciones declaradas por correo.

Antes de esto, la información vivía en planillas separadas y nadie podía responder
"¿este packing list tiene producto bloqueado?" sin revisar a mano.

**Al 07/08/2026:** 2.153 lotes evaluados, 2.384 batches, 72.779 cajas en tres bodegas.
26.689 cajas bloqueadas, 19.706 candidatas a liberar, 25.637 liberadas.

Las 19.706 candidatas son el número que importa: **producto que ya tiene con qué
liberarse y solo espera una firma que hoy nadie puede dar**, porque `puede_firmar`
está en `false` para todos. 95 lotes con stock, casi todos por materia prima.

El salto respecto de la foto anterior (537 lotes, 14.048 cajas bloqueadas) son dos
orígenes nuevos incorporados el 07/08/2026 —la detención histórica y la materia
prima— más el binomio WPS/nitrito. Ver la sección 2.

---

## 2. El principio que ordena todo

Hay **dos naturalezas de bloqueo distintas**, y mezclarlas es el error que
este diseño evita:

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Laboratorio** | Derivado de los resultados y los criterios | El motor | Entero, cada corrida |
| **Detención** | Declarada por correo ante una desviación | Personas, desde el sitio | Nunca, solo se agrega |
| **Detención histórica** | Declarada en el Excel `Bloqueo 2026.xlsm` con su motivo | Personas | Nunca, solo se agrega |
| **Materia prima** | Heredado: la MP venía no conforme | El motor, vía `PRO-REG-46` | Entero, cada corrida |

La materia prima tiene además una regla de vigencia **propia**: su incumplimiento no
caduca por una muestra posterior del mismo lote, porque ese código es del proveedor y
cubre varias unidades (ver la sección 4). Lo cierra el resultado del producto
elaborado, o una firma.

### El destino es la única dimensión separable

El estado del lote se resuelve hacia **el destino más estricto**: si un cliente es de
EE.UU., el lote entero queda marcado. Eso no cambia — es lo que decide si el criterio
aplica. Pero deja invisible algo que hace falta para firmar: **una firma para Nacional
no libera el lote, y sin embargo alcanza a las cajas que van a Nacional.**

Y acá el dato existe, a diferencia de la letra de batch: **Fishken registra el cliente
caja por caja.** Que no se pueda separar por batch de ahumado no significa que no se
pueda separar por destino. Hoy hay **28 lotes con cajas de distinto destino** (13.234
cajas); 21 bloqueados o candidatos, con 12.043 cajas de las cuales 1.355 no tienen
destino restringido.

Dos cosas lo hacen visible, y **ninguna libera nada por sí sola**:

- `CAJAS POR DESTINO` — el reparto, en el detalle del lote y en el diálogo de firma,
  para que nadie firme "Nacional" sobre un lote mixto sin saber que no libera el lote.
- `BLOQUEO SOLO POR DESTINO` (`lote.solo_destino`) — lo decide el **motor**, nunca el
  navegador: derivar criterios en JavaScript sería tener la norma escrita dos veces.
  Es verdadero solo si lo único vigente es listeria, la línea no es refrigerada —ahí se
  exige siempre—, no hay nada declarado abierto, y el lote está marcado por EE.UU. o
  Costa Rica. Hoy: **5 lotes, 2.621 cajas.** La consulta de packing list lo usa cuando
  se declara el destino del despacho.

Si lo que bloquea es RAM o nitrito, el reparto **no ayuda**: esos criterios se exigen en
todos los mercados. Por eso el mensaje distingue, en vez de ofrecer el reparto siempre.

Sus valores por omisión son **opuestos**, y es deliberado:

- Sin resultado de laboratorio, un lote **no** está bloqueado por laboratorio.
- Con un bloqueo declarado abierto, sigue bloqueado. **La ausencia de evidencia no
  libera.**

**Lo declarado se cierra por su propio motivo.** Un bloqueo por listeria no lo levanta
un nitrito conforme, y uno por falta de documentación no lo levanta ninguna muestra:
el laboratorio no mide eso. La traducción de motivo escrito a criterio vive en
`config.py`, en `MOTIVOS_LAB`, y la propuesta deja dicho que el criterio se **infirió
del texto** — a diferencia de las detenciones, donde lo declara una persona.

**"Vida útil transcurrida" no es producto vencido.** Significa que se sobrepasaron los
límites operacionales de tiempo en proceso, y lo que esa demora pone en riesgo es la
carga microbiológica: **un RAM conforme posterior a la detención cierra el motivo**.
Varias de esas filas lo dicen textualmente ("quedará PNC hasta el resultado del
laboratorio"). Se leía como no medible en laboratorio, que es lo contrario. La
aclaración viaja pegada al veredicto en pantalla, en `MOTIVOS_NOTA`: el texto del
registro está escrito para quien ya sabe de qué se trata, y quien mira para firmar, no.

Esa línea se sostiene hasta en la base de datos: el rol `motor_bloqueos` no tiene
permiso de escritura sobre detenciones, decisiones ni criterios. Una corrida mala no
puede borrar una decisión firmada. Si vas a tocar el esquema, **no cruces esa línea**.

### Tres reglas que se repiten en todo el sistema

1. **El sistema propone, una persona firma.** Un re-muestreo conforme deja el lote
   como `CANDIDATO A LIBERAR`, nunca liberado. La firma vive en `REGISTRO
   DECISIONES.xlsx` y en la tabla `decision`.
2. **Ante falta de información, el criterio se aplica.** Si no se puede determinar
   la línea o el destino, no se exime nada. Se degrada hacia lo conservador.
3. **`NO APLICA` ≠ `SIN DATO`.** En un caso se midió y se decidió no exigirlo; en el
   otro nadie midió. La razón de la liberación es distinta y queda registrada.

---

## 3. Los criterios vigentes

Viven en [`config.py`](config.py). Cambiarlos ahí es visible en el diff, que es el punto.

| Criterio | Dónde aplica |
|---|---|
| **RAM** > 500.000 UFC/g, sobre el **promedio de réplicas** de la muestra; una réplica incontable (sobre el techo del método) basta para no conforme | Toda línea |
| **Binomio WPS/nitrito** | Refrigerada, **más bacon y wheel** (salen congelados pero se venden refrigerados en destino) |
| **Listeria** presencia | Refrigerada siempre; congelada solo con destino **EE.UU. o Costa Rica** |

El nitrito no decide solo: libera si **(nitrito ≥ 85 ppm y WPS > 3,5 %) o nitrito > 100 ppm**.
Bajo 85 bloquea aunque el WPS sobre. El WPS ya venía medido en el bloque fisicoquímico
del LAB-REG-08 (`%SAL`, `%H`, `WPS`, `NITRITO`, cada uno con tres réplicas y promedio);
solo faltaba leerlo.

Un criterio **deja de estar vigente** solo si hay muestras posteriores que vuelven a
medir *ese mismo criterio* y salen conformes. Una muestra posterior que no midió lo que
falló no es evidencia de nada. Y desde el 30/09/2026 esas muestras tienen que ser **de
la misma unidad de laboratorio** —el lote con su sufijo `*SSD`—: un conforme de otra
unidad no cierra la que falló.

### Dos decisiones del 30/09/2026

**La vigencia se decide por unidad, no por lote base.** El veredicto por unidad ya
agrupaba con el sufijo, pero el del lote (`resume()`) agrupaba por el código sin él, así
que `historia()` tomaba cualquier conforme posterior del mismo lote base como
re-muestreo. `@2VQ2629250H*37V` dio listeria en 1 de 5 y lo «cubrió» `*39W`, otro
producto de otro día; `@2VQ26292461D*37W` lo cubrió `*38W`, de otro juliano. El mismo
motor respondía distinto en los dos niveles, y el lote era el que llegaba a la firma.
Ahora cada unidad se evalúa sola, y basta una unidad no conforme para que el lote lo
sea en ese criterio. Una muestra **sin sufijo** es una unidad aparte: no se sabe a qué
día corresponde, así que no cierra a una con sufijo ni la cierra una con sufijo. Contra
el stock se sigue agregando por lote base, porque Fishken no registra el sufijo. El
contraargumento es que se bloquea de más cuando el laboratorio re-muestrea bien pero
anota otro sufijo; se aceptó porque ese error se corrige escribiendo bien el código, y
el contrario —liberar la unidad positiva con el conforme de otra— no se ve nunca.
Efecto sobre la foto del 30/09: 8 candidatos con stock (2.663 cajas) pasan a bloqueado
por esta regla sola. El diálogo de firma muestra en rojo cualquier unidad del lote que
siga no conforme (`lote.unidades_no_conformes`), como defensa en profundidad: con la
regla, esos lotes ya no deberían llegar a candidato. No impide firmar.

**RAM: 500.000 UFC/g sobre el promedio de réplicas.** Es la especificación vigente del
SSCA y la que aplica el dashboard de inocuidad (`parsers/reg08.py`). Aquí se exigían
100.000 a cada réplica, y los dos sistemas daban veredictos distintos sobre la misma
fila: `@2VQ26292472K*39L`, con réplicas 163.000 / 25.000 / 38.000, quedaba bloqueado en
uno y conforme en el otro. El promedio se calcula igual que allá, para que la norma no
quede escrita dos veces: lo que no es número no entra y el promedio se redondea a
entero. La evidencia de RAM se cuenta ahora en muestras, no en réplicas. Efecto: 55
muestras de producto terminado que fallaban por una réplica pasan a conformes; 94
siguen sobre el límite. Ninguna materia prima cambia.

**Una réplica incontable hace no conforme a la muestra, sea cual sea el promedio**
(también del 30/09/2026). Copiar el promedio del dashboard traía un flanco permisivo:
una réplica escrita «incontable», «>N», TNTC o INC —el conteo pasó el techo del
método— quedaba fuera del promedio, y bastaba que las otras dos salieran bajas para
absolver una placa que no se pudo contar. Ahora esa réplica decide sola, con el texto
«RAM: réplica incontable (sobre el techo del método)». `<N`, que es lo contrario —bajo
el límite de detección—, sigue fuera del promedio, y el vacío es sin dato. Cualquier
otro texto queda fuera y el motor lo avisa en consola. El contraargumento es que se
aparta del cálculo del dashboard; se aceptó porque la diferencia va hacia bloquear y el
dashboard se corrige con la misma regla. Hoy no mueve nada: en `RAM1`–`RAM5` de los dos
LAB-REG-08 no hay una sola réplica escrita como texto. Las expresiones reconocidas
viven en `config.RAM_TECHO`.

Las dos van en una sola versión de criterios (migración
`20260930120000_bloqueos_criterio_unidad_y_ram_promedio.sql`). Juntas, sobre la misma
foto: 6 lotes a bloqueado (2.165 cajas), 4 a liberado (902), 3 a candidato (199), y los
candidatos con stock bajan de 100 a 95.

### Tres decisiones más del 30/09/2026 (tarde)

Salieron de revisar el motor después de la regla por unidad, y van juntas en otra versión
de criterios (migración `20260930180000_bloqueos_criterio_cierre_por_unidad.sql`).

**Un lote de recorte de siete caracteres es un lote.** CAL-PRO-07 escribe el recorte y
despunte mensual como `[B][@]` + sigla + año + juliano: `SW26098` tiene 7 caracteres, y el
piso `MIN_LOTE = 8` lo descartaba junto con los correlativos que el laboratorio anota en
la columna del lote. `SW26107*16V`, rebanado en frío con listeria en 1 de 3, no tenía
veredicto en ninguna hoja ni en la consulta. El piso existe por `099` o `107`, así que no
se bajó: se reconoce la forma explícita `config.LOTE_CORTO` (juliano 001 a 366), y un
lote corto solo se empareja por igualdad, nunca por prefijo. En los LAB-REG-08 2025 y
2026 entran once unidades (`SW25154`, `SW25155`, `SW25162`–`SW25164`, `SW25167`,
`SW25189`, `SW25190`, `SW25195`, `SW26106` conformes; `SW26107` bloqueado) y en el
PRO-REG-46 2026 el enlace con `SW26133`; el stock de hoy no tiene ninguno. Siguen fuera,
por no tener esa forma: los correlativos `00`–`141` de PRUEBAS, `058*24J`, `NN` (tienda),
`147326`, `15246` y `15482` del xlsm, y `2420S0W*06L`, que es otra convención y conviene
confirmar con producción. El contraargumento es que una sigla de dos letras cualquiera
también entra; se aceptó porque hoy todo lo que calza es `SW` y un lote corto que entra
recibe veredicto, no lo pierde.

**Lo que se resume como conforme dice lo que no se exigió.** En `2CK2612041`,
`2CK2614044`, `2CK2617049` y `2CK2620051` la propuesta decía «conforme(s) en LISTERIA»
y entre esas muestras había una PRESENCIA que no se exige por ser línea congelada sin
EE.UU. ni Costa Rica. El veredicto era coherente con la regla; el texto engañaba a quien
firma. Ahora todo resumen de listeria que tenga una presencia no exigible la nombra con
unidad y fecha (`presencias_no_exigibles()`): la propuesta, el motivo de la liberación,
el «no aplica» y la columna LISTERIA («Ausencia (con PRESENCIA no exigible por
destino)»). Sin efecto en ningún estado: es texto.

**Lo declarado se cierra por unidad, y el criterio de la base se lee.** La columna
`detencion.criterios` es `criterio[]`, un enum propio, y psycopg la entrega como texto
`{LISTERIA,RAM}`; el motor partía por `;`, no reconocía el criterio y ninguna detención de
la base se podía cerrar contra laboratorio. El error iba hacia bloquear, pero arreglar
solo la lectura las habría cerrado con un conforme de otra unidad, que es el error R1 de
esta misma mañana. Así que se corrigieron las dos cosas juntas:

- `lee_criterios()` acepta arreglo de Postgres, lista, JSON o el texto del xlsx, sin
  importar mayúsculas ni espacios. Un criterio desconocido, o ninguno, deja la detención
  vigente sin propuesta de cierre.
- `cierre_por_unidad()` cierra una detención, una fila de detención histórica o un
  bloqueo heredado de la materia prima solo si, para cada criterio de su motivo: hay una
  muestra estrictamente posterior al día del evento que lo mide, del alcance y del propio
  lote; ninguna muestra del alcance ni del lote lo incumple desde el día del evento; y
  cada unidad alcanzada con resultados el día del evento o antes (o sin fecha) tiene su
  propia muestra posterior que lo mide. Una detención sobre el lote base alcanza a todas
  sus unidades, también a las de sus batches hermanos; una con sufijo, solo a esa unidad,
  y solo ella la cierra. Cada traza de una detención histórica se cierra por separado.
- El chequeo de fallas mira el mismo conjunto que la regla anterior y algo más, de modo
  que la regla nueva no puede cerrar nada que antes quedaba abierto. Se verificó sobre la
  foto: ninguna detención histórica ni materia prima pasa de bloquear a cerrable.
- `firmada()`: una firma alcanza a la clave sobre la que se firmó y a lo que contiene.
  Antes bastaba que se emparentaran en cualquier sentido, y el sufijo se perdía al
  normalizar, así que una firma sobre el batch M o sobre la unidad `*37V` liberaba el lote
  entero. Hoy no hay firmas, así que no movió nada.

Efecto sobre la foto de la corrida 130: **47 candidatos pasan a bloqueado, 27 con stock
(4.440 cajas)**, y ninguno va hacia liberado ni candidato; los candidatos con stock bajan
de 95 a 68. 35 de los 47 son trazas del xlsm escritas con el sufijo de rebanado de SAP
(`2CK2612041*7M`, `@2CK2621054*09L`) o con una letra de batch (`2CK2569272A`) que el
laboratorio nunca muestreó con ese código: los conformes eran de otros días o de otros
batches. 6 dependían de una muestra del mismo día del bloqueo, 4 de una unidad con
resultado previo sin re-muestreo propio, y 2 tienen una PRESENCIA posterior en un batch
hermano que la traza alcanza. Tres de los cuatro lotes del hallazgo de texto
(`2CK2612041`, `2CK2617049`, `2CK2620051`) quedan bloqueados por esta regla, no por la del
texto. Las 29 detenciones abiertas de la base siguen bloqueando, porque una detención solo
la cierra una persona; 23 tienen ahora propuesta LIBERABLE con su evidencia por unidad.

El contraargumento es el costo: una traza con sufijo de SAP solo se cierra si el
laboratorio muestrea ese día de rebanado con ese mismo código, o con una firma, y como
Fishken no registra el sufijo el lote entero queda bloqueado en bodega. Se aceptó porque
la otra lectura —que el conforme de otro día o de otro batch cierre la detención de este—
es exactamente lo que se corrigió en la mañana, y si una traza está mal escrita se corrige
en el xlsm; si está bien escrita, nadie re-muestreó esa unidad. Ojo con un punto que hay
que confirmar: el contexto global todavía dice que el sufijo `*SSD` «solo existe en SAP y
se puede descartar al cruzar»; lo de hoy se apoya en la confirmación del 30/09 de que
distingue unidades.

**Destino:** EE.UU. se detecta por cliente (`LLC`, `INC`, Echo Falls, Slade Gorton,
Ocean Sky, Global Star) o por producto (wheel, bacon, cold smoked, sliced…).
Costa Rica: el cliente lleva **`PMT`**.

Cada cambio de criterio queda registrado en `historial/criterios.csv`, y el log de
cambios marca si una transición vino de un resultado nuevo o de un cambio de norma.
Sin eso, ajustar un límite y liberar 60 lotes se ve igual que recibir 60 conformes.

---

## 4. Trampas del dominio que cuestan caro

Todas se descubrieron rompiendo algo. No las deshagas.

- **`@` y `B` son parte del código de lote.** `@` es ASC, `B` es BAP.
  `2AS2621170M` y `B2AS2621170M` son lotes distintos, con curados y resultados
  distintos. Normalizarlos fuera fusiona lotes y cruza resultados entre ellos.
- **La letra final es el batch de ahumado** y también configura lote distinto.
  El laboratorio y los correos trabajan a ese nivel; **Fishken no registra la letra**.
  Por eso un lote de bodega arrastra a todos sus batches y hay miles de cajas
  bloqueadas por un batch que falló, sin poder separar las conformes.
- **La clave es el código normalizado, no la etiqueta visible.** 38 de 545 filas
  repetían etiqueta.
- **`TIPO = PRUEBAS` son ensayos del laboratorio, no producto despachable.** No bloquean ni
  liberan: se descartan al cargar. Se filtra por lo que dice `PRUEBAS`, no exigiendo que
  diga `PT`, para que una fila con el tipo en blanco no desaparezca sin que nadie lo note.
  Y el laboratorio a veces anota un correlativo (`099`, `107`) en la columna del lote:
  esos no tienen forma de lote y quedan fuera del veredicto, o aparecen en el listado de
  bloqueados como si fueran producto. **Pero el piso de 8 caracteres no es la forma de un
  lote:** el recorte y despunte mensual (`SW26098`, `SW26107*16V`) tiene 7, y quedaba fuera
  con los correlativos. Se reconoce por su forma (`config.LOTE_CORTO`), no bajando el piso.
- **El sufijo `*NNL` NO es descartable, aunque se creyó que sí durante meses.** Es semana
  y día de producción —coincide con la semana ISO de la fecha en el 98% de las muestras—
  y cada uno lleva su propio `LOTE JULIANO`. `@2CK26621761E*28V`, `*29L` y `*29W` son el 10,
  el 13 y el 15 de julio: solo el último salió con nitrito bajo. Descartarlo fusionaba días
  distintos y bastaba que el último fallara para bloquear a los anteriores. Hay **144 bases
  con unos sufijos conformes y otros no**. Contra el stock hay que seguir agregando —Fishken
  no registra el sufijo— pero cuando el packing list trae el código completo se responde por
  esa unidad. Y la vigencia se decide en la unidad también a nivel de lote: hasta el
  30/09/2026 el lote la decidía sin sufijo, y un conforme de otro día cerraba la listeria
  de la unidad que falló (ver la sección 3).
- **Una muestra posterior conforme de la MISMA materia prima no es un re-muestreo.**
  El código es el lote del **proveedor**, y cubre varios pallets y varias recepciones.
  Los cuatro casos que el motor leía como re-muestreo lo prueban: `26050004` tiene las
  dos muestras del mismo día (códigos 1292 `P` y 1293 `A`), y `26060014` dio `P` el
  12/06 y `A` el 15/06 con **dos recepciones distintas** en el `PRO-REG-46` bajo el
  mismo lote (pallets 2532/2533/2536 el 11/06 y 2590/2592/2595 el 15/06, con otra
  fecha de elaboración del proveedor). Es la trampa de la letra de batch otra vez: un
  conforme de otra unidad no cubre el incumplimiento de la que falló. Y encima **una
  materia prima desviada por listeria no se re-muestrea nunca**: se descarta o se
  decide sobre ella. Lo único que cierra un bloqueo de materia prima es el resultado
  propio del producto elaborado en ese mismo criterio, o una decisión firmada.
- **El lote de proveedor es otra convención, no la del lote SW.** Ahí el sufijo tras
  el guion es el pallet (`@4M1262004-VQ009F`), una celda puede traer varios lotes
  separados por `/`, y el prefijo de certificación y la confusión O/0 **sí** son ruido
  de transcripción. Normalizar los dos con la misma función pierde la mitad del cruce.
- **Un lote ausente no es un lote liberado.** Puede que su bodega se exportara antes
  de que ingresara.
- **En `Bloqueo 2026.xlsm` el `Estado` se escribe solo al liberar.** Una fila sin estado
  es un bloqueo vigente, no una fila incompleta. Las 420 filas `liberado` tienen todas
  fecha de liberación y las 2.591 sin estado ninguna, sin una sola excepción; el 95% de
  estas trae motivo escrito. Las 1.734 que dicen `Bloqueado` son un bloque contiguo de
  producción 2024–enero 2025, de la convención anterior: ahí hasta la columna
  `FECHA BLOQUEO` trae el motivo en texto en vez de una fecha.
- Hay confusiones de tipeo reales: `25281S0W` contra `25281SOW` (cero contra O), y
  lotes sin prefijo conviviendo con su gemelo prefijado.

---

## 5. Las fuentes y cómo se traen

| Fuente | Qué aporta | Cómo llega |
|---|---|---|
| Fishken | Stock por caja: cliente, condición, OF, producto | `descargar_fishken.py`, automático |
| LAB-REG-08 | Resultados de laboratorio, uno por año | `sincronizar_lab.py`, automático |
| `bloqueos.detencion` (Postgres) | Detenciones por correo | Se registran en el sitio, a nombre de quien las carga |
| `REGISTRO DETENCIONES.xlsx` | Las mismas, hasta el 10/08/2026 | **Histórico.** Solo se lee si no hay conexión |
| `REGISTRO DECISIONES.xlsx` | Liberaciones firmadas | Manual, y así debe ser |
| `Bloqueo 2026.xlsm` | Bloqueos declarados con su motivo, y liberaciones con mercado | Manual |
| `PRO-REG-46` | Ingreso de MP por proveedor: enlaza lote de proveedor con lote SW | `sincronizar_lab.py`, automático |

Ciclo completo:

```bash
python descargar_fishken.py      # baja las tres bodegas
python actualizar.py             # sincroniza lab, cruza, genera el HTML
python cargar_supabase.py        # sube a Postgres (requiere BLOQUEOS_DB_URL)
```

**Fishken** es ASP.NET WebForms: no hay URL de exportación, hay que pedir la página,
leer los tokens y enviar el formulario, tres veces. `T0 = TODAS` **no sirve para
exportar** — la búsqueda trae las ocho bodegas pero el botón baja solo la primera.

**Hay ocho bodegas y usamos tres.** Faltan CAMARA PNC, VILA, VIMU y dos de inventario.
La de PNC importa: ahí debería estar físicamente lo declarado no conforme.

---

## 6. Infraestructura

| Pieza | Dónde | Notas |
|---|---|---|
| Código | `github.com/Southwind-QA/Bloqueos` | Sin datos: los xlsx están en `.gitignore` |
| Base de datos | Supabase, proyecto MUM/MDQ, esquema `bloqueos` | Compartido con otra app; separado por esquema |
| Sitio | **`https://bloqueos.serranito.win`** — Worker de Cloudflare con `[assets]`, carpeta `web/` | Estático, sin build. Ver `wrangler.toml` |
| Corrida del motor | Tarea programada de Windows en este equipo | `Control de bloqueos - motor`, cada 2 h de 07:00 a 19:00 |

**El sitio tiene dos puertas, no una.** Delante de la aplicación hay **Cloudflare
Access** (`calidad-southwind.cloudflareaccess.com`), y detrás está el login propio
contra Supabase. Son listas distintas: alguien que esté en `persona_autorizada` pero
no en la política de Access no llega ni a ver la pantalla de login, y alguien que pase
Access sin estar en `persona_autorizada` entra y no ve absolutamente nada. **Al invitar
a las 14 personas hay que darlas de alta en las dos.**

**El motor corre en este equipo y no puede correr en otro lado.** Fishken y el
`\\192.168.2.201` del laboratorio están en la red interna: GitHub Actions no los
alcanza, por eso la automatización es una tarea programada local y no un workflow.
La tarea corre **solo con la sesión iniciada** —para correr con el equipo bloqueado
Windows exige guardar la contraseña de la cuenta, y eso no se hizo a propósito—, así
que si nadie inicia sesión, no hay corrida. El log queda en `historial/corridas.log`.

**Pasos manuales que no van al repositorio:**

- `alter role motor_bloqueos login password '...'` — la credencial del motor. **Al rol
  nunca se le había fijado una, y eso se descubrió el 10/08/2026**: las contraseñas se
  guardan cifradas, no se pueden leer, solo reemplazar. Cambiarla no afecta a nadie más:
  ese rol lo usa únicamente `cargar_supabase.py`; el sitio entra con la clave publishable
  y RLS, y las migraciones se aplican como `postgres`.
- La cadena de conexión va en `BLOQUEOS_DB_URL`, hoy en el `.env` local (ver
  `.env.ejemplo`). Usa el **Session pooler**, y el usuario lleva el project ref pegado
  con un punto: `motor_bloqueos.<project-ref>`. Sin eso el pooler responde
  `no tenant identifier provided`. La conexión directa es solo IPv6 y no resuelve desde
  equipos sin IPv6.
- **Conviene que la clave sea larga pero solo de letras y números.** Con `# @ / : % ?`
  hay que codificarla dentro de la URL (`%23 %40 %2F %3A %25 %3F`), y un error ahí da
  errores que no se parecen a la causa. `bloqueos.bat revisar` descompone la cadena sin
  mostrar la clave y prueba la conexión: es lo primero que hay que correr cuando algo
  no conecta.
- Las migraciones se aplicaron **a mano** en el SQL Editor. La integración de GitHub
  quedó conectada pero nunca ejecutó nada; no se investigó por qué.

**Claves:** la `publishable` va dentro del sitio, es pública por diseño. La `secret`
salta RLS y **nunca** debe estar en el código ni en un chat.

---

## 7. Errores cometidos y cómo se detectaron

Vale más que la lista de funcionalidades: son las formas en que este sistema puede
fallar en silencio.

| Error | Cómo se notó | Lección |
|---|---|---|
| Normalizar la `B` fuera del lote | Un correo listaba `2AS2621170M` y `B2AS2621170M` por separado | El dato de negocio manda sobre la intuición de limpieza |
| El universo excluía lotes con resultado reprobado sin stock | Un packing list dio "no reconocido" para un lote con nitrito 59 | Lo invisible es peor que lo incorrecto |
| Supabase corta la API en 1.000 filas | Muchas líneas daban "sin resultado de lab" | Todo truncamiento silencioso falla hacia lo permisivo |
| RLS también aplica al rol del motor | El cargador no veía la versión de criterios | `GRANT` y RLS son capas distintas; hay que resolver las dos |
| La etiqueta visible como clave primaria | `duplicate key` al cargar | La clave es el código normalizado |
| Detectar el login por ausencia del formulario | Login correcto daba "credenciales inválidas" | Fishken devuelve la misma pantalla con un `window.open` |
| Dos copias del mismo año del LAB-REG-08 | Se detectó al sincronizar | Habría duplicado 2.432 muestras sin avisar |
| `cmd` cortaba el `.env` en el `#` de la clave | `failed to resolve host motor_bloqueos.xxxx`: psycopg tomaba el usuario como servidor | Un error de conexión rara vez nombra su causa. Ahora el `.env` lo interpreta Python y `revisar` descompone la cadena |
| La consulta de packing list no miraba la detención histórica | Al incorporarlo: un lote bloqueado por correo con laboratorio conforme salía LIBERADO | La consulta resuelve contra el lab; cada origen nuevo hay que llevarlo **también** ahí, o el agujero queda justo en la pregunta que más se hace |
| Leer las filas sin estado como si no existieran | 18.221 cajas figuraban liberadas, 11.551 de ellas declaradas por listeria | Una columna vacía es un dato: hay que averiguar qué convención la deja vacía antes de ignorarla |
| Leer "vida útil transcurrida" como producto vencido | Lo dijo Calidad revisando los mensajes en pantalla | Un motivo escrito a mano hay que traducirlo con quien lo escribe, no inferirlo del castellano. El motor decía "no se mide en laboratorio" justo del motivo que **solo** se cierra con laboratorio |
| La hoja `FUENTES` declaraba el total en cada archivo | Los cuatro `PRO-REG-46` decían 466 registros y la misma ventana de fechas, exactos | La hoja que existe para declarar cobertura parcial la estaba inflando cuatro veces. El número era el de las muestras de MP del laboratorio, que no salen de esos archivos: la fila se los prestaba. **Una cifra repetida idéntica en varias filas es un síntoma, no una coincidencia** |
| El lote decidía la vigencia sin el sufijo, la unidad con él | El cuarto revisor, el 30/09/2026: `@2VQ2629250H*37V` positivo, «cubierto» por `*39W` de otro producto y otro día, y el lote en candidato | Una regla escrita bien en un nivel no protege si el otro nivel la reimplementa. La trampa de la letra de batch, una tercera vez |
| El piso de 8 caracteres como definición de lote | `SW26107*16V`, recorte con listeria en 1 de 3, no tenía veredicto (30/09/2026) | Un filtro contra el ruido tiene que describir el ruido, no el largo de lo bueno: el recorte mensual mide 7 |
| Leer `detencion.criterios` partiendo por `;` | Las detenciones de la base nunca se podían cerrar: psycopg entrega el `criterio[]` como texto `{LISTERIA,RAM}` (30/09/2026) | Un error que va hacia bloquear también esconde otro: arreglar solo la lectura las habría cerrado por lote base |
| Cerrar lo declarado con evalua() sobre el lote base | Revisando el arreglo de lo anterior: 47 candidatos se sostenían con conformes de otros días o de otros batches, o con una muestra del mismo día del bloqueo | La regla por unidad tiene que valer en todos los caminos que cierran algo con muestras posteriores, no solo en el veredicto del laboratorio. La trampa de la letra de batch, una cuarta vez |
| Resumir como «conforme» una listeria con PRESENCIA no exigible | Cuatro propuestas de `2CK26…` decían «conforme(s) en LISTERIA» | El texto que lee quien firma es parte del veredicto: lo que no se exige se dice, con unidad y fecha |
| Aplicar la regla de re-muestreo del producto a la materia prima | Calidad dijo "nunca haremos un re-muestreo a una materia prima desviada por listeria", y el `PRO-REG-46` lo confirmó: eran otros pallets | **Un veredicto correcto por un argumento falso sigue siendo un error.** No movió ni un lote —los 9 afectados ya se sostenían con los análisis del producto terminado— pero el motor le mostraba a quien firma una evidencia inexistente, y el próximo caso sin cobertura del terminado se habría liberado solo |

---

## 8. Lo que sigue abierto

**Preguntas sin responder que bloquean trabajo:**

1. ~~**Quién puede firmar.**~~ **Resuelto el 18/08/2026:** firman Tania Brito, Matías
   Chamorro, Carolina Bustos y Camilo Singer. La migración
   `20260818120000_bloqueos_puede_firmar.sql` lo deja escrito; **falta aplicarla en el
   SQL Editor** como `postgres` — el rol del motor no puede tocar `persona_autorizada`,
   que es justamente la protección. Mientras no corra, `decision` sigue vacía y el sitio
   le responde "Tu cuenta no puede firmar liberaciones" a todo el mundo.
   Ojo: la atribución **no** es el rol. David Santibáñez y Alejandra Díaz tienen rol
   `calidad` y no firman: registran detenciones.
2. **Qué son VILA y VIMU**, y si las bodegas de inventario son stock real o un conteo
   paralelo. Si es lo segundo, sumarlas duplicaría.
3. **44 lotes con conflicto**: figuran liberados en la detención histórica pero el
   laboratorio mantiene un incumplimiento vigente. 2.866 cajas.
4. **Las liberaciones declaradas se detienen el 19/12/2025.** Siete meses sin registrar
   ninguna, con 118 concentradas ese día. Esto ahora **bloquea producto**: si un bloqueo
   se levantó sin escribirlo, el motor lo sigue dando por abierto. Es la dirección
   conservadora, pero conviene ponerse al día con el registro.
5. **24 filas con fecha de bloqueo futura** (hasta 16/07/2027), probable tipeo de año.
   Quedan bloqueadas sin forma de liberarse, porque ninguna muestra puede ser posterior.
   El motor lo avisa por consola y en la propuesta; la corrección va en el xlsm.
6. **2.109 de las 4.326 filas abiertas del xlsm no tienen `FECHA BLOQUEO`**, y sin
   fecha no se puede acreditar que una muestra sea posterior: el motor no puede
   proponer nada. Es hoy el cuello de botella más grande, más que los criterios. Se
   vio al corregir "vida útil": de 121 filas de ese motivo, **108 no tienen fecha**, así
   que la corrección solo alcanzó a mover un lote. Poner esas fechas libera producto
   sin cambiar una sola regla.

**Trabajo pendiente:**

- Aplicar a mano en el SQL Editor, **antes del merge** de la rama
  `fix/tres-hallazgos-motor`: **`20260930180000_bloqueos_criterio_cierre_por_unidad.sql`**
  (versión 6 de criterios: cierre de lo declarado por unidad, lectura de
  `detencion.criterios`, lotes de recorte). Sin ella el cargador aborta por huella.
  La `20260930120000_bloqueos_criterio_unidad_y_ram_promedio.sql` (versión 5) ya está
  aplicada, con el merge de `e534e63`.
- Aplicar a mano en el SQL Editor: **`20260818120000_bloqueos_puede_firmar.sql`**, la
  otra pendiente. Todas las anteriores están aplicadas, incluida
  `20260811150000_bloqueos_cajas_por_destino.sql` —que este documento daba por
  pendiente— y la huella de `config.py` calza con la versión 4 de `criterio_version`:
  verificado el 18/08/2026 contra la base.
- **Cambiar `huella_criterios()` sin registrar la versión en la base rompe la carga, en
  silencio para quien mira el sitio.** Pasó: el renombre a "detención histórica"
  (`d67625f`, 10/08 18:03) cambió la huella siete minutos después de la última corrida
  que entró (la 9, 17:56). `cargar_supabase.py` abortó en cada intento posterior y el
  sitio siguió mostrando "Registro operativo" durante un día. El candado es correcto
  —evita atribuir datos a una norma que no se aplicó— pero **cada cambio de huella
  necesita su migración en el mismo commit**.
- **36 lotes de materia prima no figuran en ningún `PRO-REG-46`** (Ventisqueros 11,
  Cooke 9, Australis 9, Agrosuper 3, Antártica 2, Lo Boza 2). Su bloqueo no se puede
  arrastrar a ningún producto. Ya no es falta de archivos —se cargan 2023 a 2026— sino
  ingresos puntuales sin registrar o mal escritos.
- **Lo Boza tiene su propio registro, el `PRO-REG-37`**, en la misma carpeta del
  servidor. Hoy aporta solo 2 lotes de MP, por eso se dejó fuera; si esa línea crece,
  se incorpora con el mismo mecanismo.
- Rotar la clave `sb_secret_` que quedó expuesta en un chat. Verificado el 18/08/2026:
  no está en el repositorio ni en el historial de git, solo mencionada por nombre.
- Invitar a las 14 personas autorizadas, **en Cloudflare Access y en
  `persona_autorizada`**: son dos listas y hacen falta las dos (ver la sección 6).
- ~~Automatizar el motor en GitHub Actions.~~ **Hecho el 18/08/2026 como tarea
  programada local**, porque las fuentes están en la red interna y Actions no las
  alcanza. Ver la sección 6.
- El monitor de cámaras (`192.168.3.3`) como fuente de producto en proceso: es en vivo,
  no requiere autenticación y trae Pallet ID, que es lo que falta para las detenciones
  de cantidad parcial. Se evaluó y se dejó fuera porque no tiene cliente ni condición.
- La trazabilidad de proceso de ese mismo sistema (`search_traza.php`) enlaza materia
  prima con los productos derivados. Es la pieza para la etapa de materias primas.

---

## 9. Cómo trabajar en esto

- **Verifica contra los datos, no contra la intuición.** Casi todos los errores de
  arriba se encontraron midiendo, no razonando.
- **Cuando cambies un criterio, mira el historial.** Si 60 lotes cambian de estado,
  tiene que quedar claro si fue por la regla o por resultados nuevos.
- **No hagas que el sistema libere solo.** Puede proponer, calcular, sugerir. Firmar es
  de una persona con nombre y RUT.
- Si algo se degrada, que se degrade hacia bloquear de más, nunca hacia liberar de más.
