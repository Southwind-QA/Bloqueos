# -*- coding: utf-8 -*-
"""Actualiza todo el tablero de bloqueos en un solo paso.

    python actualizar.py

1. Cruza el stock de todas las bodegas contra el LAB-REG-08 de cada anio y el
   registro de detenciones  ->  BLOQUEOS - Cruce Stock vs LAB-REG-08.xlsx
2. Regenera la pagina de consulta                ->  CONSULTA BLOQUEOS.html

Basta con dejar los xlsx nuevos en esta carpeta: los archivos de stock se detectan
por su cabecera y los de laboratorio por el nombre (LAB-REG-08*.xlsx).
REGISTRO DETENCIONES.xlsx se lee, nunca se sobrescribe.
"""
import io
import os
import runpy
import sys
import time
import traceback

import config

AQUI = os.path.dirname(os.path.abspath(__file__))
PASOS = [("Cruzando stock, laboratorio y detenciones", "cruce2.py"),
         ("Generando la pagina de consulta", "gen_html.py")]

# La consola de Windows suele venir en cp1252 y los nombres de archivo traen
# acentos: sin esto el print revienta con UnicodeEncodeError a mitad de camino.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    os.chdir(AQUI)
    t0 = time.time()
    for i, (rotulo, script) in enumerate(PASOS, 1):
        ruta = os.path.join(AQUI, script)
        if not os.path.exists(ruta):
            print(f"\n  FALTA {script} en {AQUI}")
            return 1
        print(f"\n[{i}/{len(PASOS)}] {rotulo}...", flush=True)
        t = time.time()
        try:
            runpy.run_path(ruta, run_name="__main__")
        except SystemExit as e:
            if e.code:
                print(f"\n  {script} se detuvo: {e.code}")
                return int(e.code) if isinstance(e.code, int) else 1
        except PermissionError as e:
            print(f"\n  No se pudo escribir: {e.filename}")
            print("  Cierra ese archivo en Excel y vuelve a correr.")
            return 1
        except Exception:
            print(f"\n  Error en {script}:\n")
            traceback.print_exc()
            return 1
        print(f"      listo en {time.time() - t:0.0f} s", flush=True)
    print(f"\nTodo actualizado en {time.time() - t0:0.0f} s.")
    print(f"Abre {config.ARCH_HTML} con doble clic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
