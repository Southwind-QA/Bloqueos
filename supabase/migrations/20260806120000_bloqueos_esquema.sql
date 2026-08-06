-- ============================================================================
--  Control de bloqueos - South Wind
--  Esquema inicial para Supabase / Postgres
--
--  Principio que ordena todo el archivo: separar lo DERIVADO de lo DECLARADO.
--
--    derivado : lo calcula el motor de criterios a partir del laboratorio y el
--               stock. Se reescribe entero en cada corrida. Nadie lo edita.
--    declarado: lo escriben personas (detenciones, liberaciones firmadas,
--               criterios). Solo crece. El motor NO puede tocarlo.
--
--  Si esa linea se cruza, una corrida mala borra decisiones firmadas. Por eso
--  el rol del job tiene permisos distintos al de las personas (ver 005).
-- ============================================================================

create schema if not exists bloqueos;
set search_path = bloqueos, public;

-- ---------------------------------------------------------------- catalogos
create type estado_lote as enum (
  'BLOQUEADO', 'CANDIDATO A LIBERAR', 'LIBERADO', 'SIN ANALISIS', 'PNC');

create type criterio as enum ('LISTERIA', 'RAM', 'NITRITO');

create type estado_criterio as enum (
  'CONFORME', 'NO CONFORME', 'REMUESTREO CONFORME', 'NO APLICA', 'SIN DATO');

create type rol_usuario as enum ('consulta', 'calidad', 'admin');

-- ============================================================================
--  DECLARADO
-- ============================================================================

-- Personas. El RUT identifica; el acceso va por auth.users (correo).
-- El RUT nunca es la contrasenia.
create table usuario (
  id            uuid primary key references auth.users(id) on delete restrict,
  rut           text not null unique check (rut ~ '^[0-9]{7,8}-[0-9kK]$'),
  nombre        text not null,
  rol           rol_usuario not null default 'consulta',
  puede_firmar  boolean not null default false,  -- atribucion, distinta del rol
  activo        boolean not null default true,
  creado        timestamptz not null default now()
);
comment on column usuario.puede_firmar is
  'Quien tiene atribucion para liberar. No es lo mismo que quien tipea: un rol '
  'calidad puede registrar sin poder firmar.';

-- Version de los criterios vigentes. Cambiar una regla es un acto auditable,
-- no un commit silencioso: sin esto no se puede saber si un lote cambio de
-- estado porque llego un resultado o porque cambiamos la norma.
create table criterio_version (
  id            bigserial primary key,
  desde         timestamptz not null default now(),
  hasta         timestamptz,
  huella        text not null,              -- resumen legible de las reglas
  parametros    jsonb not null,             -- limites y matriz linea/destino
  motivo        text not null,              -- por que se cambio
  autor         uuid references usuario(id),
  unique (huella, desde)
);

-- Detenciones declaradas por correo ante una desviacion de proceso.
create table detencion (
  id            text primary key,           -- DET-2026-001
  fecha_correo  date not null,
  emitido_por   text not null,
  referencia    text,                       -- asunto / buzon de origen
  tipo          text not null,              -- vida util excedida, curado, PNC...
  descripcion   text,
  lote          text not null,              -- con su prefijo @ o B
  producto      text,
  alcance       text not null,              -- LOTE | LOTE+PRODUCTO | OF | PARCIAL
  cantidad_kg   numeric,
  fecha_evento  date not null,              -- cuando ocurrio, no cuando se avisa
  resolucion    text not null,
  criterios     criterio[] not null default '{}',
  estado        text not null default 'ABIERTA',
  observacion   text,
  origen        text,
  creado        timestamptz not null default now(),
  creado_por    uuid references usuario(id),
  constraint detencion_estado_ok
    check (estado in ('ABIERTA', 'LIBERADA', 'PNC', 'ANULADA'))
);
comment on column detencion.fecha_evento is
  'Define desde cuando una muestra sirve para liberar. Una muestra anterior al '
  'evento no es evidencia.';

-- La tabla que hoy no existe en ninguna parte: quien decidio que.
-- Nunca se hace UPDATE ni DELETE. Corregir es insertar una fila que anula.
create table decision (
  id            bigserial primary key,
  tipo          text not null,              -- LIBERACION | CIERRE DETENCION | ANULACION
  lote          text,
  batch         text,
  detencion_id  text references detencion(id),
  anula         bigint references decision(id),
  mercados      text[],                     -- Nacional / Exportacion / USA...
  evidencia     text not null,              -- codigos y fechas de laboratorio
  criterio_ver  bigint not null references criterio_version(id),
  comentario    text,
  firmado_por   uuid not null references usuario(id),
  firmado_en    timestamptz not null default now(),
  constraint decision_apunta_a_algo
    check (num_nonnulls(lote, batch, detencion_id) >= 1)
);

