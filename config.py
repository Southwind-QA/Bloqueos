# -*- coding: utf-8 -*-
"""Configuracion del control de bloqueos.

Dos motivos para que esto no viva dentro de los scripts:

1. La carpeta. Hoy todo corre en el PC de un usuario; cuando corra en un
   servidor la ruta cambia. Se toma de la variable de entorno BLOQUEOS_DIR y,
   si no existe, de la carpeta donde esta este archivo.

2. Los criterios. Los limites y las expresiones que identifican cliente,
   linea y destino son decisiones de Calidad, no detalles de implementacion.
   Tenerlos juntos y comentados permite revisarlos sin leer el motor, y que
   un cambio de norma sea visible en el diff.
"""
import os

# ------------------------------------------------------------------ ubicacion
BASE = os.environ.get("BLOQUEOS_DIR") or os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------ limites
LIM_RAM = 100_000          # UFC/g. Se supera -> bloquea. Aplica a toda linea.
LIM_NITRITO = 85           # ppm. Por debajo -> bloquea. Solo donde aplica (ver abajo).

# Largo minimo para aceptar que dos codigos de lote son el mismo a distinto
# nivel de detalle. Por debajo de esto un prefijo calza con cualquier cosa:
# el laboratorio tiene registros cortos ('010', '107') que arruinan el match.
MIN_LOTE = 8

# ------------------------------------------------------------------ criterios
#
#   RAM       toda linea, sin excepciones.
#   NITRITO   solo linea refrigerada, MAS bacon y wheel: salen congelados de
#             planta pero se venden refrigerados en destino.
#   LISTERIA  linea refrigerada siempre; linea congelada solo si el destino es
#             EE.UU. o Costa Rica. Si el destino no se puede determinar, se
#             aplica igual: no se exime un criterio por falta de informacion.
#
# Un criterio deja de estar vigente unicamente si hay muestras POSTERIORES que
# vuelven a medir ESE criterio y salen conformes. Una muestra posterior que no
# midio lo que fallo no es evidencia de nada.

# Clientes de destino EE.UU. Se detectan por razon social.
US_CLI = r"\bLLC\b|\bINC\b|ECHO FALLS|SLADE GORTON|OCEAN SKY|GLOBAL STAR"

# Costa Rica: el cliente lleva PMT en el nombre.
CR_CLI = r"\bPMT"

# Producto de destino EE.UU. por su nombre o presentacion. Cubre 106 de los 111
# lotes; los 5 restantes solo se detectan por cliente.
US_PROD = (r"\bwheel\b|\bbacon\b|cold smoked|smoked atlantic|\bsliced\b"
           r"|\bskinless\b|pin bone|farm raised|\bsides\b|echo falls")

# Bacon y wheel, para el bypass del nitrito.
BACON_WHEEL = r"\bbacon\b|\bwheel\b"

# Texto que clasifica la linea de proceso.
TXT_REFRIGERADA = "refrigerad"
TXT_CONGELADA = ("carpaccio", "congelad")

# ------------------------------------------------------------------ archivos
ARCH_DETENCIONES = "REGISTRO DETENCIONES.xlsx"
ARCH_OPERATIVO = "Bloqueo 2026.xlsm"
ARCH_SALIDA = "BLOQUEOS - Cruce Stock vs LAB-REG-08.xlsx"
ARCH_HTML = "CONSULTA BLOQUEOS.html"
GLOB_LAB = "LAB-REG-08*.xlsx"
DIR_HISTORIAL = "historial"


def ruta(*partes):
    return os.path.join(BASE, *partes)


# Huella de los criterios vigentes. Cambia cuando cambia una regla, y eso es lo
# que permite distinguir "cambio el resultado" de "cambiamos la norma".
def huella_criterios():
    return (f"listeria=refrigerada+congelada(EEUU|CostaRica); ram>{LIM_RAM}; "
            f"nitrito<{LIM_NITRITO} en refrigerada y en bacon/wheel; "
            "vigencia=ultimo resultado que cubre el criterio")
