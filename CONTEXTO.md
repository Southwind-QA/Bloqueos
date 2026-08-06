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

**Al 06/08/2026:** 537 lotes evaluados, 2.381 batches, 72.779 cajas en tres bodegas.
185 lotes bloqueados (14.048 cajas, 26.942 kg), 16 candidatos a liberar, 321 liberados.

---

## 2. El principio que ordena todo

Hay **dos orígenes de bloqueo con naturaleza distinta**, y mezclarlos es el error que
este diseño evita:

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Laboratorio** | Derivado de los resultados y los criterios | El motor | Entero, cada corrida |
| **Detención** | Declarado por correo ante una desviación | Personas | Nunca, solo se agrega |

Sus valores por omisión son **opuestos**, y es deliberado:

- Sin resultado de laboratorio, un lote **no** está bloqueado por laboratorio.
- Con una detención abierta, sigue bloqueado. **La ausencia de evidencia no libera.**

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
| **Nitrito** < 85 ppm | Refrigerada, **más bacon y wheel** (salen congelados pero se venden refrigerados en destino) |
| **Listeria** presencia | Refrigerada siempre; congelada solo con destino **EE.UU. o Costa Rica** |

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
- **Un lote ausente no es un lote liberado.** Puede que su bodega se exportara antes
  de que ingresara.
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
| `Bloqueo 2026.xlsm` | Registro operativo: liberaciones declaradas con mercado | Manual |

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

- `alter role motor_bloqueos login password '...'` — la credencial del motor.
- La cadena de conexión va en `BLOQUEOS_DB_URL`. Usa el **Session pooler**: la conexión
  directa es solo IPv6 y no resuelve desde equipos sin IPv6.
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

---

## 8. Lo que sigue abierto

**Preguntas sin responder que bloquean trabajo:**

1. **Las 2.591 filas sin estado en `Bloqueo 2026.xlsm`.** Son 16.091 cajas cuyo bloqueo
   no se puede interpretar. ¿Estar en esa hoja ya significa bloqueado, o el estado tiene
   que estar escrito? Cambia el resultado por completo.
2. **Quién puede firmar.** `puede_firmar` está en `false` para todos, así que hoy nadie
   puede ejecutar una liberación. El `update` está al final de la migración de personas.
3. **Qué son VILA y VIMU**, y si las bodegas de inventario son stock real o un conteo
   paralelo. Si es lo segundo, sumarlas duplicaría.
4. **44 lotes con conflicto**: figuran liberados en el registro operativo pero el
   laboratorio mantiene un incumplimiento vigente. 2.866 cajas.
5. **Las liberaciones declaradas se detienen el 19/12/2025.** Siete meses sin registrar
   ninguna, con 118 concentradas ese día.

**Trabajo pendiente:**

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
