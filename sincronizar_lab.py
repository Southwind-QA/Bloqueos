# -*- coding: utf-8 -*-
"""Trae los LAB-REG-08 desde la carpeta del laboratorio.

Se copian en vez de leerlos en su lugar por dos motivos: el laboratorio los
edita mientras nosotros corremos, y leer un archivo a medio guardar da un error
raro o, peor, datos incompletos. Con la copia, si el original esta ocupado se
sigue usando la anterior y se avisa.

Se preserva la fecha de modificacion del original: es lo que despues permite
distinguir "el laboratorio no ha cargado nada nuevo" de "nadie trajo el archivo".
"""
import glob
import os
import shutil
import sys

import config


def sincronizar():
    origen = config.DIR_LAB
    if not os.path.isdir(origen):
        print(f"  (no existe {origen}: se usan las copias que ya estan en la carpeta)")
        return 0

    copiados, saltados = 0, 0
    for src in sorted(glob.glob(os.path.join(origen, config.GLOB_LAB))):
        nombre = os.path.basename(src)
        if nombre.startswith("~$"):
            continue
        dst = config.ruta(nombre)
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src) - 1:
            saltados += 1
            continue
        try:
            shutil.copy2(src, dst)          # copy2 conserva la fecha del original
            print(f"  copiado: {nombre}")
            copiados += 1
        except (PermissionError, OSError) as e:
            print(f"  NO se pudo copiar {nombre}: {e}")
            if not os.path.exists(dst):
                sys.exit("  Y no hay copia previa que usar. Cierra el archivo en Excel "
                         "y vuelve a correr.")
            print("  Se sigue con la copia anterior, que puede estar desactualizada.")

    # Un original renombrado deja huerfana la copia vieja, y el cruce cargaria
    # las dos: mismo anio contado dos veces.
    nombres_origen = {os.path.basename(x) for x in glob.glob(os.path.join(origen, config.GLOB_LAB))}
    for dst in sorted(glob.glob(config.ruta(config.GLOB_LAB))):
        n = os.path.basename(dst)
        if n not in nombres_origen:
            print(f"  ATENCION: {n} ya no existe en la carpeta del laboratorio.")
            print("            Si es una copia vieja del mismo anio, el cruce contaria")
            print("            las muestras dos veces. Borrala si corresponde.")
    if saltados:
        print(f"  {saltados} archivo(s) ya estaban al dia")
    return copiados


if __name__ == "__main__":
    print("Sincronizando LAB-REG-08 desde", config.DIR_LAB)
    sincronizar()
