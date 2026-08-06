# -*- coding: utf-8 -*-
"""Sube el resultado del motor a Postgres.

    set BLOQUEOS_DB_URL=postgresql://motor_bloqueos:<clave>@<host>:5432/postgres
    python cargar_supabase.py

Escribe SOLO las tablas derivadas. Lo declarado -detenciones, decisiones,
criterios- no se toca: el rol motor_bloqueos ni siquiera tiene permiso, asi que
un error aqui no puede borrar una decision firmada. Si alguien corre esto con
una clave de servicio, el GRANT deja de protegerlo: no lo hagas.

La cadena de conexion sale de la variable de entorno. Nunca del codigo.
"""
import os
import sys

import pandas as pd

import config

try:
    import psycopg
    from psycopg import sql
except ImportError:
    sys.exit("Falta el driver. Instala:  python -m pip install \"psycopg[binary]\"")

URL = os.environ.get("BLOQUEOS_DB_URL")
if not URL:
    sys.exit("Falta BLOQUEOS_DB_URL. Es la cadena de conexion del rol motor_bloqueos,\n"
             "no la de postgres ni una clave de servicio.")
if "service_role" in URL or "sb_secret" in URL:
    sys.exit("Esa parece una credencial de servicio. El motor usa motor_bloqueos,\n"
             "que no puede escribir sobre lo declarado. Ver supabase/migrations/.")

SRC = config.ruta(config.ARCH_SALIDA)
HIST = config.ruta(config.DIR_HISTORIAL)


def txt(v):
    return None if pd.isna(v) else str(v).strip() or None


def num(v):
    return None if pd.isna(v) else float(v)


def ent(v):
    return 0 if pd.isna(v) else int(v)


def fecha(v):
    d = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(d) else d.date()


def lista(v):
    return [x for x in str(txt(v) or "").split(",") if x]


def sep(v, s=" / "):
    return [x.strip() for x in str(txt(v) or "").split(s) if x.strip()]


# ---------------------------------------------------------------- lectura
print("Leyendo", os.path.basename(SRC))
res = pd.read_excel(SRC, sheet_name="RESUMEN POR LOTE", header=3)
bats = pd.read_excel(SRC, sheet_name="VEREDICTO POR BATCH")
dlab = pd.read_excel(SRC, sheet_name="DETALLE LAB")
dstk = pd.read_excel(SRC, sheet_name="DETALLE STOCK")
fue = pd.read_excel(SRC, sheet_name="FUENTES")

# stock agregado: 77 mil cajas solo se usan sumadas
stk = (dstk.groupby(["LOTE DE PLANTA", "BODEGA"])
       .agg(cajas=("PIEZAS", "size"), kg=("PESO NETO (KG)", "sum"),
            piezas=("PIEZAS", "sum")).reset_index())

fuentes = {str(r["ARCHIVO"]): {"registros": ent(r["REGISTROS"]),
                               "hasta": str(r["HASTA"])[:19]} for _, r in fue.iterrows()}

cam = pd.DataFrame()
f_cam = os.path.join(HIST, "cambios.csv")
if os.path.exists(f_cam):
    cam = pd.read_csv(f_cam, dtype=str).fillna("")

