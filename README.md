# Control de bloqueos — Frigorífico South Wind

Cruza el stock de bodega contra los resultados de laboratorio y las detenciones
declaradas por correo, y determina qué producto está bloqueado y por qué.

> **¿Retomando este proyecto?** Parte por [`CONTEXTO.md`](CONTEXTO.md): las decisiones
> tomadas, las trampas del dominio y lo que sigue abierto. Este archivo explica cómo
> funciona el código; ese explica por qué.

Doble clic en **`bloqueos.bat`**, o desde la terminal:

```bash
python actualizar.py
```

El `.bat` hace el ciclo entero —baja el stock, cruza, genera la página y sube a
Postgres— y admite `sinstock` para reusar el stock ya bajado y `sinsubir` para no
tocar la base. Las credenciales las lee de `.env`, que no va al repositorio: copia
`.env.ejemplo` y complétalo.

Deja dos entregables en la carpeta: el Excel de análisis y `CONSULTA BLOQUEOS.html`,
una página autocontenida para consultar sin conexión. Toma unos 4 minutos, casi
todo en leer los xlsx.

---

## El principio que ordena todo

Hay **dos naturalezas de bloqueo distintas**, y mezclarlas es el error que este
diseño evita:

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Laboratorio** | Derivado de los resultados y los criterios | El motor | Entero, en cada corrida |
| **Detención** | Declarada por correo ante una desviación | Personas, desde el sitio | Nunca, solo se agrega |
| **Registro operativo** | Declarado en `Bloqueo 2026.xlsm` con su motivo | Personas | Nunca, solo se agrega |
| **Materia prima** | Heredado: la MP venía no conforme | El motor, vía `PRO-REG-46` | Entero, en cada corrida |

Sus valores por omisión son **opuestos**, y eso es deliberado:

- Sin resultado de laboratorio, un lote **no** está bloqueado por laboratorio.
- Con un bloqueo declarado abierto, sigue bloqueado. **La ausencia de evidencia
  no libera.**

Los cuatro orígenes se acumulan: un lote con varios tiene que cerrarlos todos.

### Lo que traía la materia prima

Si la materia prima estaba bloqueada, lo que se elaboró con ella también lo está.
El laboratorio registra la MP por `LOTE ORIGEN` + `PROVEEDOR` y deja el `LOTE SW`
vacío, así que esas muestras nunca entraban al cruce: el `PRO-REG-46` (ingreso de
MP por proveedor) es lo único que las enlaza con el producto.

A la materia prima solo le aplican **listeria y RAM** — no trae nitrito ni WPS, así
que el binomio no tiene nada que evaluar ahí.

**Lo que ya tiene con qué liberarse queda `CANDIDATO A LIBERAR`, no bloqueado.**
Son tres caminos, y en los tres lo único que falta es la firma:

1. La materia prima se **re-muestreó conforme** después.
2. El **producto terminado** tiene resultado propio posterior conforme en *todo* lo
   que la materia prima traía mal. El proceso —ahumado, altas presiones— es
   justamente lo que controla lo que venía en la materia prima.
3. Lo que falló fue **listeria y al producto no le aplica**, por ser línea congelada
   sin destino EE.UU. ni Costa Rica. Es la misma regla de listeria de siempre,
   aplicada al bloqueo heredado.

Si el respaldo del producto cubre solo parte de lo que falló, sigue bloqueado y la
propuesta dice qué criterio quedó sin cubrir. El argumento siempre queda escrito,
para que quien firme no tenga que ir a buscarlo al Excel.

**Cobertura:** se cargan los `PRO-REG-46` de 2023 a 2026 desde `\\192.168.2.201`,
donde los lleva producción. Con eso, 318 de los 354 lotes de MP del laboratorio
encuentran su producto; los 36 restantes no figuran en ningún registro de ingreso
y su bloqueo no se puede arrastrar. El motor lo declara en consola y en la hoja
`FUENTES`: un cruce parcial que no se declara se lee como cobertura total.

