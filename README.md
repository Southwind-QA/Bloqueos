# Control de bloqueos — Frigorífico South Wind

Cruza el stock de bodega contra los resultados de laboratorio y las detenciones
declaradas por correo, y determina qué producto está bloqueado y por qué.

```bash
python actualizar.py
```

Deja dos entregables en la carpeta: el Excel de análisis y `CONSULTA BLOQUEOS.html`,
una página autocontenida para consultar sin conexión. Toma unos 4 minutos, casi
todo en leer los xlsx.

---

## El principio que ordena todo

Hay **dos orígenes de bloqueo con naturaleza distinta**, y mezclarlos es el error
que este diseño evita:

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Laboratorio** | Derivado de los resultados y los criterios | El motor | Entero, en cada corrida |
| **Detención** | Declarado por correo ante una desviación | Personas | Nunca, solo se agrega |

Sus valores por omisión son **opuestos**, y eso es deliberado:

- Sin resultado de laboratorio, un lote **no** está bloqueado por laboratorio.
- Con una detención abierta, sigue bloqueado. **La ausencia de evidencia no libera.**

Los dos orígenes se acumulan: un lote con ambos tiene que cerrar los dos.

## Los criterios

Viven en [`config.py`](config.py), comentados, para que un cambio de norma sea
visible en el diff y no haya que leer el motor.

| Criterio | Dónde aplica |
|---|---|
| **RAM** > 100.000 UFC/g | Toda línea, sin excepciones |
| **Nitrito** < 85 ppm | Línea refrigerada, **más bacon y wheel** (salen congelados de planta pero se venden refrigerados en destino) |
| **Listeria** presencia | Línea refrigerada siempre; línea congelada solo si el destino es **EE.UU. o Costa Rica** |

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
| `FRIGORÍFICO SOUTH WIND - *.xlsx` | Stock por caja: cliente, condición, OF, producto. Uno por bodega |
| `LAB-REG-08*.xlsx` | Resultados de laboratorio. Uno por año, con estructura levemente distinta entre años |
| `REGISTRO DETENCIONES.xlsx` | Detenciones por correo. **Se lee, nunca se sobrescribe** |
| `Bloqueo 2026.xlsm` | Registro operativo: liberaciones declaradas con su mercado |

Cada una tiene su propio corte, y la hoja `FUENTES` del Excel de salida lo deja
por escrito. Un lote ausente **no es un lote liberado**: puede ser que su bodega
se exportó antes de que ingresara.

## Estructura

```
config.py        criterios, límites y rutas
cruce2.py        el motor: normaliza, evalúa y escribe el Excel
gen_html.py      genera la página de consulta a partir del Excel
actualizar.py    corre los dos pasos en orden
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
