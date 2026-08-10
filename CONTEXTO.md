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
orígenes nuevos incorporados el 07/08/2026 —el registro operativo y la materia
prima— más el binomio WPS/nitrito. Ver la sección 2.

---

## 2. El principio que ordena todo

Hay **dos naturalezas de bloqueo distintas**, y mezclarlas es el error que
este diseño evita:

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Laboratorio** | Derivado de los resultados y los criterios | El motor | Entero, cada corrida |
| **Detención** | Declarada por correo ante una desviación | Personas, desde el sitio | Nunca, solo se agrega |
| **Registro operativo** | Declarado en `Bloqueo 2026.xlsm` con su motivo | Personas | Nunca, solo se agrega |
| **Materia prima** | Heredado: la MP venía no conforme | El motor, vía `PRO-REG-46` | Entero, cada corrida |

Sus valores por omisión son **opuestos**, y es deliberado:

- Sin resultado de laboratorio, un lote **no** está bloqueado por laboratorio.
- Con un bloqueo declarado abierto, sigue bloqueado. **La ausencia de evidencia no
  libera.**

**Lo declarado se cierra por su propio motivo.** Un bloqueo por listeria no lo levanta
un nitrito conforme, y uno por falta de documentación no lo levanta ninguna muestra:
el laboratorio no mide eso. La traducción de motivo escrito a criterio vive en
`config.py`, en `MOTIVOS_LAB`, y la propuesta deja dicho que el criterio se **infirió
del texto** — a diferencia de las detenciones, donde lo declara una persona.

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
| **RAM** > 100.000 UFC/g | Toda línea |
| **Binomio WPS/nitrito** | Refrigerada, **más bacon y wheel** (salen congelados pero se venden refrigerados en destino) |
| **Listeria** presencia | Refrigerada siempre; congelada solo con destino **EE.UU. o Costa Rica** |

El nitrito no decide solo: libera si **(nitrito ≥ 85 ppm y WPS > 3,5 %) o nitrito > 100 ppm**.
Bajo 85 bloquea aunque el WPS sobre. El WPS ya venía medido en el bloque fisicoquímico
del LAB-REG-08 (`%SAL`, `%H`, `WPS`, `NITRITO`, cada uno con tres réplicas y promedio);
solo faltaba leerlo.

Un criterio **deja de estar vigente** solo si hay muestras posteriores que vuelven a
medir *ese mismo criterio* y salen conformes. Una muestra posterior que no midió lo que
falló no es evidencia de nada.

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
- **El sufijo `*NNL`** de los lotes del laboratorio (semana y turno) sí es descartable.
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
| `REGISTRO DETENCIONES.xlsx` | Detenciones por correo | Manual, y así debe ser |
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
| Sitio | Cloudflare Pages, carpeta `web/` | Estático, sin build |

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
| La consulta de packing list no miraba el registro operativo | Al incorporarlo: un lote bloqueado por correo con laboratorio conforme salía LIBERADO | La consulta resuelve contra el lab; cada origen nuevo hay que llevarlo **también** ahí, o el agujero queda justo en la pregunta que más se hace |
| Leer las filas sin estado como si no existieran | 18.221 cajas figuraban liberadas, 11.551 de ellas declaradas por listeria | Una columna vacía es un dato: hay que averiguar qué convención la deja vacía antes de ignorarla |

---

## 8. Lo que sigue abierto

**Preguntas sin responder que bloquean trabajo:**

1. **Quién puede firmar.** `puede_firmar` está en `false` para todos, así que hoy nadie
   puede ejecutar una liberación. El `update` está al final de la migración de personas.
   Es lo que más urge: hay **19.706 cajas candidatas** esperando una firma que nadie
   puede dar. Todo lo demás que se construyó desemboca ahí.
2. **Qué son VILA y VIMU**, y si las bodegas de inventario son stock real o un conteo
   paralelo. Si es lo segundo, sumarlas duplicaría.
3. **44 lotes con conflicto**: figuran liberados en el registro operativo pero el
   laboratorio mantiene un incumplimiento vigente. 2.866 cajas.
4. **Las liberaciones declaradas se detienen el 19/12/2025.** Siete meses sin registrar
   ninguna, con 118 concentradas ese día. Esto ahora **bloquea producto**: si un bloqueo
   se levantó sin escribirlo, el motor lo sigue dando por abierto. Es la dirección
   conservadora, pero conviene ponerse al día con el registro.
5. **24 filas con fecha de bloqueo futura** (hasta 16/07/2027), probable tipeo de año.
   Quedan bloqueadas sin forma de liberarse, porque ninguna muestra puede ser posterior.
   El motor lo avisa por consola y en la propuesta; la corrección va en el xlsm.

6. **Dónde vive el registro de detenciones.** Desde el 10/08/2026 el sitio las escribe en
   Postgres —el esquema ya lo preveía: la policy `detencion_alta` deja insertar a `calidad`
   y `admin`, y el rol del motor solo puede leer—. Pero `cruce2.py` sigue leyendo
   `REGISTRO DETENCIONES.xlsx`. Mientras las dos fuentes convivan, una detención cargada
   en el sitio **no entra al cruce** hasta que alguien la copie al Excel. Hay que elegir:
   que el motor lea de Postgres, o que el sitio siga exportando filas para el Excel.

**Trabajo pendiente:**

- Aplicar a mano en el SQL Editor, antes de la próxima carga a Postgres:
  `20260807140000_bloqueos_materia_prima.sql`. (Las de `motivo_operativo`, `wps` y sus
  versiones de criterios ya se aplicaron el 07/08/2026.)
- **36 lotes de materia prima no figuran en ningún `PRO-REG-46`** (Ventisqueros 11,
  Cooke 9, Australis 9, Agrosuper 3, Antártica 2, Lo Boza 2). Su bloqueo no se puede
  arrastrar a ningún producto. Ya no es falta de archivos —se cargan 2023 a 2026— sino
  ingresos puntuales sin registrar o mal escritos.
- **Lo Boza tiene su propio registro, el `PRO-REG-37`**, en la misma carpeta del
  servidor. Hoy aporta solo 2 lotes de MP, por eso se dejó fuera; si esa línea crece,
  se incorpora con el mismo mecanismo.
- Rotar la clave `sb_secret_` que quedó expuesta en un chat.
- Invitar a las 14 personas autorizadas.
- Automatizar el motor en GitHub Actions.
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