-- Cada ejecucion del motor, con la huella de sus insumos.
create table corrida (
  id            bigserial primary key,
  inicio        timestamptz not null default now(),
  fin           timestamptz,
  criterio_ver  bigint references criterio_version(id),
  fuentes       jsonb not null,             -- archivo -> {hash, filas, corte}
  resultado     text,
  detalle       text
);

-- Historial de transiciones. Es lo unico que responde "estuvo bloqueado y
-- despues se libero".
create table cambio_estado (
  id            bigserial primary key,
  corrida_id    bigint not null references corrida(id),
  nivel         text not null check (nivel in ('lote', 'batch')),
  clave         text not null,
  estado_ant    text,
  estado_nuevo  text not null,
  causas        text,
  cajas         integer,
  por_criterio  boolean not null default false   -- cambio la regla, no el dato
);
create index on cambio_estado (clave);
create index on cambio_estado (corrida_id);

-- ============================================================================
--  DERIVADO  (lo reescribe el motor en cada corrida)
-- ============================================================================

create table lote (
  lote            text primary key,
  normalizado     text not null,
  estado          estado_lote not null,
  origen_bloqueo  text,
  causas          criterio[] not null default '{}',
  causas_remuestreo criterio[] not null default '{}',
  motivo_lab      text,
  motivo_detencion text,
  motivo_liberacion text,
  por_criterio    jsonb,                    -- {LISTERIA: CONFORME, ...}
  evidencia       text,
  historia_remuestreo text,
  linea           text,
  destino_restringido text,
  liberacion_declarada date,
  mercados_liberados  text[],
  fuente_liberacion   text,
  en_stock        boolean not null default false,
  bodegas         text[],
  productos       text[],
  clientes        text[],
  cajas           integer not null default 0,
  kg              numeric  not null default 0,
  piezas          integer  not null default 0,
  batches_con_resultado integer not null default 0,
  batches_no_conformes  text,
  n_muestras      integer not null default 0,
  ultima_muestra  date,
  observaciones   text,
  corrida_id      bigint references corrida(id)
);
create index on lote (estado);
create index on lote (normalizado);

create table batch (
  batch           text primary key,
  normalizado     text not null,
  lote_base       text,                     -- lote de stock al que se agrega
  estado          estado_lote not null,
  causas          criterio[] not null default '{}',
  motivo_lab      text,
  motivo_detencion text,
  remuestreo      text,
  listeria        text,
  ram_max         numeric,
  nitrito         numeric,
  n_muestras      integer not null default 0,
  primera_muestra date,
  ultima_muestra  date,
  linea           text,
  tipo            text,
  presentacion    text,
  observacion_lab text,
  liberacion_declarada date,
  mercados_liberados   text[],
  corrida_id      bigint references corrida(id)
);
create index on batch (normalizado);
create index on batch (lote_base);

-- Muestras del LAB-REG-08 normalizadas. Es la evidencia; conviene tenerla
-- consultable y no solo resumida.
create table muestra (
  id              bigserial primary key,
  fuente          text not null,            -- hoja y archivo de origen
  codigo_lab      text,
  fecha           date,
  lote_sw         text,
  normalizado     text not null,
  tipo            text,
  grupo           text,
  presentacion    text,
  observacion     text,
  listeria_dato   boolean not null default false,
  listeria_presencia boolean not null default false,
  ram_max         numeric,
  nitrito_prom    numeric,
  linea           text,
  destino_restringido text,
  corrida_id      bigint references corrida(id)
);
create index on muestra (normalizado);
create index on muestra (fecha);

-- Stock agregado por lote y bodega. No se guarda caja por caja: son 77 mil
-- filas que solo se usan sumadas.
create table stock_lote (
  lote            text not null,
  normalizado     text not null,
  bodega          text not null,
  cajas           integer not null,
  kg              numeric not null,
  piezas          integer not null,
  corte           timestamptz,              -- hasta cuando llega ese archivo
  corrida_id      bigint references corrida(id),
  primary key (lote, bodega)
);
create index on stock_lote (normalizado);