### Lo declarado se cierra por su propio motivo

Un bloqueo declarado trae escrito **por qué** se bloqueó, y solo lo levanta un
resultado posterior que vuelva a medir *ese* criterio y salga conforme. Un
bloqueo por listeria no se cierra con un nitrito conforme, y uno por falta de
documentación **no se cierra con ninguna muestra**: el laboratorio no mide eso.

En `Bloqueo 2026.xlsm` la columna `Estado` se escribe **únicamente al liberar**,
así que una fila sin estado es un bloqueo vigente. La evidencia está en el
comentario de `cruce2.py` que lee la hoja. Hoy son 2.019 lotes con bloqueo
abierto; 137 de ellos tienen stock, con 30.550 cajas.

## Los criterios

Viven en [`config.py`](config.py), comentados, para que un cambio de norma sea
visible en el diff y no haya que leer el motor.

| Criterio | Dónde aplica |
|---|---|
| **RAM** > 100.000 UFC/g | Toda línea, sin excepciones |
| **Binomio WPS/nitrito** | Línea refrigerada, **más bacon y wheel** (salen congelados de planta pero se venden refrigerados en destino) |
| **Listeria** presencia | Línea refrigerada siempre; línea congelada solo si el destino es **EE.UU. o Costa Rica** |

El nitrito no decide solo. Lo que controla *Listeria* en el ahumado es la
combinación de sal en fase acuosa y nitrito:

| WPS | nitrito < 85 | 85 ≤ nitrito ≤ 100 | nitrito > 100 |
|---|---|---|---|
| **> 3,5 %** | Bloquea | Libera | Libera |
| **3 – 3,5 %** | Bloquea | Bloquea | Libera |
| **< 3 %** | Bloquea | Bloquea | Libera |

Es decir: **libera si (nitrito ≥ 85 y WPS > 3,5) o nitrito > 100**. Escrita así,
la regla resuelve sola el caso sin WPS medido y hacia el lado correcto: con
nitrito bajo 100 no se puede acreditar el binomio, así que no libera.

Los criterios que puede levantar un motivo escrito a mano en el registro
operativo también viven en `config.py`, en `MOTIVOS_LAB`. Ahí se traduce el texto
libre (`presencia de LM`, `alto en ram`) al criterio que lo cierra. Un motivo que
no calce con ninguno no es liberable contra el laboratorio.

### Una firma puede cubrir solo parte

Firmar no es siempre liberar todo:

- **Por mercado.** Un congelado con destino EE.UU. exige listeria; el mismo producto
  a mercado nacional no. Si la firma dice `Nacional`, el lote **sigue bloqueado** para
  Echo Falls o Slade Gorton, y el motor lo dice.
- **Por tratamiento.** Las altas presiones hidrostáticas son un proceso letal que se
  aplica a un despacho completo. Levantan **listeria y RAM**, no lo fisicoquímico: un
  nitrito bajo sigue bajo después del APH, y ese lote queda bloqueado igual.

Los lotes que viajaron juntos se firman en bloque desde el sitio, pegando el packing
list del despacho, y cada uno queda con su firma propia bajo la misma `ruta`.

Tres reglas transversales:

1. **Un criterio deja de estar vigente** solo si hay muestras posteriores que
   vuelven a medir *ese mismo criterio* y salen conformes. Una muestra posterior
   que no midió lo que falló no es evidencia de nada. Cuando eso ocurre el lote
   queda **CANDIDATO A LIBERAR**, no liberado: el sistema propone, Calidad firma.
2. **Si el destino o la línea no se pueden determinar, el criterio se aplica.**
   No se exime nada por falta de información.
3. **NO APLICA ≠ SIN DATO.** En un caso se midió y se decidió no exigirlo; en el
   otro nadie midió. La razón de la liberación es distinta y queda registrada.

