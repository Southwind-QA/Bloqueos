# Llevar el control de bloqueos a la web — estructura para conversar

Borrador para revisar. No hay nada implementado.

---

## 1. Qué problema resuelve pasar a la web

Hoy tenemos tres limitaciones que no se arreglan con más planilla:

1. **No es consultable en cualquier momento.** El HTML es una foto local; hay que correr el script y pasarse el archivo.
2. **Nadie firma nada.** El sistema propone liberaciones y cierres de detención, pero no hay dónde registrar quién decidió. Para un control de inocuidad eso es lo que falta.
3. **El historial depende de que alguien corra el script.** Si nadie corre, no hay registro del cambio.

El punto 2 es el que obliga a base de datos. Un sitio estático puede resolver el 1 y el 3, pero no el 2: **firmar requiere identidad y escritura**.

---

## 2. Principio que hay que mantener

El mismo que venimos sosteniendo: **separar lo derivado de lo declarado**.

| | Qué es | Quién lo escribe | Se recalcula |
|---|---|---|---|
| **Derivado** | Veredicto por lote y por batch, causas, evidencia | El motor de criterios | Sí, entero, cada corrida |
| **Declarado** | Detenciones, liberaciones firmadas, criterios vigentes | Personas | Nunca, solo se agrega |

En la base de datos esto son dos grupos de tablas con permisos distintos. El job de cálculo **no puede tocar** las tablas declaradas. Si se rompe esa línea, una corrida mala borra decisiones firmadas.

---

## 3. Arquitectura propuesta

```
Fishken ─┐
LAB-REG-08 ─┼─► Storage (archivos crudos) ─► Job Python (motor de criterios) ─► Postgres
Correos ─┘                                                                        │
                                                                                  ▼
                                                        Frontend ◄── Auth (RUT + rol)
```

**Componentes**

| Capa | Herramienta | Por qué |
|---|---|---|
| Archivos crudos | Supabase Storage (o Cloudflare R2) | Los xlsx no van al repositorio: pesan 9 MB y son datos comerciales |
| Base de datos | Supabase (Postgres) | Trae Auth + RLS + Storage en un solo lugar; el volumen es chico |
| Motor de criterios | Python, en GitHub Actions | Es el código que ya existe y funciona. No se reescribe |
| Frontend | Cloudflare Pages | Gratis, rápido, y ya lo tienen en el radar |
| Identidad | Supabase Auth + tabla de usuarios con RUT y rol | Ver punto 5 |
| Código | GitHub | Solo código y migraciones, nunca datos |

**Lo que NO haría**

- **No reescribir el motor de criterios en JavaScript ni en SQL.** La lógica de línea, destino, vigencia por re-muestreo y bacon/wheel es donde vive el conocimiento del negocio. Queda en Python, versionada, con pruebas.
- **No mandar todo el dataset al navegador.** Hoy el HTML embebe los 545 lotes y 2.381 batches. Con control de acceso eso es un problema: cualquiera con login descarga todo. El frontend consulta y filtra en el servidor.
- **No poner xlsx en el repositorio.**

---

## 4. Modelo de datos (primer boceto)

**Derivadas** (las reescribe el job)
- `veredicto_lote` — lote, estado, causas, motivo, evidencia, línea, destino, cajas, kg, bodegas
- `veredicto_batch` — batch, estado, causas, muestras, fechas, re-muestreo
- `muestra_lab` — el LAB-REG-08 normalizado, una fila por muestra
- `stock_caja` — el stock normalizado (o agregado por lote, si 77 mil filas resultan innecesarias)

**Declaradas** (solo crecen, nunca se pisan)
- `detencion` — la que hoy es REGISTRO DETENCIONES.xlsx
- `decision` — **la tabla nueva y la más importante**: quién liberó qué, cuándo, contra qué evidencia, para qué mercados, con qué comentario
- `criterio_version` — los límites y las reglas vigentes, con fecha desde/hasta
- `corrida` — cada ejecución del job: hash de cada archivo fuente, versión de criterios, resultado
- `cambio_estado` — el historial que hoy es `cambios.csv`
- `auditoria` — append-only: actor, acción, antes, después, timestamp

**Regla dura:** en las declaradas no hay `UPDATE` ni `DELETE`. Corregir es insertar una fila que anula la anterior. Es lo que pide una auditoría.

---

## 5. Acceso con RUT — lo que hay que decidir

**El RUT no puede ser la contraseña.** Es público-ish, tiene dígito verificador calculable y circula en mil formularios. Sirve como *identificador*, no como secreto.

Tres opciones, de menos a más fricción:

