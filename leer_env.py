# -*- coding: utf-8 -*-
"""Traduce .env a ordenes SET para bloqueos.bat.

Lo hace Python y no cmd porque "for /f" corta la linea en el primer # aunque
venga dentro de una clave, y la cadena de conexion llega truncada. Cuando eso
pasa, psycopg toma el usuario como host y el error -"failed to resolve host
motor_bloqueos.xxxx"- no se parece en nada a la causa.

No imprime valores vacios: si alguien deja FISHKEN_USER= sin completar porque ya
lo tiene como variable de usuario de Windows, el .env no debe pisarselo con nada.
"""
import os
import re
import sys

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
CLAVE = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", re.S)

if not os.path.exists(RUTA):
    sys.exit(0)

for linea in open(RUTA, encoding="utf-8-sig"):
    linea = linea.rstrip("\r\n")
    if not linea.strip() or linea.lstrip().startswith("#"):
        continue
    m = CLAVE.match(linea)
    if not m:
        continue
    nombre, valor = m.group(1), m.group(2).strip()
    # Las comillas hacen falta en PowerShell pero aqui quedarian dentro del valor
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
        valor = valor[1:-1]
    if valor:
        print(f'set "{nombre}={valor}"')
