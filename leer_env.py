# -*- coding: utf-8 -*-
"""Lee el .env, para Python y para bloqueos.bat.

    import leer_env; leer_env.al_entorno()      desde Python
    python leer_env.py                          imprime ordenes SET para el .bat

Lo interpreta Python y no cmd porque "for /f" corta la linea en el primer #
aunque venga dentro de una clave, y la cadena de conexion llega truncada. Cuando
eso pasa, psycopg toma el usuario como host y el error -"failed to resolve host
motor_bloqueos.xxxx"- no se parece en nada a la causa.

Y lo usa tambien Python directamente porque si solo lo leyera el .bat, correr
"python cargar_supabase.py" a mano fallaria con "Falta BLOQUEOS_DB_URL" estando
la cadena ahi al lado, en el .env. Paso.

No devuelve valores vacios: si alguien deja FISHKEN_USER= sin completar porque ya
lo tiene como variable de usuario de Windows, el .env no debe pisarselo con nada.
"""
import os
import re

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
CLAVE = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", re.S)


def pares(ruta=RUTA):
    """(nombre, valor) de cada linea util del .env. Vacio si el archivo no esta."""
    if not os.path.exists(ruta):
        return
    for linea in open(ruta, encoding="utf-8-sig"):
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
            yield nombre, valor


def al_entorno(ruta=RUTA):
    """Mete el .env en os.environ. Pisa lo que ya haya, igual que hace el .bat."""
    for nombre, valor in pares(ruta):
        os.environ[nombre] = valor


if __name__ == "__main__":
    for _n, _v in pares():
        print(f'set "{_n}={_v}"')
