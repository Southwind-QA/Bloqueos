-- ============================================================================
--  El registro operativo es un tercer origen de bloqueo
--
--  Bloqueo 2026.xlsm tiene la misma naturaleza que la detencion por correo: lo
--  escribe una persona, no se recalcula, y solo lo cierra una liberacion
--  explicita o un resultado de laboratorio posterior que cubra SU motivo.
--
--  En esa hoja la columna Estado se escribe UNICAMENTE al liberar, asi que una
--  fila sin estado es un bloqueo vigente. Hasta ahora esas 2.591 filas quedaban
--  fuera del cruce por no saber que significaban: 18.221 cajas figuraban
--  liberadas, 11.551 de ellas declaradas por presencia de listeria.
--
--  operativo_bloquea separa "hay un bloqueo declarado abierto" de "hay uno con
--  re-muestreo conforme posterior, esperando firma". Existe porque la consulta
--  de packing list resuelve contra el laboratorio, que no sabe nada de este
--  origen: sin esta marca, un lote bloqueado por correo con laboratorio
--  conforme saldria LIBERADO justo en la pregunta que mas se hace.
-- ============================================================================
set search_path = bloqueos, public;

alter table lote add column if not exists motivo_operativo  text;
alter table lote add column if not exists operativo_bloquea boolean not null default false;

create index if not exists lote_operativo_bloquea_idx on lote (operativo_bloquea)
  where operativo_bloquea;