## Detalles del dominio que cuestan caro si se ignoran

- **`@` y `B` son parte del código de lote**, no ruido de exportación. `@` es ASC
  y `B` es BAP: `2AS2621170M` y `B2AS2621170M` son lotes distintos, con fechas de
  curado y resultados distintos. Normalizarlos fuera fusiona lotes y cruza
  resultados entre ellos.
- **La letra final es el batch de ahumado** y también configura lote distinto.
  El laboratorio y los correos trabajan a ese nivel; **el stock de Fishken no
  registra la letra**, así que un lote de bodega arrastra a todos sus batches.
  Hoy eso implica que ~20.000 cajas quedan bloqueadas por un batch que falló sin
  poder separar las conformes.
- El sufijo `*NNL` de los lotes del laboratorio (semana y turno) sí es descartable.

## Fuentes

| Archivo | Qué aporta |
|---|---|
| `FRIGORÍFICO SOUTH WIND - *.xlsx` | Stock por caja: cliente, condición, OF, producto. Los baja `descargar_fishken.py` |
| `LAB-REG-08*.xlsx` | Resultados de laboratorio. Uno por año, con estructura levemente distinta entre años |
| `bloqueos.detencion` | Detenciones por correo. Se registran **en el sitio**; el motor solo las lee, y su rol ni siquiera tiene permiso para escribirlas |
| `REGISTRO DETENCIONES.xlsx` | Las mismas hasta el 10/08/2026. Histórico: solo se usa si no hay conexión a la base |
| `Bloqueo 2026.xlsm` | Registro operativo: bloqueos declarados con su motivo, y liberaciones con su mercado |
| `*PRO-REG-46*.xlsx` | Ingreso de materia prima por proveedor. Enlaza el lote del proveedor con el lote SW: lo único que permite heredar el bloqueo de la MP |

Cada una tiene su propio corte, y la hoja `FUENTES` del Excel de salida lo deja
por escrito. Un lote ausente **no es un lote liberado**: puede ser que su bodega
se exportó antes de que ingresara.

## Estructura

```
config.py        criterios, límites y rutas
descargar_fishken.py  baja los reportes de stock desde Fishken, sin navegador
cruce2.py        el motor: normaliza, evalúa y escribe el Excel
gen_html.py      genera la página de consulta a partir del Excel
actualizar.py    corre la sincronización, el cruce y la página en orden
sincronizar_lab.py    trae los LAB-REG-08 y el PRO-REG-46 desde la carpeta del laboratorio
cargar_supabase.py    sube el resultado a Postgres
crear_decisiones.py   crea el registro de liberaciones firmadas
web/             el sitio que consulta la base (Cloudflare Pages)
valida.py        validador de paletas de color (port del de la skill dataviz)
supabase/        migraciones del esquema y los permisos (Supabase las aplica al mergear a main)
historial/       snapshot y log de cambios entre corridas (dato, no código)
```

`BLOQUEOS_DIR` permite mover la carpeta de datos sin tocar el código.

## Historial

El motor se recalcula entero en cada corrida, así que sin historial no habría
forma de saber que un lote estuvo bloqueado y después se liberó.

- `historial/estado_actual.csv` — la foto contra la que se compara. Se sobrescribe.
- `historial/cambios.csv` — las transiciones. Solo crece.
- `historial/criterios.csv` — qué reglas estaban vigentes en cada corrida.

Esa última existe para poder distinguir **un cambio por resultado nuevo de un
cambio por cambio de norma**. Sin ella, ajustar un criterio y liberar 60 lotes se
ve igual que recibir 60 resultados conformes.

## Despliegue

Ver [`PROPUESTA WEB.md`](PROPUESTA%20WEB.md) y `supabase/migrations/`. Lo importante del esquema:
el rol del motor **no tiene permiso de escritura** sobre detenciones, decisiones
ni criterios. Una corrida mala no puede borrar una decisión firmada.
