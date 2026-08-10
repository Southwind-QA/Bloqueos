-- ============================================================================
--  Las detenciones se mudan del xlsx a Postgres
--
--  Hasta ahora vivian en REGISTRO DETENCIONES.xlsx y nadie las habia subido: la
--  tabla estaba vacia, por eso el sitio no mostraba ninguna. Desde el 10/08/2026
--  el sitio las registra directamente aqui y el xlsx queda como historico.
--
--  Va como migracion y no en el cargador a proposito: el rol motor_bloqueos no
--  puede escribir detenciones, y esa es la proteccion que impide que una corrida
--  mala toque lo que declararon las personas. Cargarlas es un acto del
--  administrador, una sola vez.
--
--  on conflict do nothing: si se corre dos veces no duplica ni pisa lo que ya
--  haya editado alguien desde el sitio.
-- ============================================================================
set search_path = bloqueos, public;

insert into detencion (id, fecha_correo, emitido_por, referencia, tipo, descripcion,
                       lote, producto, alcance, cantidad_kg, fecha_evento, resolucion,
                       criterios, estado, observacion, origen)
values
  ('DET-2026-001', '2026-08-04', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '@2VQ26192151', 'Bacon Cut (Inyectado)', 'LOTE+PRODUCTO', null, '2026-08-04', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 27/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-002', '2026-08-04', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '@2VQ26192151', 'Bacon Cut (Sin Inyectar)', 'LOTE+PRODUCTO', null, '2026-08-04', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 27/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-003', '2026-08-04', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '@2VQ26192151', 'Molde Tradicional', 'LOTE+PRODUCTO', null, '2026-08-04', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 27/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-004', '2026-07-30', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '@2VQ2618210', 'Filete Wheel (Salado Seco)', 'LOTE+PRODUCTO', null, '2026-07-30', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 22/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-005', '2026-07-30', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '@2VQ2618211', 'Filete Wheel (Salado Seco)', 'LOTE+PRODUCTO', null, '2026-07-30', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 22/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-006', '2026-07-30', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Vida util excedida', 'Lote procesado en sala 10 con 8 dias de vida util transcurridos a la fecha de proceso.', '2SA26062102', 'Molde Trucha', 'LOTE+PRODUCTO', null, '2026-07-30', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM}', 'ABIERTA', 'Fecha de elaboracion del lote: 22/07/2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-007', '2026-07-09', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Curado excedido', 'Producto sobrepaso los 4 dias de curado.', '2AS2621170M', 'Filete ahumado caliente linea refrigerada (salado seco)', 'LOTE+PRODUCTO', null, '2026-06-28', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM,NITRITO}', 'ABIERTA', 'Inicio curado 23/06 - inicio secado 28/06 - 5 dias. OJO: el correo escribe el anio como ''25'', se asume 2026. Fecha del evento = fin del curado (28/06/2026).', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-008', '2026-07-09', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Curado excedido', 'Producto sobrepaso los 4 dias de curado.', 'B2AS2621170M', 'Filete ahumado caliente linea refrigerada (salado seco)', 'LOTE+PRODUCTO', null, '2026-06-28', 'Detencion hasta liberacion de laboratorio', '{LISTERIA,RAM,NITRITO}', 'ABIERTA', 'Inicio curado 22/06 - inicio secado 28/06 - 6 dias. Lote DISTINTO de 2AS2621170M (prefijo B). OJO: el correo escribe el anio como ''25'', se asume 2026.', 'REGISTRO DETENCIONES.xlsx (historico)'),
  ('DET-2026-009', '2026-06-26', 'Macarena Lira (Supervisor de Calidad)', 'Detencion - supervisorcalidad@southwind.cl', 'Contaminacion fisica', 'Caida al piso en sala 10 durante el pesaje.', '2GT26021751', 'Filete fresco para molde', 'PARCIAL (KG)', 145.64, '2026-06-26', 'PNC - no se libera contra laboratorio', '{}', 'PNC', 'PNC declarado en el correo. ALCANCE PARCIAL: 145,64 kg de un lote mayor; sin identificacion de pallet/caja el cruce marca el lote completo. Requiere precisar cajas afectadas.', 'REGISTRO DETENCIONES.xlsx (historico)')
on conflict (id) do nothing;
