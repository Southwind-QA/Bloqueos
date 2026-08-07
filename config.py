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

# Binomio WPS / nitrito. Ninguno de los dos por si solo decide: lo que controla
# Listeria en el ahumado es la combinacion de sal en fase acuosa y nitrito.
#
#   WPS         nitrito < 85    85 <= nitrito <= 100    nitrito > 100
#   > 3,5       BLOQUEA         libera                  libera
#   3 a 3,5     BLOQUEA         BLOQUEA                 libera
#   < 3         BLOQUEA         BLOQUEA                 libera
#
# Se reduce a: libera si (nitrito >= 85 y WPS > 3,5) o nitrito > 100.
#
# Escrito asi, el caso sin WPS medido se resuelve solo y hacia el lado correcto:
# con nitrito bajo 100 no se puede acreditar que el WPS acompanie, asi que no
# libera. No se exime un criterio por falta de informacion.
LIM_NITRITO = 85           # ppm. Por debajo bloquea SIEMPRE, aunque el WPS sobre.
NIT_BINOMIO = 100          # ppm. Por encima libera sin importar el WPS.
WPS_MIN = 3.5              # % de sal en fase acuosa. Hay que superarlo, no igualarlo.

# Largo minimo para aceptar que dos codigos de lote son el mismo a distinto
# nivel de detalle. Por debajo de esto un prefijo calza con cualquier cosa:
# el laboratorio tiene registros cortos ('010', '107') que arruinan el match.
MIN_LOTE = 8

# ------------------------------------------------------------------ criterios
#
#   RAM       toda linea, sin excepciones.
#   NITRITO   binomio con el WPS (ver arriba). Solo linea refrigerada, MAS bacon
#             y wheel: salen congelados de planta pero se venden refrigerados
#             en destino.
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

# ------------------------------------------------------------------ motivos declarados
#
# El registro operativo (Bloqueo 2026.xlsm) anota el motivo del bloqueo en texto
# libre. Esta tabla traduce ese texto al criterio de laboratorio que puede
# levantarlo: un bloqueo por listeria se cierra con listeria posterior conforme,
# no con un nitrito conforme.
#
# Es lo mismo que la columna CRITERIOS DE LIBERACION del registro de detenciones,
# con una diferencia que hay que tener presente: alla lo declara una persona y
# aca se infiere del texto. Por eso la propuesta deja constancia de que el
# criterio fue inferido.
MOTIVOS_LAB = (
    (r"listeria|\bl\.?\s?m\.?\b|\blm\b", "LISTERIA"),
    (r"\bram\b|recuento|aerobio|mesofil", "RAM"),
    (r"nitrito", "NITRITO"),
)

# Un motivo que no calza con ninguna expresion de arriba NO es liberable contra
# el laboratorio: falta de documentacion, un reclamo de cliente o un desvio de
# proceso no se cierran con una muestra conforme. Quedan bloqueados hasta que
# Calidad firme la liberacion. La ausencia de evidencia no libera.

# ------------------------------------------------------------------ origenes
# Los LAB-REG-08 los edita el laboratorio en su carpeta de registros. Se copian
# desde ahi antes de cada corrida en vez de que alguien los traiga a mano: asi
# el cruce lee siempre una copia estable, y si el original esta a medio guardar
# la copia anterior sigue sirviendo.
DIR_LAB = os.environ.get(
    "BLOQUEOS_DIR_LAB",
    r"C:\Users\Usuario\Documents\doc_BRC\SSCA\REGISTROS\LABORATORIO\Registro En Linea")

# ------------------------------------------------------------------ archivos
ARCH_DETENCIONES = "REGISTRO DETENCIONES.xlsx"
ARCH_OPERATIVO = "Bloqueo 2026.xlsm"
ARCH_SALIDA = "BLOQUEOS - Cruce Stock vs LAB-REG-08.xlsx"
ARCH_HTML = "CONSULTA BLOQUEOS.html"
GLOB_LAB = "LAB-REG-08*.xlsx"

# PRO-REG-46: ingreso de materia prima por proveedor. Es lo unico que enlaza el
# lote del proveedor con el lote SW del producto elaborado, y por lo tanto lo
# unico que permite arrastrar el bloqueo de una materia prima a lo que se hizo
# con ella. Una hoja por proveedor.
GLOB_MP = "*PRO-REG-46*.xlsx"
DIR_HISTORIAL = "historial"


def ruta(*partes):
    return os.path.join(BASE, *partes)


# Huella de los criterios vigentes. Cambia cuando cambia una regla, y eso es lo
# que permite distinguir "cambio el resultado" de "cambiamos la norma".
def huella_criterios():
    return (f"listeria=refrigerada+congelada(EEUU|CostaRica); ram>{LIM_RAM}; "
            f"binomio wps/nitrito en refrigerada y en bacon/wheel: libera si "
            f"(nitrito>={LIM_NITRITO} y wps>{WPS_MIN}) o nitrito>{NIT_BINOMIO}; "
            "vigencia=ultimo resultado que cubre el criterio; "
            "registro operativo=bloquea por su motivo hasta liberacion declarada")