# ---------------------------------------------------------------- carga
with psycopg.connect(URL, autocommit=False) as cx:
    with cx.cursor() as cur:
        cur.execute("set search_path = bloqueos, public")

        # La version de criterios es DECLARADA: la registra un administrador, no
        # el motor. Si el motor pudiera escribirla, una corrida podria cambiar la
        # norma contra la que se evalua.
        cur.execute("select id, huella from criterio_version where hasta is null "
                    "order by desde desc limit 1")
        fila = cur.fetchone()
        if not fila:
            sys.exit("No hay una version de criterios vigente en la base. "
                     "Registrala aplicando la migracion "
                     "20260806120400_bloqueos_criterio_inicial.sql")
        criterio_id, huella_db = fila
        if huella_db.strip() != config.huella_criterios().strip():
            print("  AVISO: los criterios de config.py no coinciden con los de la base.")
            print("         base   :", huella_db)
            print("         config :", config.huella_criterios())
            print("         Registra la version nueva antes de cargar, o los datos")
            print("         quedaran atribuidos a una norma que no es la que se aplico.")
            sys.exit(1)

        cur.execute("insert into corrida (criterio_ver, fuentes) values (%s, %s) "
                    "returning id", (criterio_id, psycopg.types.json.Jsonb(fuentes)))
        corrida = cur.fetchone()[0]
        print("  corrida", corrida)

        # Las derivadas se reemplazan enteras: el motor es la unica verdad sobre
        # ellas y un borrado parcial dejaria lotes fantasma de corridas viejas.
        for t in ("lote", "batch", "muestra", "stock_lote"):
            cur.execute(sql.SQL("delete from {}").format(sql.Identifier(t)))

        cur.executemany(
            """insert into lote (lote, normalizado, estado, origen_bloqueo, causas,
                 causas_remuestreo, motivo_lab, motivo_detencion, motivo_liberacion,
                 por_criterio, evidencia, historia_remuestreo, linea, destino_restringido,
                 liberacion_declarada, mercados_liberados, fuente_liberacion, en_stock,
                 bodegas, productos, clientes, cajas, kg, piezas,
                 batches_con_resultado, batches_no_conformes, n_muestras, ultima_muestra,
                 observaciones, corrida_id)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       %s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(txt(r["LOTE"]), txt(r["LOTE (normalizado)"]), txt(r["ESTADO"]),
              txt(r["ORIGEN DEL BLOQUEO"]), lista(r["CAUSAS LAB"]),
              lista(r["CAUSAS CON REMUESTREO CONFORME"]), txt(r["MOTIVO - LABORATORIO"]),
              txt(r["MOTIVO - DETENCION"]), txt(r["MOTIVO DE LA LIBERACION"]),
              psycopg.types.json.Jsonb(dict(
                  p.split("=") for p in str(txt(r["ESTADO POR CRITERIO"]) or "").split("; ") if "=" in p)),
              txt(r["EVIDENCIA (ultimas muestras)"]), txt(r["HISTORIA DEL RE-MUESTREO"]),
              txt(r["LINEA"]), txt(r["DESTINO RESTRINGIDO"]),
              fecha(r["LIBERACION DECLARADA"]), sep(r["MERCADOS LIBERADOS"], "/"),
              txt(r["FUENTE DE LA LIBERACION"]), txt(r["EN STOCK"]) == "SI",
              sep(r["BODEGA(S)"]), sep(r["PRODUCTOS"]), sep(r["CLIENTE(S)"]),
              ent(r["CAJAS EN STOCK"]), 0, 0,
              ent(r["BATCHES CON RESULTADO"]), txt(r["BATCHES NO CONFORMES"]),
              ent(r["N MUESTRAS LAB"]), fecha(r["ULTIMA MUESTRA LAB"]),
              txt(r["OBSERVACIONES"]), corrida) for _, r in res.iterrows()])
        print("  lote:", len(res))

        cur.executemany(
            """insert into batch (batch, normalizado, lote_base, estado, causas,
                 motivo_lab, motivo_detencion, remuestreo, listeria, ram_max, nitrito,
                 n_muestras, primera_muestra, ultima_muestra, linea, tipo, presentacion,
                 observacion_lab, liberacion_declarada, mercados_liberados, corrida_id)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(txt(r["BATCH"]), txt(r["BATCH (normalizado)"]), txt(r["LOTE BASE EN STOCK"]),
              txt(r["ESTADO"]), lista(r["CAUSAS LAB"]), txt(r["MOTIVO - LABORATORIO"]),
              txt(r["MOTIVO - DETENCION"]), txt(r["RE-MUESTREO CONFORME"]),
              txt(r["LISTERIA"]), num(r["RAM MAX (UFC/g)"]), num(r["NITRITO PROMEDIO (ppm)"]),
              ent(r["N MUESTRAS"]), fecha(r["PRIMERA MUESTRA"]), fecha(r["ULTIMA MUESTRA"]),
              txt(r["LINEA"]), txt(r["TIPO"]), txt(r["PRESENTACION"]),
              txt(r["OBSERVACION LAB"]), fecha(r["LIBERACION DECLARADA"]),
              sep(r["MERCADOS LIBERADOS"], "/"), corrida) for _, r in bats.iterrows()])
        print("  batch:", len(bats))

        cur.executemany(
            """insert into muestra (fuente, codigo_lab, fecha, lote_sw, normalizado, tipo,
                 grupo, presentacion, observacion, listeria_dato, listeria_presencia,
                 ram_max, nitrito_prom, corrida_id)
               values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [(txt(r["FUENTE LAB"]), txt(r["CÓDIGO LAB"]), fecha(r["FECHA INGRESO"]),
              txt(r["LOTE SW"]), txt(r["LOTE (normalizado)"]), txt(r["TIPO "]),
              txt(r["GRUPO"]), txt(r["PRESENTACIÓN"]), txt(r["OBSERVACIÓN"]),
              any(pd.notna(r[c]) for c in ("LM1", "LM2", "LM3", "LM4", "LM5")),
              any(str(r[c]).strip().upper() == "P" for c in ("LM1", "LM2", "LM3", "LM4", "LM5")),
              num(r[["RAM1", "RAM2", "RAM3", "RAM4", "RAM5"]].apply(
                  pd.to_numeric, errors="coerce").max()),
              num(r["NITRITO PROMEDIO"]), corrida) for _, r in dlab.iterrows()])
        print("  muestra:", len(dlab))

        cur.executemany(
            """insert into stock_lote (lote, normalizado, bodega, cajas, kg, piezas,
                 corrida_id) values (%s,%s,%s,%s,%s,%s,%s)""",
            [(txt(r["LOTE DE PLANTA"]), txt(r["LOTE DE PLANTA"]), txt(r["BODEGA"]),
              ent(r["cajas"]), num(r["kg"]) or 0, ent(r["piezas"]), corrida)
             for _, r in stk.iterrows()])
        print("  stock_lote:", len(stk))

        # El historial solo agrega lo que aun no esta: cambios.csv se reescribe
        # entero en cada corrida y reinsertarlo duplicaria.
        if len(cam):
            cur.execute("select count(*) from cambio_estado")
            ya = cur.fetchone()[0]
            nuevos = cam.iloc[::-1].iloc[ya:] if ya < len(cam) else cam.iloc[0:0]
            if len(nuevos):
                cur.executemany(
                    """insert into cambio_estado (corrida_id, nivel, clave, estado_ant,
                         estado_nuevo, causas, cajas, por_criterio)
                       values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [(corrida, r["NIVEL"], r["CLAVE"], r["ESTADO ANTERIOR"] or None,
                      r["ESTADO NUEVO"], r["CAUSAS"] or None,
                      int(r["CAJAS"] or 0),
                      str(r.get("HUBO CAMBIO DE CRITERIO", "")).upper() == "SI")
                     for _, r in nuevos.iterrows()])
            print(f"  cambio_estado: +{len(nuevos)} (ya habia {ya})")

        cur.execute("update corrida set fin = now(), resultado = %s where id = %s",
                    ("ok", corrida))
    cx.commit()

print("\nListo. Todo en una transaccion: o entro completo o no entro nada.")
