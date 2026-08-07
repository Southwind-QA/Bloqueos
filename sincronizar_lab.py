# -*- coding: utf-8 -*-
"""Trae los LAB-REG-08 y el PRO-REG-46 desde la carpeta del laboratorio.

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
    # Cada registro vive donde lo lleva quien lo escribe: el LAB-REG-08 en la
    # carpeta del laboratorio y el PRO-REG-46 en la de produccion, en el servidor.
    origenes = [(config.DIR_LAB, config.GLOB_LAB), (config.DIR_MP, config.GLOB_MP)]
    faltan = [d for d, _ in origenes if not os.path.isdir(d)]
    for d in faltan:
        print(f"  (no se llega a {d}: se usan las copias que ya estan en la carpeta)")
    origenes = [(d, p) for d, p in origenes if os.path.isdir(d)]
    if not origenes:
        return 0

    copiados, saltados = 0, 0
    for origen, patron in origenes:
        for src in sorted(glob.glob(os.path.join(origen, patron))):
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
    for origen, patron in origenes:
        nombres_origen = {os.path.basename(x)
                          for x in glob.glob(os.path.join(origen, patron))}
        for dst in sorted(glob.glob(config.ruta(patron))):
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
    print("               PRO-REG-46 desde", config.DIR_MP)
    sincronizar()