| Opción | Cómo entra la persona | Firma sirve para auditoría | Fricción |
|---|---|---|---|
| A. Cloudflare Access, correo corporativo | Código al mail @southwind.cl | Sí (identidad = correo) | Baja |
| B. Supabase Auth, correo + contraseña, RUT en el perfil | Correo y clave | Sí (identidad = persona, RUT registrado) | Media |
| C. RUT + contraseña | RUT y clave | Sí | Media, pero hay que administrar claves |

**Recomiendo B.** El RUT queda como el identificador que se estampa en cada decisión firmada, y el acceso va por correo, que es lo que la gente ya tiene y se puede revocar al día siguiente de una desvinculación.

**Roles**
- `consulta` — ve todo, no escribe (bodega, comercial, planta)
- `calidad` — además firma liberaciones y cierra detenciones
- `admin` — además edita criterios y usuarios

Con RLS en Postgres el rol se aplica en la base, no en el frontend. Un usuario `consulta` no puede escribir aunque manipule el navegador.

**Nota legal, corta:** el RUT es dato personal bajo la Ley 19.628 y la nueva ley de protección de datos. Guardar una lista de RUTs con roles es legítimo, pero conviene que quede escrito para qué se usa y quién la administra.

---

## 6. Ingesta

**Stock (Fishken)** — dijiste que ya bajan los kilos en otra parte. **Necesito ver cómo lo hacen hoy**: si hay API, si es un reporte programado, o si alguien exporta a mano. De eso depende todo:
- Con API → el job la llama directo, sin intervención.
- Con export programado a una carpeta → un agente chico en un PC de planta que sube el archivo al Storage.
- A mano → página de carga con validación. Funciona, pero el atraso vuelve (hoy REPROCESO va tres semanas atrás del resto).

**LAB-REG-08** — asumo que sigue siendo Excel editado a mano por un buen tiempo. Entonces: página de carga con **validación al ingresar** y reporte de rechazo. Ya sabemos qué revisar, porque lo encontramos: fechas con texto adentro, lotes tipo "Lote Prueba", `25281S0W` contra `25281SOW`, prefijos `@`/`B` faltantes.

**Correos de detención** — se pueden leer del buzón (Graph API sobre el correo de calidad). Con una regla de seguridad: un correo puede **crear un bloqueo** en borrador de forma automática (dirección conservadora), pero **nunca liberar**. La persona confirma el alcance y los criterios antes de que quede firme.

---

## 7. Por fases

| Fase | Qué queda andando | Esfuerzo |
|---|---|---|
| **1. Publicar** | El HTML de hoy detrás de Cloudflare Access, regenerado por GitHub Actions. Resuelve "consultable en cualquier momento" | Chico |
| **2. Base de datos** | Supabase + job que escribe en Postgres + frontend que consulta. Se acaba el archivo de 1,4 MB y el historial deja de depender de que alguien corra el script | Medio |
| **3. Firmar** | Login con rol, tabla `decision`, auditoría. Liberar un candidato deja de ser un correo y pasa a ser un acto registrado | Medio |
| **4. Ingesta** | Fishken automático, carga validada del lab, correos a borrador | Depende de qué ofrezca Fishken |

La 1 se puede tener andando rápido y ya cambia el día a día. Las 2 y 3 van juntas: la base de datos sin firma no aporta tanto.

---

## 8. Lo que necesito de ti para avanzar

1. **Cómo se baja hoy el reporte de Fishken.** Es lo que define la fase 4 y puede cambiar el orden.
2. **La lista de RUTs con nombre y rol** (consulta / calidad / admin).
3. **Quién tiene atribución para firmar una liberación.** No es lo mismo que quién la tipea.
4. **Si el LAB-REG-08 va a seguir siendo Excel** o hay intención de reemplazarlo. Cambia cuánto invertir en la validación de carga.
5. **Si esto lo ve alguien fuera de South Wind** (cliente, auditor, SERNAPESCA). Si sí, hay que pensar vistas por cliente desde el principio, no después.

---

## 9. Un riesgo que quiero dejar escrito

Pasar a la web **no arregla la calidad de los datos de origen**, solo la hace más visible y más rápida de propagar. Todo lo que encontramos sigue igual: el stock de una bodega tres semanas atrasado, el registro operativo con 2.591 filas sin estado, las liberaciones declaradas detenidas el 19/12/2025, el lote que no distingue batch de ahumado.

Si el sitio muestra un lote como liberado porque el archivo llegó incompleto, el error viaja más rápido que hoy. Por eso la validación en la ingesta y el aviso de fuente desactualizada no son adorno: son parte del diseño.
