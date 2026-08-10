# -*- coding: utf-8 -*-
"""Revisa la forma de BLOQUEOS_DB_URL sin mostrar la clave.

Existe porque el error de psycopg cuando la cadena llega truncada -"failed to
resolve host motor_bloqueos.xxxx"- no dice lo que realmente pasa: que falta el
@ y el host, y que por eso el usuario se esta usando como nombre de servidor.
"""
import os
import urllib.parse as up

u = os.environ.get("BLOQUEOS_DB_URL", "")
p = up.urlparse(u)
fallas = []

print(f"  Postgres ............ usuario {p.username or '(falta)'}")
print(f"                        host    {p.hostname or '(falta)'}"
      f"{':' + str(p.port) if p.port else ''}")
print(f"                        base    {p.path.lstrip('/') or '(falta)'}")
print(f"                        clave   {'presente' if p.password else 'FALTA'}")

if p.scheme not in ("postgresql", "postgres"):
    fallas.append("no empieza con postgresql://")
if p.hostname and p.username and p.hostname == p.username:
    fallas.append("el host es igual al usuario: falta el @ y el servidor, "
                  "la cadena quedo cortada")
elif p.hostname and "pooler" not in p.hostname and "supabase" in (p.hostname or ""):
    fallas.append("no parece el Session pooler; la conexion directa es solo IPv6")
if p.username and "." not in p.username:
    fallas.append("al usuario le falta el project ref pegado con un punto "
                  "(motor_bloqueos.<project-ref>)")
if p.username and p.username.startswith("postgres"):
    fallas.append("es el rol postgres, no motor_bloqueos: ese rol puede escribir "
                  "sobre decisiones y criterios, y esa proteccion se pierde")
if not p.password:
    fallas.append("no se lee la clave: revisa que no falte el : antes de ella")

for f in fallas:
    print(f"                        AVISO: {f}")
if not fallas:
    print("                        forma correcta")

# Conectar de verdad: la forma puede estar bien y la clave no. Vale mas descubrirlo
# ahora que despues de cinco minutos de cruce. Solo lee.
try:
    import psycopg
except ImportError:
    raise SystemExit(0)
try:
    with psycopg.connect(u, connect_timeout=10) as cx:
        with cx.cursor() as cur:
            cur.execute("select count(*) from bloqueos.lote")
            n = cur.fetchone()[0]
            cur.execute("select to_char(max(inicio), 'DD/MM/YYYY HH24:MI') "
                        "from bloqueos.corrida")
            f = cur.fetchone()[0]
    print(f"                        conecta: {n} lotes cargados, ultima corrida {f}")
except Exception as e:                                              # noqa: BLE001
    print(f"                        NO CONECTA: {str(e).splitlines()[0][:110]}")
