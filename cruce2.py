# -*- coding: utf-8 -*-
"""Cruce de bloqueos: stock de todas las bodegas x LAB-REG-08 x registro de detenciones.

Dos origenes de bloqueo con naturaleza distinta:
  - LAB        : derivado. Se recalcula entero en cada corrida.
  - DETENCION  : declarado por correo. Entrada durable, el script solo la lee.
Se acumulan: un lote con ambos necesita cerrar los dos.
"""
import datetime
import json
import os
import re
import glob
import pandas as pd
import numpy as np
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import config

BASE = config.BASE
LABS = sorted(glob.glob(config.ruta(config.GLOB_LAB)))
F_DET = config.ruta(config.ARCH_DETENCIONES)
OUT = config.ruta(config.ARCH_SALIDA)

LIM_RAM = config.LIM_RAM
LIM_NITRITO = config.LIM_NITRITO
NIT_BINOMIO = config.NIT_BINOMIO
WPS_MIN = config.WPS_MIN
MIN_LOTE = config.MIN_LOTE

LM = ["LM1", "LM2", "LM3", "LM4", "LM5"]
RAM = ["RAM1", "RAM2", "RAM3", "RAM4", "RAM5"]
NIT = ["NITRITO", "NITRITO.1", "NITRITO.2"]
WPS = ["WPS1", "WPS2", "WPS3"]


def norm(s):
    """Lote comparable. Conserva @ y B: son parte del codigo, no ruido.
    2AS2621170M y B2AS2621170M son lotes DISTINTOS (correo de detencion 09/07/2026).
    Solo se corta el sufijo *SEMANA y se limpian separadores."""
    return re.sub(r"[^A-Z0-9@]", "", str(s).strip().upper().split("*")[0])


def norm_u(s):
    """Unidad de laboratorio: el lote CON su sufijo de semana y turno.

    El sufijo *NNL NO es ruido, aunque durante mucho tiempo se trato como tal.
    Distingue dias de produccion y cada uno lleva su propio LOTE JULIANO:
    @2CK26621761E*28V, *29L y *29W son el 10, el 13 y el 15 de julio, y solo el
    ultimo salio con nitrito bajo. Fusionarlos bloquea dos dias conformes.

    Contra el stock hay que seguir agregando, porque Fishken no registra el
    sufijo; pero cuando el packing list trae el codigo completo, hay con que
    responder exacto y no hay razon para perder esa precision.
    """
    return re.sub(r"[^A-Z0-9@*]", "", str(s).strip().upper())


def laxo(s):
    """Version tolerante, solo para detectar posibles errores de tipeo en @ / B."""
    return norm(s).lstrip("@").lstrip("B")


def emparenta(a, b):
    """True si a y b son el mismo lote a distinto nivel de detalle (lote vs sublote)."""
    if len(a) < MIN_LOTE or len(b) < MIN_LOTE:
        return a == b
    return a.startswith(b) or b.startswith(a)


# Si un codigo base tiene forma de lote: el largo minimo, o la forma explicita de
# los lotes de recorte y despunte mensual (SW26098, 7 caracteres). Ver
# config.LOTE_CORTO. Un lote corto solo se empareja por igualdad (emparenta).
es_lote = config.es_lote


# ----------------------------------------------------------------- STOCK (N bodegas)
marcos = []
for f in sorted(glob.glob(os.path.join(BASE, "*.xlsx"))):
    n = os.path.basename(f)
    if (n.startswith("~$") or n.startswith("LAB-REG-08") or "PRO-REG-46" in n
            or f in (F_DET, OUT)):
        continue
    try:
        cab = pd.read_excel(f, header=None, nrows=2)
        if "LOTE DE PLANTA" not in cab.iloc[1].astype(str).values:
            print("  (omitido, no parece stock):", n)
            continue
        d = pd.read_excel(f, header=1).dropna(how="all")
    except Exception as e:                                    # noqa: BLE001
        print("  (omitido, no se pudo leer):", n, e)
        continue
    titulo = str(cab.iloc[0, 0])
    d["BODEGA"] = titulo.split("-")[-1].strip() if "-" in titulo else titulo.strip()
    d["ARCHIVO ORIGEN"] = n
    marcos.append(d)
    print(f"  stock: {n}  ->  {len(d)} cajas  |  bodega: {d['BODEGA'].iloc[0]}")

if not marcos:
    raise SystemExit("No se encontro ningun archivo de stock.")
stock = pd.concat(marcos, ignore_index=True)
stock = stock[stock["LOTE DE PLANTA"].notna()].copy()
stock["_L"] = stock["LOTE DE PLANTA"].map(norm)

# ----------------------------------------------------------------- LAB (N anios)
# Los archivos por anio no son identicos: 2025 escribe "Nitrito" y no trae la columna
# "A/R Nitrito"; 2026 escribe "NITRITO" y si la trae. Se ubica cada bloque por nombre,
# no por posicion.
INFO = ["CÓDIGO LAB", "FECHA INGRESO", "TIPO ", "GRUPO", "PRESENTACIÓN", "LOTE SW", "OBSERVACIÓN"]


_HOJAS_VISTAS = {}


# Las muestras de materia prima traen LOTE ORIGEN y dejan LOTE SW vacio, asi que
# el filtro de carga las descarta. Se apartan aqui para cruzarlas por el PRO-REG-46.
_MP_CRUDAS = []


def carga_lab(f):
    n = os.path.basename(f)
    xls = pd.ExcelFile(f)
    hojas = [h for h in xls.sheet_names if h.strip().upper().startswith("RESULTADOS MICRO")]
    if not hojas:
        print("  (lab omitido, sin hoja RESULTADOS MICRO):", n)
        return None
    # Dos archivos con la misma hoja son el mismo anio: cargarlos ambos duplica
    # cada muestra. Pasa apenas queda una copia vieja con otro nombre.
    if hojas[0] in _HOJAS_VISTAS:
        print(f"  (lab OMITIDO por duplicar {hojas[0]}): {n}")
        print(f"      ya se cargo desde {_HOJAS_VISTAS[hojas[0]]}. Borra el que sobre.")
        return None
    _HOJAS_VISTAS[hojas[0]] = n
    d = pd.read_excel(f, sheet_name=hojas[0], header=2).dropna(how="all")
    _MP_CRUDAS.append(d[d["TIPO "].astype(str).str.strip().str.upper().str.startswith("MP")
                        & d["LOTE ORIGEN"].notna()].assign(_FUENTE=hojas[0]))
    d = d[d["LOTE SW"].notna()].copy()
    # Las filas TIPO=PRUEBAS son ensayos del laboratorio, no producto que se
    # despache: no deben bloquear ni liberar nada. Se descarta lo que dice
    # PRUEBAS en vez de exigir que diga PT, para que una fila con el tipo en
    # blanco o con un valor nuevo no desaparezca del cruce sin que nadie lo note.
    _pr = d["TIPO "].astype(str).str.strip().str.upper().eq("PRUEBAS")
    if _pr.any():
        print(f"      ({int(_pr.sum())} filas TIPO=PRUEBAS omitidas: son ensayos, "
              "no producto despachable)")
        d = d[~_pr].copy()
    cols = list(d.columns)

    # El bloque fisicoquimico va %SAL, %H, WPS, NITRITO, cada uno con sus
    # replicas y su Promedio inmediatamente despues. Por eso el promedio de cada
    # magnitud es la primera columna PROMEDIO que aparece tras su ultima replica.
    def bloque(nombre):
        ix = [i for i, c in enumerate(cols)
              if re.fullmatch(rf"{nombre}(\d|\.\d+)?", str(c).strip().upper())]
        if not ix:
            return [], None
        p = next((c for i, c in enumerate(cols)
                  if str(c).strip().upper().startswith("PROMEDIO") and i > max(ix)), None)
        return [cols[i] for i in ix], p

    nit, prom = bloque("NITRITO")
    wps, promw = bloque("WPS")
    ar = next((c for c in cols if "A/R" in str(c).upper()), None)

    out = pd.DataFrame(index=d.index)
    for c in INFO:
        out[c] = d[c] if c in d.columns else None
    for i, c in enumerate(LM):
        out[c] = d[c] if c in d.columns else None
    for c in RAM:
        out[c] = d[c] if c in d.columns else None
    for i, c in enumerate(NIT):
        out[c] = d[nit[i]] if i < len(nit) else None
    out["NITRITO PROMEDIO"] = d[prom] if prom else None
    for i, c in enumerate(WPS):
        out[c] = d[wps[i]] if i < len(wps) else None
    out["WPS PROMEDIO"] = d[promw] if promw else None
    out["A/R Nitrito"] = d[ar] if ar else ""
    out["FUENTE LAB"] = hojas[0]
    out["_ARCHIVO"] = n
    out["_GUARDADO"] = pd.Timestamp(datetime.datetime.fromtimestamp(os.path.getmtime(f)))
    print(f"  lab: {n}  ->  {len(out)} muestras con lote  |  hoja: {hojas[0]}"
          + ("" if ar else "  (sin columna A/R Nitrito)"))
    return out


LABS = sorted(LABS, key=os.path.getmtime, reverse=True)
marcos_lab = [x for x in (carga_lab(f) for f in LABS) if x is not None]
if not marcos_lab:
    raise SystemExit("No se encontro ningun LAB-REG-08 legible.")
lab = pd.concat(marcos_lab, ignore_index=True)

lab["_L"] = lab["LOTE SW"].map(norm)
lab["_U"] = lab["LOTE SW"].map(norm_u)
lab["_FECHA"] = pd.to_datetime(lab["FECHA INGRESO"], errors="coerce")
_lm = lab[LM].astype(str).apply(lambda c: c.str.strip().str.upper())
lab["_LM_P"] = (_lm == "P").any(axis=1)
lab["_LM_DATO"] = lab[LM].notna().any(axis=1)

def ram_promedio(d):
    """RAM de cada muestra: el promedio de sus replicas, como lo exige el SSCA.

    Replica exactamente lo que hace el dashboard de inocuidad
    (southwind_inocuidad/parsers/reg08.py, RAM_mean): RAM1-RAM5 leidas como
    numero, lo que no es numero -vacio, "<10", "incontable"- queda fuera, promedio
    de lo que queda y redondeo a entero. Sin replicas numericas, NaN: sin dato.
    Dos sistemas que leen la misma fila no pueden dar veredictos distintos.

    Una replica sobre el techo del metodo no entra al promedio, pero tampoco se
    pierde: la marca ram_techo() y hace no conforme a la muestra.
    """
    return d[RAM].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True).round(0)


RX_RAM_TECHO = re.compile(config.RAM_TECHO, re.I)


def _texto_ram(d):
    """Las replicas de RAM escritas como texto, sin los numeros ni los vacios."""
    v = d[RAM].astype(str).apply(lambda c: c.str.strip())
    num = d[RAM].apply(pd.to_numeric, errors="coerce")
    return v, d[RAM].notna() & num.isna() & ~v.isin(["", "nan", "NaN", "None"])


def ram_techo(d):
    """True si alguna replica dice que el conteo paso el techo del metodo.

    "incontable", ">N", TNTC, INC, MNPC: la placa no se pudo contar porque habia
    demasiado. Decision de Calidad del 30/09/2026: eso hace NO CONFORME a la
    muestra sea cual sea el promedio. Dejarla fuera del promedio -que es lo que
    hace el calculo del dashboard- absolvia la placa con que las otras dos
    replicas salieran bajas. "<10" es lo contrario, bajo el limite de deteccion,
    y sigue fuera del promedio.
    """
    v, txt = _texto_ram(d)
    return (txt & v.apply(lambda c: c.str.contains(RX_RAM_TECHO))).any(axis=1)


def ram_no_numericas(d):
    """Replicas de RAM escritas como texto que no son ni "<N" ni un techo. Quedan
    fuera del promedio, y como no se sabe que dicen no se dejan pasar en silencio."""
    v, txt = _texto_ram(d)
    raro = txt & ~v.apply(lambda c: c.str.match(r"^<\s*\d") | c.str.contains(RX_RAM_TECHO))
    return int(raro.sum().sum()), sorted({str(x) for x in v.where(raro).stack().dropna()})[:5]


lab["_RAM"] = ram_promedio(lab)
lab["_RAM_TECHO"] = ram_techo(lab)
if lab["_RAM_TECHO"].any():
    print(f"  RAM: {int(lab['_RAM_TECHO'].sum())} muestra(s) con una replica sobre el techo "
          "del metodo (incontable): no conformes aunque el promedio cumpla")
_rn, _rx = ram_no_numericas(lab)
if _rn:
    print(f"  ATENCION RAM: {_rn} replica(s) escritas como texto que no se reconocen "
          f"({', '.join(_rx)}): quedan fuera del promedio. Revisar esas muestras a mano")
_n = lab[NIT].apply(pd.to_numeric, errors="coerce")
lab["_NIT"] = pd.to_numeric(lab["NITRITO PROMEDIO"], errors="coerce").fillna(_n.mean(axis=1))
lab["_NIT_MIN"] = _n.min(axis=1)
_w = lab[WPS].apply(pd.to_numeric, errors="coerce")
lab["_WPS"] = pd.to_numeric(lab["WPS PROMEDIO"], errors="coerce").fillna(_w.mean(axis=1))
lab["_AR"] = lab["A/R Nitrito"].astype(str).str.strip().str.upper().replace("NAN", "")

# ----------------------------------------------------------------- MATERIAS PRIMAS
# Si una materia prima esta bloqueada, lo que se elaboro con ella tambien lo esta.
# El laboratorio registra la MP por LOTE ORIGEN + PROVEEDOR y deja el LOTE SW
# vacio, asi que esas muestras no entran por el camino normal; el PRO-REG-46 es lo
# unico que las enlaza con el producto que salio de ellas.
#
# A la materia prima solo le aplican listeria y RAM: no trae nitrito ni WPS (0 de
# 509 muestras), asi que el binomio no tiene nada que evaluar ahi.
MIN_PROV = 6            # los lotes de proveedor son mas cortos que los de planta


def npro(s):
    """Lote de proveedor comparable.

    Es otra convencion que la del lote SW y hay que respetarla: aqui el sufijo
    tras el guion identifica el pallet (@4M1262004-VQ009F), no el batch.
    """
    return re.sub(r"[^0-9A-Z]", "", str(s).strip().upper().split("-")[0])


def lotes_prov(s):
    """Una celda puede traer varios lotes: '26020006 / 26020007'."""
    return [x for x in (npro(p) for p in re.split(r"[/,;]", str(s))) if len(x) >= MIN_PROV]


def laxo_prov(s):
    """En el lote de proveedor, a diferencia del lote SW, el prefijo de
    certificacion y la confusion O/0 SI son ruido de transcripcion."""
    return s.lstrip("@B").replace("O", "0").replace("I", "1")


# ---- PRO-REG-46: una hoja por proveedor, lote de proveedor -> lote SW
MP_DE_SW, PROV_46, _f46, _anios46 = {}, {}, [], {}
# Lo que aporta CADA archivo, para que la hoja FUENTES no declare el total en
# cada fila: cuatro veces el mismo numero se lee como cuatro veces la cobertura,
# que es justo el error que esa hoja existe para evitar.
_ap46 = {}
# La fecha de recepcion viene con acento y el acento cambia entre archivos, asi
# que la columna se busca por su forma, no por su nombre exacto.
_RX_REC46 = re.compile(r"fecha\s+de\s+recepci", re.I)


def pro46_por_anio(archivos):
    """Un PRO-REG-46 por anio: si hay dos, el modificado mas recientemente.

    Un anio cargado dos veces cuenta cada ingreso dos veces (paso con el
    LAB-REG-08 y se detecto tarde), asi que se carga uno solo. Pero cual no lo
    puede decidir el orden alfabetico: una copia local "2026. (PRO-REG-46) ESTE
    ESTA ACTUALIZADO.xlsx" del 01/09 ordenaba antes que la del servidor del 22/09
    y se quedaba con el anio, y la materia prima que entro despues no arrastraba
    su bloqueo a ningun producto. El que se edito ultimo es el vigente.

    Devuelve ({anio: ruta elegida}, [(ruta omitida, anio), ...]).
    """
    grupos = {}
    for f in archivos:
        n = os.path.basename(f)
        if n.startswith("~$"):
            continue
        a = re.search(r"\b(20\d\d)\b", n)
        grupos.setdefault(a.group(1) if a else n, []).append(f)
    elegidos, omitidos = {}, []
    for a, fs in grupos.items():
        fs = sorted(fs, key=os.path.getmtime, reverse=True)
        elegidos[a] = fs[0]
        omitidos += [(x, a) for x in fs[1:]]
    return elegidos, omitidos


def _mod(f):
    return f"{datetime.datetime.fromtimestamp(os.path.getmtime(f)):%d/%m/%Y %H:%M}"


_el46, _om46 = pro46_por_anio(glob.glob(config.ruta(config.GLOB_MP)))
for _x, _a in _om46:
    print(f"  (PRO-REG-46 OMITIDO por duplicar {_a}): {os.path.basename(_x)} [{_mod(_x)}]")
    print(f"      se carga el mas reciente: {os.path.basename(_el46[_a])} "
          f"[{_mod(_el46[_a])}]. Aparta el que sobre.")
for _a, f in sorted(_el46.items()):
    n46 = os.path.basename(f)
    _anios46[_a] = n46
    _f46.append(n46)
    _ap46[n46] = {"enlaces": 0, "fechas": []}
    try:
        xls46 = pd.ExcelFile(f)
    except Exception as e:                                          # noqa: BLE001
        print("  (no se pudo leer el PRO-REG-46):", e)
        continue
    for hoja in xls46.sheet_names:
        d46 = pd.read_excel(xls46, sheet_name=hoja)
        d46.columns = [str(c).strip() for c in d46.columns]
        if "lote proveedor" not in d46.columns or "Lote SW" not in d46.columns:
            continue
        _c_rec = next((c for c in d46.columns if _RX_REC46.search(c)), None)
        if _c_rec:
            _ap46[n46]["fechas"].append(pd.to_datetime(d46[_c_rec], errors="coerce"))
        for _, x in d46[d46["lote proveedor"].notna() & d46["Lote SW"].notna()].iterrows():
            sw = norm(x["Lote SW"])
            if not es_lote(sw):
                continue
            for p in lotes_prov(x["lote proveedor"]):
                MP_DE_SW.setdefault(sw, set()).add(laxo_prov(p))
                PROV_46[laxo_prov(p)] = hoja
                _ap46[n46]["enlaces"] += 1

if _f46:
    print(f"  materias primas: {len(_f46)} PRO-REG-46 ({', '.join(sorted(_anios46))}) -> "
          f"{len(MP_DE_SW)} lotes SW enlazados con {len(PROV_46)} lotes de proveedor")
else:
    print("  (sin PRO-REG-46: no se puede arrastrar el bloqueo de materia prima)")

# ---- muestras de materia prima, con las mismas columnas internas que el resto
# para poder reutilizar historia() y su regla de vigencia sin duplicarla
if _MP_CRUDAS:
    mp = pd.concat(_MP_CRUDAS, ignore_index=True)
    mp["_L"] = mp["LOTE ORIGEN"].map(lambda x: (lotes_prov(x) or [""])[0]).map(laxo_prov)
    mp["_TODOS"] = mp["LOTE ORIGEN"].map(lambda x: [laxo_prov(p) for p in lotes_prov(x)])
    mp["_FECHA"] = pd.to_datetime(mp["FECHA INGRESO"], errors="coerce")
    _mlm = mp[LM].astype(str).apply(lambda c: c.str.strip().str.upper())
    mp["_LM_P"] = (_mlm == "P").any(axis=1)
    mp["_LM_DATO"] = mp[LM].notna().any(axis=1)
    mp["_LIS_APLICA"] = True          # en materia prima no hay destino que la exima
    mp["_RAM"] = ram_promedio(mp)
    mp["_RAM_TECHO"] = ram_techo(mp)
    mp["_NIT"] = pd.NA                # la MP no trae nitrito ni WPS
    mp["_WPS"] = pd.NA
    mp["_NIT_APLICA"] = False
    mp = mp[mp["_L"].str.len() >= MIN_PROV]
else:
    mp = pd.DataFrame(columns=["_L", "_FECHA", "_LM_P", "_LM_DATO", "_LIS_APLICA",
                               "_RAM", "_RAM_TECHO", "_NIT", "_WPS", "_NIT_APLICA", "OBSERVACIÓN"])

# ------------------------------------------------- linea de proceso
# El nitrito es un control de la linea REFRIGERADA: en la congelada el criterio no
# aplica. La clasificacion sale primero del texto del laboratorio, que es el que
# nombra la linea, y si no alcanza, de la condicion del producto en bodega
# (CONDICION concuerda con el nombre en todos los productos que lo declaran).
# Ante la duda NO se clasifica como congelada: ignorar un criterio es la direccion
# permisiva y no se toma por defecto.
_COND = "CONDICIÓN" if "CONDICIÓN" in stock.columns else "CONDICION"
_porlote = stock.groupby("_L").agg(
    cond=(_COND, lambda x: set(x.dropna().astype(str).str.upper())),
    nom=("NOMBRE PRODUCTO", lambda x: " ".join(set(x.dropna().astype(str))).lower()))
_LOTES_ST = sorted(_porlote.index)


def linea_stock(l):
    """Linea de un lote segun su stock. Vacio = no se pudo determinar."""
    if l not in _porlote.index:
        return ""
    r = _porlote.loc[l]
    if "refrigerad" in r["nom"] or ({"REFRIGERADO", "FRESCO"} & r["cond"]):
        return "REFRIGERADA"
    if "carpaccio" in r["nom"] or r["cond"] == {"CONGELADO"}:
        return "CONGELADA"
    return ""


_txt = (lab["GRUPO"].fillna("").astype(str) + " " + lab["PRESENTACIÓN"].fillna("").astype(str)
        + " " + lab["OBSERVACIÓN"].fillna("").astype(str)).str.lower()


def _linea_muestra(i, l):
    t = _txt.iloc[i]
    if "refrigerad" in t:
        return "REFRIGERADA"
    if "carpaccio" in t or "congelad" in t:
        return "CONGELADA"
    # emparenta y no un prefijo suelto: un lote corto (SW26107) solo calza por
    # igualdad; con prefijo calzaria con cualquier lote que empiece igual
    base = next((x for x in _LOTES_ST if es_lote(x) and emparenta(x, l)), None)
    return linea_stock(base) if base else ""


# ---- destino EE.UU.
# Listeria es permisible en linea congelada, salvo lo que se exporta a EE.UU.
# Se usan dos señales: el cliente del stock (dato directo del destino) y el texto
# del producto (wheel, bacon, nombre en ingles). Basta una para marcar destino USA.
# Un lote con varios clientes queda marcado si CUALQUIERA es de EE.UU.: las cajas
# comparten lote y no se pueden separar.
US_CLI = re.compile(config.US_CLI, re.I)
CR_CLI = re.compile(config.CR_CLI, re.I)
# Bacon y wheel salen congelados de planta pero se venden refrigerados en destino:
# para el nitrito se evaluan como linea refrigerada, no como congelada.
BACON_WHEEL = re.compile(config.BACON_WHEEL, re.I)
US_PROD = re.compile(config.US_PROD, re.I)
_cli = stock.groupby("_L").agg(
    cli=("CLIENTE", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))),
    nom=("NOMBRE PRODUCTO", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))))


def destino_restringido(l):
    """Destino que exige ausencia de Listeria aunque el producto sea congelado.

    Devuelve "EE.UU.", "Costa Rica", "" (ningun destino restringido) o None si no
    hay con que determinarlo. None no equivale a "": sin informacion el criterio
    se aplica igual.

    Es el destino del LOTE, resuelto hacia lo estricto. Para el reparto caja por
    caja esta _CAJAS_DEST.
    """
    if l is None or l not in _cli.index:
        return None
    r = _cli.loc[l]
    if CR_CLI.search(r["cli"]):
        return "Costa Rica"
    if US_CLI.search(r["cli"]) or US_PROD.search(r["nom"]):
        return "EE.UU."
    return ""


# ---- reparto de cajas por destino DENTRO del mismo lote
# Resolver el lote hacia lo estricto es correcto para decidir si el criterio aplica,
# pero deja invisible algo que hace falta para firmar: una firma para Nacional no
# alcanza al lote, y sin embargo alcanza a las cajas que van a Nacional.
#
# Y aca el dato existe, a diferencia de la letra de batch: Fishken registra el
# CLIENTE caja por caja. Que no se pueda separar por batch de ahumado no significa
# que no se pueda separar por destino.
def _destino_fila(cli, nom):
    if CR_CLI.search(cli):
        return "Costa Rica"
    if US_CLI.search(cli) or US_PROD.search(nom):
        return "EE.UU."
    return ""


_dest_caja = pd.Series(
    [_destino_fila(str(c), str(n)) for c, n in zip(
        stock["CLIENTE"].fillna("").astype(str),
        stock["NOMBRE PRODUCTO"].fillna("").astype(str))],
    index=stock.index)
# una fila de stock es una caja
_CAJAS_DEST = {l: g.value_counts().to_dict() for l, g in _dest_caja.groupby(stock["_L"])}
_mixtos = [l for l, d in _CAJAS_DEST.items() if len(d) > 1]
if _mixtos:
    print(f"  destino: {len(_mixtos)} lote(s) tienen cajas de distinto destino en el mismo "
          f"lote ({sum(sum(_CAJAS_DEST[l].values()) for l in _mixtos)} cajas). El estado del "
          "lote se resuelve hacia lo estricto; el reparto va en la columna CAJAS POR DESTINO")


def nombre_destino(d):
    """Como se lee un destino en pantalla. "" no es 'sin dato': es 'sin restriccion'."""
    return d or "sin destino restringido"


def reparto_destino(clave, mercados=()):
    """(texto del reparto, cajas que cubre la firma, cajas totales) de un lote.

    Sin stock devuelve ("", 0, 0). Sin mercados la firma vale para todo, asi que
    cubre todas.
    """
    d = _CAJAS_DEST.get(clave) or {}
    if not d:
        return "", 0, 0
    txt = "; ".join(f"{nombre_destino(k)}: {v} caja(s)"
                    for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0])))
    cub = sum(v for k, v in d.items() if cubre(mercados, k)[0])
    return txt, cub, sum(d.values())


lab["_LINEA"] = [_linea_muestra(i, l) for i, l in enumerate(lab["_L"])]


def _bw(i, l):
    """Bacon o wheel, segun el texto del laboratorio o el producto en bodega."""
    if BACON_WHEEL.search(_txt.iloc[i]):
        return True
    base = next((x for x in _LOTES_ST if es_lote(x) and emparenta(x, l)), None)
    return bool(base and BACON_WHEEL.search(_cli.loc[base, "nom"]))


lab["_BW"] = [_bw(i, l) for i, l in enumerate(lab["_L"])]
# El nitrito aplica a la linea refrigerada y a bacon/wheel aunque figuren congelados.
lab["_NIT_APLICA"] = (lab["_LINEA"] != "CONGELADA") | lab["_BW"]
print(f"  bacon/wheel: {int(lab['_BW'].sum())} muestras se evaluan como refrigeradas "
      "para el nitrito")


def _restr_muestra(i, l):
    if US_PROD.search(_txt.iloc[i]):
        return "EE.UU."
    base = next((x for x in _LOTES_ST if es_lote(x) and emparenta(x, l)), None)
    return destino_restringido(base)


# Listeria aplica siempre a linea refrigerada. En congelada solo si el destino es
# EE.UU. o Costa Rica, o si no se pudo determinar: no se exime un criterio por
# falta de informacion.
_restr = [_restr_muestra(i, l) for i, l in enumerate(lab["_L"])]
lab["_DESTINO"] = [x if x is not None else "" for x in _restr]
lab["_LIS_APLICA"] = [(ln != "CONGELADA") or (d is None) or (d != "")
                      for ln, d in zip(lab["_LINEA"], _restr)]
_ex = lab[lab["_LM_DATO"] & ~lab["_LIS_APLICA"]]
print(f"  listeria: no aplica a {len(_ex)} muestras de linea congelada sin destino "
      f"restringido (de {int(lab['_LM_DATO'].sum())} con dato de listeria)")
_c = lab.loc[lab["_NIT"].notna(), "_LINEA"].replace("", "sin clasificar").value_counts()
print("  linea de proceso en muestras con nitrito: "
      + ", ".join(f"{k}={v}" for k, v in _c.items()))

# ----------------------------------------------------------------- DETENCIONES
# La fuente es Postgres: las detenciones se registran en el sitio, a nombre de
# quien las carga. El xlsx quedo como historico y solo se usa si no hay conexion,
# porque una detencion que no se lee es producto que sale sin estar liberado.
COLS_DET = ["ID", "FECHA CORREO", "EMITIDO POR", "ASUNTO / REFERENCIA",
            "TIPO DE DESVIACION", "DESCRIPCION", "LOTE", "PRODUCTO", "ALCANCE",
            "CANTIDAD AFECTADA (KG)", "FECHA DEL EVENTO", "RESOLUCION",
            "CRITERIOS DE LIBERACION", "ESTADO"]


CRITERIOS_DB = ("LISTERIA", "RAM", "NITRITO")     # el enum criterio de la base


def lee_criterios(v):
    """(criterios reconocidos, textos no reconocidos) de CRITERIOS DE LIBERACION.

    La columna es criterio[] en Postgres, un enum propio, y psycopg no sabe
    convertir un arreglo de un tipo que no conoce: llega como TEXTO con forma de
    arreglo, '{LISTERIA,RAM}'. El motor partia por ';', no reconocia
    '{LISTERIA,RAM}' como criterio y ninguna detencion de la base se podia cerrar
    contra el laboratorio. Se acepta lo que pueda llegar: lista o tupla, arreglo de
    Postgres ('{LISTERIA,RAM}', '{"RAM"}', '{}'), JSON ('["RAM"]') o el texto del
    xlsx historico ('LISTERIA; RAM'). Mayusculas y espacios no importan.

    Un texto que no es un criterio conocido NO se descarta: se devuelve aparte y
    deja la detencion vigente, porque no se puede acreditar que se midio.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return [], []
    if isinstance(v, (list, tuple, set, np.ndarray)):
        partes = [str(x) for x in v]
    else:
        t = str(v).strip()
        if t.startswith("[") and t.endswith("]"):
            try:
                j = json.loads(t)
                partes = [str(x) for x in j] if isinstance(j, list) else [t]
            except ValueError:
                partes = re.split(r"[;,]", t[1:-1])
        elif t.startswith("{") and t.endswith("}"):
            partes = t[1:-1].split(",")
        else:
            partes = re.split(r"[;,]", t)
    ok, raro = [], []
    for p in partes:
        c = p.strip().strip('"').strip("'").strip().upper()
        if not c or c in ("NAN", "NONE", "NULL"):
            continue
        (ok if c in CRITERIOS_DB else raro).append(c)
    return list(dict.fromkeys(ok)), list(dict.fromkeys(raro))


def detenciones_de_postgres():
    """Detenciones desde la base. None si no se puede, para caer al xlsx."""
    url = os.environ.get("BLOQUEOS_DB_URL")
    if not url:
        return None
    try:
        import psycopg
    except ImportError:
        print("  (sin driver psycopg: las detenciones salen del xlsx historico)")
        return None
    try:
        # cursor directo y no pd.read_sql: con psycopg3 pandas avisa que solo
        # soporta SQLAlchemy y ensucia la salida sin que haya nada que arreglar
        with psycopg.connect(url, connect_timeout=15) as cx:
            with cx.cursor() as cur:
                cur.execute("select * from bloqueos.detencion order by id")
                cols = [c.name for c in cur.description]
                d = pd.DataFrame(cur.fetchall(), columns=cols)
    except Exception as e:                                          # noqa: BLE001
        print("  (no se pudo leer detencion en Postgres):", str(e).splitlines()[0][:90])
        return None
    if not len(d):
        print("  (la tabla detencion esta vacia: se usa el xlsx historico)")
        return None
    return pd.DataFrame({
        "ID": d["id"], "FECHA CORREO": d["fecha_correo"], "EMITIDO POR": d["emitido_por"],
        "ASUNTO / REFERENCIA": d["referencia"], "TIPO DE DESVIACION": d["tipo"],
        "DESCRIPCION": d["descripcion"], "LOTE": d["lote"], "PRODUCTO": d["producto"],
        "ALCANCE": d["alcance"], "CANTIDAD AFECTADA (KG)": d["cantidad_kg"],
        "FECHA DEL EVENTO": d["fecha_evento"], "RESOLUCION": d["resolucion"],
        # se normaliza al leer, para que la hoja DETENCIONES lo muestre legible; lo
        # no reconocido se conserva y vuelve a salir como no reconocido
        "CRITERIOS DE LIBERACION": d["criterios"].map(
            lambda v: "; ".join(sum(lee_criterios(v), []))),
        "ESTADO": d["estado"]})


det = detenciones_de_postgres()
FUENTE_DET = "Postgres (bloqueos.detencion)"
if det is None:
    FUENTE_DET = os.path.basename(F_DET) + " (historico)"
    det = pd.read_excel(F_DET, sheet_name="DETENCIONES", header=4).dropna(how="all")
    det = det[det["ID"].notna()].copy()
print(f"  detenciones: {len(det)} desde {FUENTE_DET}")
det["_L"] = det["LOTE"].map(norm)
# con el sufijo: una detencion sobre una unidad concreta solo la cierra esa unidad
det["_U"] = det["LOTE"].map(norm_u)
det["_EVENTO"] = pd.to_datetime(det["FECHA DEL EVENTO"], errors="coerce")
_lc = det["CRITERIOS DE LIBERACION"].map(lee_criterios)
det["_CRIT"] = _lc.map(lambda x: x[0])
det["_CRIT_RARO"] = _lc.map(lambda x: x[1])
_raros = sorted({c for v in det["_CRIT_RARO"] for c in v})
if _raros:
    print(f"  ATENCION detenciones: criterio(s) de liberacion no reconocido(s) "
          f"({', '.join(_raros)}): esas detenciones quedan vigentes sin propuesta de cierre")
det["_ESTADO"] = det["ESTADO"].astype(str).str.strip().str.upper()
det["_VIGENTE"] = det["_ESTADO"].isin(["ABIERTA", "PNC"])


def binomio(nit, wps):
    """Binomio WPS/nitrito. Devuelve (no_conforme, texto).

    Lo que controla Listeria en el ahumado no es el nitrito solo ni la sal sola,
    sino los dos juntos. La tabla esta en config.py; aqui esta la misma regla
    escrita como se lee: libera si el nitrito llega a 85 y el WPS lo acompania,
    o si el nitrito por si solo pasa de 100.

    Sin WPS medido y con nitrito bajo 100 no se puede acreditar el binomio, asi
    que no libera: la falta de informacion no exime.
    """
    if pd.isna(nit):
        return False, ""
    if nit > NIT_BINOMIO:
        return False, ""
    if nit < LIM_NITRITO:
        return True, (f"Nitrito {nit:.1f} ppm < {LIM_NITRITO}"
                      + (f" (WPS {wps:.2f}% no lo compensa)" if pd.notna(wps)
                         and wps > WPS_MIN else ""))
    # entre 85 y 100: decide el WPS
    if pd.isna(wps):
        return True, (f"Nitrito {nit:.1f} ppm sobre {LIM_NITRITO} pero sin WPS medido: "
                      f"no se puede acreditar el binomio (haria falta WPS > {WPS_MIN}"
                      f" o nitrito > {NIT_BINOMIO})")
    if wps > WPS_MIN:
        return False, ""
    return True, (f"Nitrito {nit:.1f} ppm sobre {LIM_NITRITO} pero no cumple el binomio: "
                  f"WPS {wps:.2f}% no supera {WPS_MIN} y el nitrito no llega a "
                  f"{NIT_BINOMIO} ppm")


def evalua(rows, criterios=None, desde=None):
    """Estado de cada criterio sobre un conjunto de muestras de laboratorio."""
    if desde is not None:
        rows = rows[rows["_FECHA"].notna() & (rows["_FECHA"] >= desde)]
    r = {"n": len(rows)}
    if len(rows) == 0:
        r.update(listeria=None, ram=None, nitrito=None, nit_min=None, wps=None,
                 nit_nc=False, nit_txt="", ar="")
        return r, rows
    # La listeria se mira solo donde se exige, con la misma regla que para el lote:
    # refrigerada siempre, congelada solo con destino EE.UU. o Costa Rica. Sin esto,
    # cerrar una detencion pedia ausencia incluso en producto al que el criterio no
    # se le aplica, y la detencion no se cerraba nunca.
    _apl = rows[rows["_LIS_APLICA"]] if "_LIS_APLICA" in rows else rows
    if _apl["_LM_DATO"].any():
        r["listeria"] = "PRESENCIA" if _apl["_LM_P"].any() else "Ausencia"
    elif rows["_LM_DATO"].any():
        # medido y conforme por no exigible: distinto de que nadie lo haya medido
        r["listeria"] = "NO APLICA"
    else:
        r["listeria"] = None
    r["ram"] = rows["_RAM"].max() if rows["_RAM"].notna().any() else None
    r["ram_techo"] = bool(rows["_RAM_TECHO"].any())
    r["nitrito"] = rows["_NIT"].min() if rows["_NIT"].notna().any() else None
    r["nit_min"] = rows["_NIT_MIN"].min() if rows["_NIT_MIN"].notna().any() else None
    r["wps"] = rows["_WPS"].min() if rows["_WPS"].notna().any() else None
    # El binomio se evalua muestra a muestra: el par nitrito/WPS de UNA muestra
    # decide. Agregarlos por separado y compararlos despues mezclaria el nitrito
    # de una con el WPS de otra.
    _b = [binomio(x["_NIT"], x["_WPS"]) for _, x in rows.iterrows()]
    _mal = [t for nc, t in _b if nc]
    r["nit_nc"] = bool(_mal)
    r["nit_txt"] = "; ".join(sorted(set(_mal)))
    r["ar"] = "R" if (rows["_AR"] == "R").any() else ("A" if (rows["_AR"] == "A").any() else "")
    return r, rows


TXT_RAM_TECHO = "RAM: réplica incontable (sobre el techo del método)"


def lis_txt(v, rows):
    """La listeria de un conjunto de muestras como se muestra en la columna.

    "Ausencia" o "NO APLICA" a secas callaba una PRESENCIA medida en linea congelada
    sin destino restringido: el veredicto no cambia, pero la columna lo dice.
    """
    if v in ("Ausencia", "NO APLICA") and len(rows) and             (rows["_LM_P"] & ~rows["_LIS_APLICA"].astype(bool)).any():
        return f"{v} (con PRESENCIA no exigible por destino)"
    return v


def incumple(r, criterio):
    """(no_conforme, falta_dato, texto) para un criterio dado."""
    if criterio == "LISTERIA":
        if r["listeria"] is None:
            return False, True, "sin dato de listeria"
        if r["listeria"] == "NO APLICA":
            return False, False, ("Listeria medida pero no exigible: linea congelada sin "
                                  "destino EE.UU. ni Costa Rica")
        return r["listeria"] == "PRESENCIA", False, "Listeria: PRESENCIA"
    if criterio == "RAM":
        if r.get("ram_techo"):
            return True, False, TXT_RAM_TECHO
        if r["ram"] is None:
            return False, True, "sin dato de RAM"
        return r["ram"] > LIM_RAM, False, (f"RAM promedio {r['ram']:,.0f} UFC/g > "
                                           f"{LIM_RAM:,}").replace(",", ".")
    if criterio == "NITRITO":
        if r["nitrito"] is None:
            return False, True, "sin dato de nitrito"
        return r["nit_nc"], False, r["nit_txt"]
    return False, True, f"criterio no reconocido: {criterio}"


# ------------------------------------------------- DETENCION HISTORICA
# Bloqueo 2026.xlsm es el Excel de detenciones historicas. Cada fila es un bloqueo declarado
# por una persona, con su motivo escrito. La hoja Historia es el log de
# liberaciones con su mercado.
#
# La columna Estado se escribe UNICAMENTE al liberar. Una fila sin estado es un
# bloqueo vigente, y la evidencia es concluyente:
#   - las 420 filas 'liberado' tienen fecha de liberacion; las 2.591 sin estado,
#     ninguna, sin una sola excepcion;
#   - el 95% de las filas sin estado trae motivo escrito, y son los mismos
#     motivos que las 'Bloqueado' (presencia de LM, RAM alto, documentacion);
#   - la columna mal llamada 'liberado' dice "bloqueado" en 215 de ellas, y
#     nunca "liberado";
#   - 1.219 trazas aparecen solo sin estado: el estado no esta en otra fila.
# Las 1.734 filas que dicen 'Bloqueado' son un bloque contiguo de produccion
# 2024-enero 2025, de la convencion anterior; se leen igual.
#
# Un bloqueo declarado tiene la misma naturaleza que una detencion por correo:
# lo escribe una persona, no se recalcula, y solo lo cierra una liberacion
# explicita o un resultado de laboratorio posterior que cubra SU motivo.
F_OPE = config.ruta(config.ARCH_OPERATIVO)
MERCADOS = ("Nacional", "Exportación", "USA")
reg, blo = [], []


def _fecha_ope(s):
    """La fecha viene como datetime, como serial de Excel o como texto libre.

    En el bloque historico la columna FECHA BLOQUEO trae el motivo ('ALTO RAM')
    en vez de una fecha; eso no es un error de lectura, es como se llevaba antes.
    """
    out = pd.to_datetime(s, errors="coerce")
    num = pd.to_numeric(s, errors="coerce")
    ser = pd.to_datetime(num.where(num.between(40000, 60000)), unit="D",
                         origin="1899-12-30", errors="coerce")
    return out.fillna(ser)


if os.path.exists(F_OPE):
    try:
        _h = pd.read_excel(F_OPE, sheet_name="Historia")
        _h.columns = [str(c).strip() for c in _h.columns]
        for _, x in _h[_h["Lote"].notna()].iterrows():
            mk = [m for m in MERCADOS
                  if str(x.get(m, "")).strip().lower() in ("si", "sí", "x", "ok", "1")]
            reg.append({"_L": norm(x["Lote"]), "FECHA": pd.to_datetime(x["Fecha"], errors="coerce"),
                        "MERCADOS": "/".join(mk), "FUENTE": "Historia"})
    except Exception as e:                                              # noqa: BLE001
        print("  (no se pudo leer la hoja Historia):", e)
    try:
        _o = pd.read_excel(F_OPE, sheet_name="codigos bloqueados SAP", header=1).dropna(how="all")
        _o.columns = [str(c).strip() for c in _o.columns]
        _o = _o[_o["Traza"].notna()].copy()
        _o["_E"] = _o["Estado"].astype(str).str.strip().str.lower()
        _o["_FB"] = _fecha_ope(_o["FECHA BLOQUEO"])
        # el encabezado lleva tilde y segun como se guarde el libro llega de dos formas
        _cdesc = next((c for c in _o.columns if c.lower().startswith("descripci")), None)
        for _, x in _o[_o["_E"] == "liberado"].iterrows():
            mk = [m for m, c in zip(MERCADOS, ("NACIONAL", "EXPORTACIÓN", "USA"))
                  if pd.notna(x.get(c))]
            reg.append({"_L": norm(x["Traza"]),
                        "FECHA": pd.to_datetime(x["Fecha Liberacion"], errors="coerce"),
                        "MERCADOS": "/".join(mk), "FUENTE": "Registro SAP"})
        for _, x in _o[_o["_E"] != "liberado"].iterrows():
            # el motivo esta en Observacion; en el bloque historico quedo escrito
            # en la columna de la fecha, asi que se toman los dos
            mot = " / ".join(dict.fromkeys(
                str(v).strip() for v in (x.get("Observacion"), x.get("FECHA BLOQUEO"))
                if pd.notna(v) and isinstance(v, str) and str(v).strip()))
            blo.append({"_L": norm(x["Traza"]), "_U": norm_u(x["Traza"]),
                        "LOTE": str(x["Traza"]).strip(),
                        "FECHA": x["_FB"], "MOTIVO": mot,
                        "PRODUCTO": str(x.get(_cdesc, "") or "").strip() if _cdesc else "",
                        "DECLARADO": "Bloqueado" if x["_E"] == "bloqueado" else "sin estado"})
    except Exception as e:                                              # noqa: BLE001
        print("  (no se pudo leer la hoja de codigos bloqueados):", e)
else:
    print("  (sin Bloqueo 2026.xlsm: no hay detencion historica que cruzar)")

if reg:
    _lib = pd.DataFrame(reg)
    _lib = _lib[_lib["_L"].map(es_lote)]
    libu = _lib.groupby("_L").agg(
        FECHA=("FECHA", "max"),
        MERCADOS=("MERCADOS", lambda x: "/".join(sorted({k for v in x for k in str(v).split("/") if k}))),
        FUENTE=("FUENTE", lambda x: " / ".join(sorted(set(x)))))
    print(f"  liberaciones declaradas: {len(_lib)} registros sobre {len(libu)} lotes"
          + (f", hasta {_lib['FECHA'].max():%d/%m/%Y}" if _lib["FECHA"].notna().any() else ""))
else:
    libu = pd.DataFrame(columns=["FECHA", "MERCADOS", "FUENTE"])
LIBK = list(libu.index)


def liberacion(clave):
    """Liberacion declarada para un lote o batch: fecha, mercados y de donde sale."""
    k = [x for x in LIBK if emparenta(x, clave)]
    if not k:
        return "", "", ""
    m = libu.loc[k]
    f = m["FECHA"].max()
    mk = sorted({v for x in m["MERCADOS"] for v in str(x).split("/") if v})
    return (f.strftime("%Y-%m-%d") if pd.notna(f) else ""), "/".join(mk), \
        " / ".join(sorted({v for x in m["FUENTE"] for v in str(x).split(" / ")}))


# ------------------------------------------------- BLOQUEOS DECLARADOS
# Cada fila de bloqueo se cierra sola si despues aparece una liberacion declarada
# para el mismo lote (o para el lote padre: la liberacion del lote base alcanza a
# sus batches). Sin fecha de bloqueo no se puede acreditar que la liberacion sea
# posterior, asi que en ese caso basta con que exista.
def criterios_del_motivo(txt):
    """Criterios de laboratorio que pueden levantar un motivo escrito a mano."""
    t = str(txt).lower()
    return [c for rx, c in config.MOTIVOS_LAB if re.search(rx, t)]


HOY = pd.Timestamp.now().normalize()
ope = pd.DataFrame(columns=["_L", "_U", "LOTE", "FECHA", "MOTIVO", "PRODUCTO",
                            "DECLARADO", "_CRIT"])


def alcanza(traza_u, unidad_u):
    """Si un bloqueo declarado sobre traza_u alcanza a esta unidad del laboratorio.

    Cuando quien lo escribio puso el sufijo -y lo pone en el 64% de los casos-
    identifico el dia exacto: @2CK26621761E*29W es el 15 de julio, y no dice nada
    del 10 ni del 13. Sin sufijo, el bloqueo es sobre el lote y alcanza a todas
    sus unidades.

    Contra el STOCK se sigue bloqueando el lote entero igual: Fishken no registra
    el sufijo, asi que las cajas de los dias conformes no se pueden separar.
    """
    if "*" in traza_u:
        return unidad_u == traza_u or unidad_u.startswith(traza_u)
    return emparenta(unidad_u.split("*")[0], traza_u)
if blo:
    ope = pd.DataFrame(blo)
    ope = ope[ope["_L"].map(es_lote)].copy()
    _cerrada = []
    for _, x in ope.iterrows():
        k = [j for j in LIBK if emparenta(j, x["_L"])]
        f = libu.loc[k, "FECHA"].max() if k else pd.NaT
        _cerrada.append(bool(k) and (pd.isna(x["FECHA"]) or
                                     (pd.notna(f) and f >= x["FECHA"])))
    ope["_CERRADA"] = _cerrada
    ope["_CRIT"] = ope["MOTIVO"].map(criterios_del_motivo)
    _ab = ope[~ope["_CERRADA"]]
    print(f"  bloqueos declarados en el registro: {len(ope)} filas sobre "
          f"{ope['_L'].nunique()} lotes; {len(_ab)} siguen abiertos "
          f"({_ab['_L'].nunique()} lotes)"
          + (f", hasta {_ab['FECHA'].max():%d/%m/%Y}" if _ab["FECHA"].notna().any() else ""))
    _sc = _ab[_ab["_CRIT"].map(len) == 0]
    print(f"  de esos, {len(_sc)} tienen un motivo que el laboratorio no puede levantar "
          f"(documentacion, reclamo, desvio de proceso o sin motivo escrito)")
    _fut = _ab[_ab["FECHA"] > HOY]
    if len(_fut):
        print(f"  ATENCION: {len(_fut)} con fecha de bloqueo futura (hasta "
              f"{_fut['FECHA'].max():%d/%m/%Y}), probable tipeo de anio: quedan "
              f"bloqueados sin forma de liberarse")
    ope = _ab.reset_index(drop=True)


# ------------------------------------------------- DECISIONES FIRMADAS
# Lo declarado por Calidad. El motor lo lee y nunca lo escribe. Es lo unico
# que convierte un CANDIDATO A LIBERAR en LIBERADO.
#
# Se firman en el sitio y quedan en Postgres, igual que las detenciones. El xlsx
# es historico: una firma que el motor no lee es producto que sigue figurando
# bloqueado despues de que alguien se hizo responsable de liberarlo.
F_DEC = config.ruta("REGISTRO DECISIONES.xlsx")
COLS_DEC = ["ID", "FECHA", "TIPO", "LOTE", "BATCH", "DETENCION", "ANULA", "MERCADOS",
            "EVIDENCIA", "COMENTARIO", "FIRMADO POR", "RUT",
            "HUELLA DE CRITERIOS AL FIRMAR", "TRATAMIENTO", "RUTA"]
dec = pd.DataFrame(columns=COLS_DEC)


def decisiones_de_postgres():
    """Firmas desde la base. None si no se puede, para caer al xlsx."""
    url = os.environ.get("BLOQUEOS_DB_URL")
    if not url:
        return None
    try:
        import psycopg
    except ImportError:
        return None
    try:
        with psycopg.connect(url, connect_timeout=15) as cx:
            with cx.cursor() as cur:
                # el nombre de quien firma vive en usuario, que el motor no puede
                # leer: se resuelve en la vista y aqui basta con el id
                cur.execute("select d.id, d.firmado_en, d.tipo, d.lote, d.batch, "
                            "d.detencion_id, d.anula, d.mercados, d.evidencia, "
                            "d.comentario, d.firmado_por::text, v.huella, "
                            "d.tratamiento, d.ruta "
                            "from bloqueos.decision d "
                            "left join bloqueos.criterio_version v on v.id = d.criterio_ver "
                            "order by d.id")
                filas = cur.fetchall()
    except Exception as e:                                          # noqa: BLE001
        print("  (no se pudo leer decision en Postgres):", str(e).splitlines()[0][:90])
        return None
    if not filas:
        return None
    d = pd.DataFrame(filas, columns=["ID", "FECHA", "TIPO", "LOTE", "BATCH", "DETENCION",
                                     "ANULA", "MERCADOS", "EVIDENCIA", "COMENTARIO",
                                     "FIRMADO POR", "HUELLA DE CRITERIOS AL FIRMAR",
                                     "TRATAMIENTO", "RUTA"])
    d["MERCADOS"] = d["MERCADOS"].map(
        lambda v: "/".join(v) if isinstance(v, (list, tuple)) else (v or ""))
    d["RUT"] = ""
    return d[COLS_DEC]


_dpg = decisiones_de_postgres()
FUENTE_DEC = "Postgres (bloqueos.decision)"
if _dpg is not None:
    dec = _dpg
elif os.path.exists(F_DEC):
    FUENTE_DEC = os.path.basename(F_DEC) + " (historico)"
    try:
        _d = pd.read_excel(F_DEC, sheet_name="DECISIONES", header=4).dropna(how="all")
        _d = _d[_d["ID"].notna()]
        _d = _d[~_d["ID"].astype(str).str.upper().str.startswith("EJEMPLO")]
        if len(_d):
            dec = _d
    except Exception as e:                                          # noqa: BLE001
        print("  (no se pudo leer REGISTRO DECISIONES.xlsx):", e)
if len(dec):
    dec["_FECHA"] = pd.to_datetime(dec["FECHA"], errors="coerce")
    dec["_TIPO"] = dec["TIPO"].astype(str).str.strip().str.upper()
    dec["_LOTE"] = dec["LOTE"].map(norm, na_action="ignore")
    dec["_BATCH"] = dec["BATCH"].map(norm, na_action="ignore")
    # lo firmado, CON sufijo: el batch si se anoto, si no el lote. Una firma sobre una
    # unidad (*SSD) o sobre un batch no alcanza al lote que la contiene
    dec["_OBJ"] = [norm_u(b) if pd.notna(b) and str(b).strip() else
                   (norm_u(x) if pd.notna(x) else "") for b, x in zip(dec["BATCH"], dec["LOTE"])]
    anuladas = set(dec.loc[dec["_TIPO"] == "ANULACION", "ANULA"].dropna().astype(str))
    dec = dec[~dec["ID"].astype(str).isin(anuladas)]
    print(f"  decisiones firmadas vigentes: {len(dec)} desde {FUENTE_DEC}")
else:
    dec["_FECHA"] = pd.NaT
    dec["_TIPO"] = ""
    dec["_LOTE"] = ""
    dec["_BATCH"] = ""
    dec["_OBJ"] = ""


# Lo que cada tratamiento corrige de verdad. Las altas presiones hidrostaticas
# son un proceso letal: resuelven la carga microbiana, pero no cambian la
# quimica. Un nitrito bajo sigue bajo despues del APH, y un lote con ese
# problema no queda liberado por haber pasado por la maquina.
LEVANTA = {"APH": {"LISTERIA", "RAM"}}


def cubre(mercados, d):
    """Si una firma para ciertos mercados alcanza a UN destino concreto.

    Liberar para Nacional no es liberar para Echo Falls. Sin mercados anotados
    la firma vale para todo, que es como se firmaba antes.

    Se separa de cubre_destino para poder preguntarlo caja por caja sin repetir
    la regla: la unica definicion de que mercado cubre que destino vive aca.
    """
    if not mercados:
        return True, ""
    m = {x.strip().upper() for x in mercados if str(x).strip()}
    if d == "EE.UU." and not ({"USA", "EEUU", "EE.UU."} & m):
        return False, "el destino es EE.UU. y la firma no lo cubre"
    if d == "Costa Rica" and not ({"COSTA RICA", "EXPORTACION", "EXPORTACIÓN"} & m):
        return False, "el destino es Costa Rica y la firma no lo cubre"
    if d is None:
        return False, "no se pudo determinar el destino, asi que no se puede acreditar "\
                      "que la firma lo cubra"
    return True, ""


def cubre_destino(mercados, clave):
    """Si una firma alcanza al destino del LOTE, resuelto hacia lo estricto."""
    return cubre(mercados, destino_restringido(clave))


def firmada(clave, rows_lab, causas_vivas=()):
    """Liberacion firmada aplicable a un lote o batch.

    Devuelve (dict de la decision, aviso) o (None, ""). El aviso dice por que
    una firma existente NO alcanza: llego un resultado no conforme despues,
    cambiaron los criterios, la firma no cubre el destino de este lote, o el
    tratamiento no corrige lo que lo bloquea.
    """
    if not len(dec):
        return None, ""
    # Una firma alcanza a la clave solo si se firmo sobre ella o sobre un lote que la
    # contiene. Hasta el 30/09/2026 bastaba que se emparentaran en cualquier sentido:
    # una firma sobre el batch M, o sobre la unidad *37V (el sufijo se perdia al
    # normalizar), liberaba el lote entero con sus otros batches y dias. Es la regla
    # por unidad aplicada a la firma: lo firmado sobre una parte no cierra el todo.
    lib = dec[dec["_TIPO"] == "LIBERACION"]
    def _alcanza_firma(t):
        if not t or "*" in t:
            return False
        return es_lote(t) and emparenta(t, clave) and len(t) <= len(clave)
    m = lib[lib["_OBJ"].fillna("").map(_alcanza_firma)]
    if not len(m):
        parte = lib[lib["_OBJ"].fillna("").map(
            lambda t: bool(t) and emparenta(t.split("*")[0], clave))]
        if len(parte):
            return None, ("Hay firma(s) sobre una parte del lote ("
                          + ", ".join(sorted(set(parte["_OBJ"]))[:3]) + "): una firma sobre "
                          "un batch o una unidad no libera el lote que la contiene")
        return None, ""
    d = m.sort_values("_FECHA").iloc[-1]
    f = d["_FECHA"]
    if pd.notna(f) and len(rows_lab):
        post = rows_lab[rows_lab["_FECHA"] > f]
        # por unidad, igual que el veredicto: un no conforme posterior de una unidad
        # supera la firma aunque despues llegue un conforme de OTRA unidad
        _ap, _ = resume(post)
        for c in CRIT:
            h = _ap[c]
            if h["estado"] == "NO CONFORME":
                return None, (f"Liberacion firmada {d['ID']} del {f:%d/%m/%Y} SUPERADA: "
                              f"hay un resultado posterior no conforme ({h['txt']})")
    # ---- alcance por mercado
    merc = [x for x in str(d.get("MERCADOS", "") or "").split("/") if x.strip()]
    ok, por_que = cubre_destino(merc, clave)
    if not ok:
        # el lote se resuelve hacia lo estricto, pero decir solo "no aplica aqui"
        # esconde que la firma SI alcanza a parte del stock. El cliente esta
        # registrado caja por caja: se puede decir cuantas, y hace falta decirlo.
        rep, cub, tot = reparto_destino(clave, merc)
        detalle = ""
        if cub and cub < tot:
            detalle = (f" Alcanza a {cub} de {tot} caja(s) del lote ({rep}): las otras "
                       f"{tot - cub} son las que la firma no cubre. Separarlas es posible "
                       "-el cliente esta por caja- pero el estado del lote muestra lo mas "
                       "estricto y esa separacion la decide Calidad.")
        return None, (f"Liberacion firmada {d['ID']} para {'/'.join(merc)}: no libera el lote "
                      f"porque {por_que}.{detalle}")

    # ---- alcance por tratamiento
    trat = str(d.get("TRATAMIENTO", "") or "").strip().upper()
    if trat:
        levanta = LEVANTA.get(trat, set())
        fuera = [c for c in causas_vivas if c not in levanta]
        if fuera:
            return None, (f"Liberacion por {trat} ({d['ID']}): el tratamiento no corrige "
                          f"{', '.join(fuera)}. Sigue bloqueado por eso.")

    aviso = ""
    hf = str(d.get("HUELLA DE CRITERIOS AL FIRMAR", "")).strip()
    if hf and hf != config.huella_criterios():
        aviso = (f"Los criterios cambiaron despues de firmar {d['ID']}: "
                 "conviene revalidar la liberacion")
    if merc:
        aviso = (aviso + " | " if aviso else "") + f"Firma valida solo para {'/'.join(merc)}"
    return d, aviso


CRIT = ("LISTERIA", "RAM", "NITRITO")


def cod_lab(v):
    """El codigo de laboratorio a veces viene como numero (9250.0) y a veces con
    letra ('1623A'). Un rstrip aqui se come los ceros finales."""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(v).strip()
    except (TypeError, ValueError):
        return str(v).strip() or "?"


def con_dato(rows, c):
    """Muestras que midieron el criterio, aplique o no."""
    if c == "LISTERIA":
        return rows[rows["_LM_DATO"]]
    if c == "RAM":
        return rows[rows["_RAM"].notna() | rows["_RAM_TECHO"]]
    return rows[rows["_NIT"].notna()]


def mide(rows, c):
    """Muestras que midieron el criterio Y a las que el criterio aplica.

    RAM aplica a todo. Nitrito solo a linea refrigerada. Listeria a refrigerada y a
    congelada con destino EE.UU. o Costa Rica. Una muestra sin clasificar NO se
    excluye: no se exime un criterio por falta de informacion.
    """
    if c == "LISTERIA":
        return rows[rows["_LM_DATO"] & rows["_LIS_APLICA"]]
    if c == "RAM":
        return rows[rows["_RAM"].notna() | rows["_RAM_TECHO"]]
    return rows[rows["_NIT"].notna() & rows["_NIT_APLICA"]]


def por_que_no_aplica(rows, c):
    """Texto trazable para un criterio medido pero no exigible, con el valor omitido."""
    if c == "NITRITO":
        mal = [t for _, x in rows.iterrows()
               for nc, t in [binomio(x["_NIT"], x["_WPS"])] if nc]
        return ("Nitrito no aplica: linea congelada (no es bacon ni wheel)"
                + (f" (se omite: {mal[0]})" if mal else ""))
    if c == "LISTERIA":
        ne = presencias_no_exigibles(rows)
        return ("Listeria no aplica: linea congelada sin destino EE.UU. ni Costa Rica"
                + (f" ({ne})" if ne else ""))
    return f"{c.title()} no aplica"


def presencias_no_exigibles(rows):
    """Cada PRESENCIA de listeria que el motor no exige, con su unidad y su fecha.

    Una muestra de linea congelada sin destino EE.UU. ni Costa Rica puede dar
    PRESENCIA y no bloquear, porque ahi el criterio no se exige. El veredicto es
    correcto; lo que no puede pasar es que el texto que lee quien firma la resuma
    como "conforme en LISTERIA" (paso el 30/09/2026 en 2CK2612041, 2CK2614044,
    2CK2617049 y 2CK2620051). Vacio si no hay ninguna.
    """
    if not len(rows) or "_LIS_APLICA" not in rows:
        return ""
    x = rows[rows["_LM_P"] & ~rows["_LIS_APLICA"].astype(bool)]
    if not len(x):
        return ""
    u = x["_U"] if "_U" in x else x["_L"]
    donde = sorted({f"{a} del {f:%d/%m/%Y}" if pd.notna(f) else f"{a} (sin fecha)"
                    for a, f in zip(u, x["_FECHA"])})
    return (f"PRESENCIA de listeria no exigible por destino -linea congelada sin EE.UU. "
            f"ni Costa Rica- en {', '.join(donde[:4])}"
            + (f" y {len(donde) - 4} mas" if len(donde) > 4 else ""))


def _falla(row, c):
    if c == "LISTERIA":
        return bool(row["_LM_P"])
    if c == "RAM":
        return bool(row["_RAM_TECHO"]) or (pd.notna(row["_RAM"]) and row["_RAM"] > LIM_RAM)
    return binomio(row["_NIT"], row["_WPS"])[0]


def _texto(row, c):
    if c == "LISTERIA":
        return "Listeria: PRESENCIA"
    if c == "RAM":
        if row["_RAM_TECHO"]:
            return TXT_RAM_TECHO
        k = int(pd.to_numeric(row[RAM], errors="coerce").notna().sum())
        return (f"RAM promedio {row['_RAM']:,.0f} UFC/g de {k} replica(s) > "
                f"{LIM_RAM:,}").replace(",", ".")
    return binomio(row["_NIT"], row["_WPS"])[1]


# En que se cuenta la evidencia de cada criterio. La listeria son determinaciones
# independientes; el RAM se decide sobre el promedio de las replicas de UNA
# muestra, asi que su unidad es la muestra; el nitrito es una medicion por fila.
UNIDAD = {"LISTERIA": "analisis", "RAM": "muestra(s)", "NITRITO": "medicion(es)"}


def cuenta_analisis(rows, c):
    """(analisis, no conformes) de un criterio. Cuenta determinaciones, no filas.

    Una fila del LAB-REG-08 no es un analisis: es una muestra con hasta cinco
    determinaciones de listeria y cinco de RAM, cada una sobre una unidad
    distinta. La fila del 14/07 de @2CK26681881E*29M trae tres A, o sea tres
    analisis de listeria, y contarla como uno subestima la evidencia justo
    cuando alguien la esta mirando para firmar: hay 1.317 filas con listeria y
    2.799 determinaciones detras.

    El nitrito y el WPS son otra cosa: sus tres columnas son replicas de UNA
    medicion fisicoquimica que se promedia, asi que ahi el analisis es la fila.

    Y desde el 30/09/2026 el RAM tambien: la especificacion es sobre el promedio
    de las replicas de la muestra, no sobre cada replica, asi que lo que falla o
    cumple es la muestra. Contar replicas sobre el limite mostraria como no
    conforme una replica que el promedio absuelve.
    """
    if c == "LISTERIA":
        v = rows[LM].astype(str).apply(lambda col: col.str.strip().str.upper())
        return int(v.isin(["A", "P"]).sum().sum()), int((v == "P").sum().sum())
    if c == "RAM":
        v, t = rows["_RAM"], rows["_RAM_TECHO"]
        return int((v.notna() | t).sum()), int(((v > LIM_RAM) | t).sum())
    return len(rows), int(rows.apply(lambda r: _falla(r, c), axis=1).sum()) if len(rows) else 0


def historia(rows, c, remuestrea=True):
    """Estado VIGENTE de un criterio, no el peor de toda su historia.

    Un resultado reprobado deja de estar vigente solo si despues hay muestras que
    vuelven a medir ESE criterio y salen conformes. El flujo real en planta es
    fallar, tratar (tipicamente altas presiones) y re-muestrear; una muestra
    posterior que no midio lo que fallo no es evidencia de nada, y por eso se
    filtra con mide() antes de comparar fechas.

    Un re-muestreo conforme NO libera por si solo: deja el lote como candidato y
    la decision la firma Calidad.

    Con remuestrea=False la reprobacion no caduca nunca por muestras posteriores.
    Es lo que corresponde a la MATERIA PRIMA: ahi el codigo de lote es del
    proveedor y cubre varios pallets y hasta varias recepciones, asi que una
    muestra posterior conforme es OTRA unidad, no la misma vuelta a analizar
    (ver el comentario de MP_ESTADO).
    """
    m = mide(rows, c).sort_values("_FECHA")
    # n y n_mal son el tamano de la evidencia: "PRESENCIA" no dice lo mismo si fue
    # una muestra de una que dos de seis, y quien firma necesita saberlo.
    vacio = {"estado": "SIN DATO", "txt": "", "falla": pd.NaT, "ok": pd.NaT, "n_post": 0,
             "n": 0, "n_mal": 0}
    if m.empty:
        # medido pero no exigible: se distingue de "nadie lo midio", porque la razon
        # de la liberacion es distinta y hay que poder rastrearla
        td = con_dato(rows, c)
        if len(td):
            return {**vacio, "estado": "NO APLICA", "txt": por_que_no_aplica(td, c),
                    "n": len(td)}
        return vacio
    malo = m.apply(lambda r: _falla(r, c), axis=1)
    _n, _nm = cuenta_analisis(m, c)
    cuenta = {"n": _n, "n_mal": _nm, "n_muestras": len(m)}
    _un = UNIDAD[c]
    # lo medido y no exigido no cuenta para el veredicto, pero tampoco se calla:
    # "conforme" junto a una PRESENCIA no exigible tiene que decirlo
    ne = presencias_no_exigibles(rows) if c == "LISTERIA" else ""
    if not malo.any():
        return {**vacio, **cuenta, "estado": "CONFORME", "no_exigible": ne,
                "txt": f"{c.title()} conforme en {_n} {_un}"
                       + (f" de {len(m)} muestra(s)" if len(m) != _n else "")
                       + (f"; ademas {ne}" if ne else "")}
    ult = m[malo].iloc[-1]
    post = m[m["_FECHA"] > ult["_FECHA"]]
    de_n = (f" ({_nm} de {_n} {_un}"
            + (f" en {len(m)} muestra(s))" if _un != "muestra(s)" else ")"))
    if remuestrea and len(post) and not post.apply(lambda r: _falla(r, c), axis=1).any():
        obs = " / ".join(sorted({str(v).strip() for v in post["OBSERVACIÓN"].dropna()}))[:60]
        return {**cuenta, "estado": "REMUESTREO CONFORME",
                "txt": (f"{_texto(ult, c)} el {ult['_FECHA']:%d/%m/%Y}{de_n}, luego {len(post)} "
                        f"muestra(s) conforme(s) hasta el {post['_FECHA'].max():%d/%m/%Y}"
                        + (f" [{obs}]" if obs else "") + (f"; ademas {ne}" if ne else "")),
                "falla": ult["_FECHA"], "ok": post["_FECHA"].max(), "n_post": len(post)}
    return {**cuenta, "estado": "NO CONFORME", "txt": _texto(ult, c) + de_n,
            "falla": ult["_FECHA"], "ok": pd.NaT, "n_post": len(post)}


def _agrega(e, c, que):
    """Estado de un criterio sobre varias partes: el peor vigente manda.

    Basta UNA parte no conforme para que el conjunto lo sea. Solo si ninguna lo
    es, un re-muestreo conforme deja el conjunto como candidato.
    """
    nc = [x for x in e if x["estado"] == "NO CONFORME"]
    rc = [x for x in e if x["estado"] == "REMUESTREO CONFORME"]
    if nc:
        return {"estado": "NO CONFORME", "txt": "; ".join(sorted({x["txt"] for x in nc})),
                "unidades": [u for x in nc for u in x.get("unidades", [])]}
    if rc:
        return {"estado": "REMUESTREO CONFORME",
                "txt": "; ".join(sorted({x["txt"] for x in rc})), "unidades": []}
    if any(x["estado"] == "CONFORME" for x in e):
        n = sum(1 for x in e if x["estado"] == "CONFORME")
        # las presencias no exigibles de las partes suben con el resumen: sin esto
        # "Listeria conforme en 3 batch(es)" escondia una PRESENCIA de linea congelada
        ne = sorted({x["no_exigible"] for x in e if x.get("no_exigible")}
                    | {x["txt"] for x in e if x["estado"] == "NO APLICA"
                       and "PRESENCIA" in x.get("txt", "")})
        return {"estado": "CONFORME", "unidades": [],
                "no_exigible": "; ".join(ne),
                "txt": f"{c.title()} conforme en {n} {que}"
                       + (f"; ademas {'; '.join(ne)}" if ne else "")}
    if any(x["estado"] == "NO APLICA" for x in e):
        na = [x for x in e if x["estado"] == "NO APLICA"]
        return {"estado": "NO APLICA", "txt": "; ".join(sorted({x["txt"] for x in na})),
                "unidades": []}
    return {"estado": "SIN DATO", "txt": "", "unidades": []}


def resume(rows):
    """Estado por criterio de un conjunto de muestras: unidad, batch y lote.

    La vigencia se decide en la UNIDAD de laboratorio (_U, el lote con su sufijo
    *SSD), no en el batch. Hasta el 30/09/2026 se agrupaba por _L, que corta el
    sufijo, y cualquier conforme posterior del mismo lote base contaba como
    re-muestreo: @2VQ2629250H*37V dio listeria en 1 de 5 y lo "cubrio" *39W, que es
    otro producto de otro dia; @2VQ26292461D*37W lo cubrio *38W, de otro juliano.
    Cada unidad lleva su propio lote juliano: un conforme de otra unidad no dice
    nada de la que fallo, que es la trampa de la letra de batch otra vez. Y el
    error iba siempre hacia liberar, en todos los criterios.

    Asi que:
      - cada unidad se evalua sola con historia(): solo sus propias muestras
        posteriores conformes la llevan a REMUESTREO CONFORME;
      - el batch y el lote agregan hacia lo estricto: si una unidad queda NO
        CONFORME, el batch y el lote quedan NO CONFORME en ese criterio;
      - una muestra SIN sufijo es una unidad aparte. No se puede saber a cual de
        los dias corresponde, asi que no cierra a una unidad con sufijo, y una con
        sufijo tampoco la cierra a ella. Degrada hacia bloquear.

    El agregado contra el stock sigue siendo por lote base -Fishken no registra el
    sufijo-, pero ahora agrega veredictos de unidades, no muestras sueltas.

    Devuelve (agg por criterio, porbat {batch: {criterio: estado}}). Cada estado
    NO CONFORME trae "unidades": [(unidad, fecha de la falla, texto)].
    """
    if len(rows) == 0:
        return {c: {"estado": "SIN DATO", "txt": "", "unidades": []} for c in CRIT}, {}
    poruni, bat_de = {}, {}
    for u, g in rows.groupby("_U"):
        bat_de[u] = g["_L"].iloc[0]
        h = {}
        for c in CRIT:
            x = historia(g, c)
            if x["estado"] in ("NO CONFORME", "REMUESTREO CONFORME") and "*" in u:
                # el texto sube al lote: sin la unidad no se sabe cual dia fallo
                x = {**x, "txt": f"{x['txt']} [{u}]"}
            if x["estado"] == "NO CONFORME":
                x = {**x, "unidades": [(u, x["falla"], x["txt"])]}
            h[c] = x
        poruni[u] = h
    porbat = {}
    for b in sorted(set(bat_de.values())):
        us = [u for u in poruni if bat_de[u] == b]
        porbat[b] = {c: _agrega([poruni[u][c] for u in us], c, "unidad(es)") for c in CRIT}
    agg = {c: _agrega([porbat[b][c] for b in porbat], c, "batch(es)") for c in CRIT}
    return agg, porbat


# ------------------------------------------------- cierre de lo declarado, por unidad
# Una detencion (Postgres), una fila de detencion historica o un bloqueo heredado de
# la materia prima se cierra contra el laboratorio con la MISMA regla que decide la
# vigencia de un criterio: por unidad de laboratorio (lote con su sufijo *SSD).
#
# Hasta el 30/09/2026 se cerraban con evalua() sobre todas las muestras del lote base
# posteriores al evento: un conforme de cualquier unidad cerraba la detencion de otra,
# que es el error R1 que se corrigio ese mismo dia en el veredicto del laboratorio.
# Las detenciones de Postgres no lo mostraban solo porque su criterio no se leia
# ('{LISTERIA,RAM}'); arreglar la lectura sin esto las habria cerrado por lote base.
_ALCANCE = {}


def alcance_lab(objetivo_u):
    """Muestras del laboratorio que alcanza algo declarado sobre objetivo_u.

    Con sufijo, solo esa unidad: es la unica que la puede cerrar. Sin sufijo, todas
    las unidades del lote (y de sus batches), con o sin sufijo. Se busca en todo el
    laboratorio y no en las muestras del lote de stock, para no perder unidades
    hermanas de una detencion declarada sobre un lote padre.
    """
    if objetivo_u not in _ALCANCE:
        if "*" in objetivo_u:
            _ALCANCE[objetivo_u] = lab[lab["_U"] == objetivo_u]
        else:
            _ALCANCE[objetivo_u] = lab[lab["_L"].map(lambda x: emparenta(x, objetivo_u))]
    return _ALCANCE[objetivo_u]


def _lista(us, k=4):
    us = sorted(us)
    return ", ".join(us[:k]) + (f" y {len(us) - k} mas" if len(us) > k else "")


def cierre_por_unidad(scope, crit, evento, contexto=None, objetivo=""):
    """(se_cierra, texto) de algo declarado, contra el laboratorio y por unidad.

    scope son las muestras de las unidades que lo declarado alcanza; contexto, las
    del lote en que se esta evaluando (lo que miraba la regla anterior). Se cierra
    solo si, para CADA criterio de su motivo:
      1. hay al menos una muestra posterior al evento, del alcance, que lo mida;
      2. ninguna muestra del alcance ni del lote, del dia del evento en adelante,
         lo incumple (listeria, solo donde se exige; RAM y nitrito, en todas, como
         hacia evalua()). Es el mismo conjunto que miraba la regla anterior y algo
         mas: la regla por unidad no puede cerrar nada que antes quedaba abierto;
      3. cada unidad alcanzada que tenga resultados el mismo dia del evento o antes
         -o sin fecha- tiene su PROPIA muestra posterior que lo mide. Un conforme de
         otra unidad no la cierra;
      4. el lote que se esta evaluando (contexto) tiene muestra posterior propia que
         lo mide: una detencion sobre el lote padre no se da por cerrada para el
         batch 1 con lo que se analizo del batch W.
    "Posterior" es estrictamente despues: una muestra del dia del evento no
    acredita que se tomo despues de la desviacion. Sin criterio, sin fecha o sin
    muestras, no se cierra. Ante cualquier duda, no se cierra.

    Una listeria medida en linea congelada sin destino restringido cuenta como
    medida y no exigible, igual que en el veredicto; el texto lo dice con unidad y
    fecha, y nunca la resume como conforme.
    """
    if not crit:
        return False, ("NO LIBERABLE - sin criterio de laboratorio: el motivo no se mide "
                       "en laboratorio y solo lo cierra una decision firmada")
    if pd.isna(evento):
        return False, ("NO LIBERABLE - sin fecha del evento no se puede acreditar que una "
                       "muestra sea posterior")
    de = f" de {objetivo}" if objetivo else ""
    f = scope["_FECHA"]
    post = scope[f.notna() & (f > evento)]
    pre = scope[f.isna() | (f <= evento)]
    if not len(scope):
        return False, (f"NO LIBERABLE - el laboratorio no tiene muestras{de}: nada "
                       "acredita que se haya re-muestreado")
    mismo = int((f.notna() & (f.dt.normalize() == pd.Timestamp(evento).normalize())).sum())
    if not len(post):
        return False, (f"NO LIBERABLE - sin muestras posteriores al {evento:%d/%m/%Y}{de}"
                       + (f" ({mismo} del mismo dia, que no cuentan como posteriores)"
                          if mismo else ""))
    vigila = scope if contexto is None else pd.concat([scope, contexto])
    vigila = vigila[~vigila.index.duplicated()]
    vigila = vigila[vigila["_FECHA"].notna() & (vigila["_FECHA"] >= evento)]
    u_pre = set(pre["_U"])
    malos, faltan, sin_propia, partes = [], [], [], []
    for c in crit:
        base = mide(vigila, c) if c == "LISTERIA" else con_dato(vigila, c)
        mal = base[base.apply(lambda r: _falla(r, c), axis=1)] if len(base) else base
        for _, x in mal.sort_values("_FECHA").iterrows():
            malos.append(f"{_texto(x, c)} en {x['_U']} del {x['_FECHA']:%d/%m/%Y}")
        medido = con_dato(post, c)
        if not len(medido):
            faltan.append(c)
            continue
        if contexto is not None:
            _fc = contexto["_FECHA"]
            if not len(con_dato(contexto[_fc.notna() & (_fc > evento)], c)):
                faltan.append(f"{c} en el propio lote")
                continue
        sp = sorted(u_pre - set(medido["_U"]))
        if sp:
            sin_propia.append(f"{c}: {_lista(sp)}")
        m = mide(post, c)
        ne = presencias_no_exigibles(post) if c == "LISTERIA" else ""
        if len(m):
            n, _ = cuenta_analisis(m, c)
            p = f"{c} conforme en {n} {UNIDAD[c]} de {m['_U'].nunique()} unidad(es)"
        else:
            p = f"{c} medida pero no exigible (linea congelada sin EE.UU. ni Costa Rica)"
        partes.append(p + (f"; {ne}" if ne else ""))
    if malos:
        return False, (f"NO LIBERABLE - resultado no conforme desde el {evento:%d/%m/%Y} ("
                       + "; ".join(dict.fromkeys(malos)) + ")")
    if faltan:
        return False, (f"NO LIBERABLE - las {len(post)} muestra(s) posterior(es) al "
                       f"{evento:%d/%m/%Y}{de} no midieron {', '.join(faltan)}")
    if sin_propia:
        return False, ("NO LIBERABLE - hay unidades con resultados al "
                       f"{evento:%d/%m/%Y} o antes sin muestra posterior propia que mida "
                       "el criterio (" + "; ".join(sin_propia) + "): un conforme de otra "
                       "unidad no las cierra")
    return True, (f"LIBERABLE segun lab - {len(post)} muestra(s) posterior(es) al "
                  f"{evento:%d/%m/%Y} en {post['_U'].nunique()} unidad(es)"
                  + (f", incluida muestra propia de cada una de las {len(u_pre)} unidad(es) "
                     "con resultados previos" if u_pre else "")
                  + ": " + " | ".join(partes))


# ------------------------------------------------- estado de cada materia prima
# Aca la regla de vigencia NO es la del producto terminado, y confundirlas liberaba
# producto con evidencia que no existe.
#
# En el producto terminado el flujo es fallar, tratar y re-muestrear LA MISMA cosa,
# asi que una muestra posterior conforme dice algo del lote que fallo. En la materia
# prima no: el codigo es el LOTE DEL PROVEEDOR, y cubre varios pallets y hasta varias
# recepciones distintas. Una muestra posterior conforme con el mismo codigo es OTRA
# unidad, no la misma vuelta a analizar. Y una materia prima desviada por listeria no
# se re-muestrea nunca: se descarta o se decide sobre ella.
#
# Los cuatro casos que el motor leia como re-muestreo lo dejan a la vista:
#   26060014  P el 12/06 y A el 15/06, pero el PRO-REG-46 trae dos recepciones con
#             ese lote -pallets 2532/2533/2536 el 11/06 y 2590/2592/2595 el 15/06-
#             con distinta fecha de elaboracion del proveedor
#   26050004  las dos muestras son del MISMO dia, codigos 1292 (P) y 1293 (A)
#   25100013  P el 16/10 y dos filas A el 20/10, que es la fecha de entrada a
#             produccion de los pallets 819 y 820 de esa misma recepcion
# Es la trampa de la letra de batch otra vez: un conforme de otra unidad no cubre
# el incumplimiento de la que fallo. Lo unico que cierra un bloqueo de materia prima
# es el resultado propio del producto elaborado, o una decision firmada.
CRIT_MP = ("LISTERIA", "RAM")
MP_ESTADO = {}
for _l, _g in mp.groupby("_L"):
    MP_ESTADO[_l] = {c: historia(_g, c, remuestrea=False) for c in CRIT_MP}
_mp_nc = [k for k, v in MP_ESTADO.items()
          if any(x["estado"] == "NO CONFORME" for x in v.values())]
# se sigue contando lo que ANTES se leia como re-muestreo, para que el hallazgo no
# desaparezca en silencio si manana el registro cambia de convencion
_mp_rem = [k for k, _g in mp.groupby("_L")
           if any(historia(_g, c)["estado"] == "REMUESTREO CONFORME" for c in CRIT_MP)]
if len(mp):
    _sin46 = [k for k in MP_ESTADO if k not in PROV_46]
    print(f"  materias primas: {len(mp)} muestras sobre {len(MP_ESTADO)} lotes; "
          f"{len(_mp_nc)} no conformes")
    if _mp_rem:
        print(f"  {len(_mp_rem)} lote(s) de MP tienen una muestra posterior conforme con el "
              "mismo codigo: NO es un re-muestreo, es otro pallet u otra recepcion, y no "
              "levanta el incumplimiento (" + ", ".join(sorted(_mp_rem)[:6]) + ")")
    print(f"  de los {len(MP_ESTADO)} lotes de MP del laboratorio, {len(_sin46)} no figuran "
          "en el PRO-REG-46: su bloqueo no se puede arrastrar a ningun producto")
    _prov_sin = (mp[mp["_L"].isin(_sin46)]["PROVEEDOR"].astype(str).str.strip()
                 .str.upper().value_counts().head(6))
    if len(_prov_sin):
        print("     " + ", ".join(f"{k}={v}" for k, v in _prov_sin.items()))


def aplica_listeria(clave, rows_lab):
    """Si el criterio de listeria aplica a este lote, con la misma regla de siempre.

    Refrigerada siempre; congelada solo con destino EE.UU. o Costa Rica. Manda la
    clasificacion del laboratorio y, si el lote no tiene muestras propias, la
    condicion de bodega. Sin poder determinar linea ni destino, aplica: no se
    exime un criterio por falta de informacion.
    """
    if len(rows_lab):
        return bool(rows_lab["_LIS_APLICA"].any())
    d = destino_restringido(clave)
    return linea_stock(clave) != "CONGELADA" or d is None or d != ""


def cuantos(rows, c):
    """'2 de 5 analisis' de un criterio, o el motivo por el que no hay numero.

    Un veredicto sin el tamano de la evidencia no sirve para firmar: 'PRESENCIA'
    no dice lo mismo si fue una muestra de una que dos de seis.
    """
    if not len(rows):
        return "sin analisis"
    n, mal = cuenta_analisis(mide(rows, c), c)
    return f"{mal} de {n} {UNIDAD[c]}" if n else "sin analisis"


def materia_prima(clave, rows_lab, aplica_lis=True):
    """Materias primas no conformes con las que se elaboro este lote.

    Devuelve (motivos, propuestas, n_bloquean, n_candidatas, fecha_falla, criterios).

    Una sola cosa deja el lote en CANDIDATO A LIBERAR aca: que el criterio que fallo
    haya sido listeria y al producto elaborado no le aplique, por ser linea congelada
    sin destino EE.UU. ni Costa Rica.

    El otro caso -que el producto terminado tenga resultado propio conforme
    posterior- se resuelve fuera, porque necesita las muestras del producto. Y ese
    es el unico camino real: la materia prima no se vuelve a analizar, asi que su
    incumplimiento no caduca solo (ver MP_ESTADO).
    """
    if not MP_DE_SW:
        return [], [], 0, 0, pd.NaT, set()
    mps = set()
    for sw, ps in MP_DE_SW.items():
        if emparenta(sw, clave):
            mps |= ps
    motivos, propuestas, nb, nc, falla, crit = [], [], 0, 0, pd.NaT, set()
    for p in sorted(mps):
        est = MP_ESTADO.get(p)
        if not est:
            continue
        prov = PROV_46.get(p, "")
        malos = [c for c in CRIT_MP if est[c]["estado"] == "NO CONFORME"]
        etq = f"MP {p}" + (f" ({prov})" if prov else "")
        exime = [c for c in malos if c == "LISTERIA" and not aplica_lis]
        malos = [c for c in malos if c not in exime]
        if malos:
            nb += 1
            crit |= set(malos)
            motivos.append(f"{etq}: " + "; ".join(est[c]["txt"] for c in malos))
            # el numero de los dos lados: lo que fallo en la materia prima y como
            # salio despues el producto que se hizo con ella. Es lo que permite
            # decidir, y sin eso la pantalla solo repite que sigue bloqueado
            comp = "; ".join(
                f"{c.title()} - materia prima: {est[c]['n_mal']} de {est[c]['n']} "
                f"{UNIDAD[c]}; producto terminado: {cuantos(rows_lab, c)}" for c in malos)
            # decir "sin re-muestreo conforme posterior" mandaba a esperar una muestra
            # que no va a llegar nunca: la materia prima desviada no se vuelve a
            # analizar. Lo que corresponde es decir con que SI se cierra.
            propuestas.append(
                f"{etq}: NO LIBERABLE - la materia prima entro con "
                f"{', '.join(malos)}. La materia prima no se vuelve a analizar, asi que "
                "esto lo cierra el resultado propio del producto elaborado en ese mismo "
                f"criterio, o una decision firmada. {comp}")
            for c in malos:
                if pd.notna(est[c]["falla"]) and (pd.isna(falla) or est[c]["falla"] > falla):
                    falla = est[c]["falla"]
        elif exime:
            nc += 1
            motivos.append(f"{etq}: " + "; ".join(est[c]["txt"] for c in exime)
                           + " (no aplica a este producto)")
            propuestas.append(f"{etq}: LIBERABLE - la materia prima traia listeria, pero "
                              "el producto es de linea congelada sin destino EE.UU. ni "
                              "Costa Rica, donde el criterio no se exige. Requiere firma "
                              "de Calidad.")
    return motivos, propuestas, nb, nc, falla, crit


# ----------------------------------------------------------------- universo de lotes
lotes_stock = sorted(stock["_L"].unique())
lotes_det = sorted(det.loc[det["_VIGENTE"], "_L"].unique())

# una detencion puede apuntar a un lote que aun no llega a bodega (lag de informacion)
huerfanos = [d for d in lotes_det if not any(emparenta(d, s) for s in lotes_stock)]

# Lo mismo por el lado del laboratorio: un lote puede tener resultado NO CONFORME y todavia
# no figurar en ningun stock (produccion reciente, o ya despachada). Si no se incorpora al
# universo queda invisible, que es el peor error posible en un control de bloqueos.
lab_solo = []
for _l, _g in lab.groupby("_L"):
    if not es_lote(_l):
        continue
    if any(emparenta(_l, s) for s in lotes_stock) or any(emparenta(_l, d) for d in lotes_det):
        continue
    _a, _ = resume(_g)
    if any(_a[c]["estado"] == "NO CONFORME" for c in CRIT):
        lab_solo.append(_l)

# Y lo mismo con las detenciones historicas: un lote bloqueado por correo o por SAP puede
# haberse despachado, o estar en una bodega que no bajamos. Si queda fuera del universo,
# consultarlo devuelve "no reconocido", que es exactamente el error que ya cometimos una
# vez con los lotes reprobados sin stock.
lotes_ope = sorted(ope["_L"].unique()) if len(ope) else []
ope_solo = [o for o in lotes_ope
            if not any(emparenta(o, s) for s in lotes_stock)
            and not any(emparenta(o, d) for d in lotes_det)
            and not any(emparenta(o, x) for x in lab_solo)]

universo = lotes_stock + huerfanos + lab_solo + ope_solo
print(f"\nUniverso: {len(lotes_stock)} lotes en stock + {len(huerfanos)} solo con detencion "
      f"+ {len(lab_solo)} solo en laboratorio y no conformes "
      f"+ {len(ope_solo)} solo en detenciones historicas")

# Posibles typos de @ / B: calzarian si se ignorara el prefijo.
# No se marca cuando ambas variantes tienen respaldo propio en lab o en el registro:
# ahi la diferencia de prefijo es deliberada (2AS2621170M vs B2AS2621170M son lotes reales
# y distintos, listados por separado en el correo del 09/07/2026).
conocidos = set(lab["_L"]) | set(det["_L"])


def respaldado(x):
    return any(emparenta(k, x) for k in conocidos)


casi = {}
for d in huerfanos:
    cand = [s for s in lotes_stock
            if emparenta(laxo(d), laxo(s)) and not (respaldado(d) and respaldado(s))]
    if cand:
        casi[d] = cand

# Convenciones de prefijo: @ = ASC, B = BAP. Configuran lotes distintos y se respetan.
# Un par @X / BX es legitimo (mismo correlativo, dos certificaciones). Un par X / @X o
# X / BX no deberia existir: a uno de los dos le falta el prefijo.
def bare(x):
    return re.sub(r"^[@B]", "", x)


_grp = {}
for s in lotes_stock:
    _grp.setdefault(bare(s), []).append(s)
gemelos, sospecha_pfx = {}, {}
for _b, g in _grp.items():
    if len(g) < 2:
        continue
    destino = sospecha_pfx if any(x[0] not in "@B" for x in g) else gemelos
    for x in g:
        destino[x] = [y for y in g if y != x]

# Confusion de caracteres dentro del codigo (letra O contra cero, I contra uno).
_conf = {}
for s in lotes_stock:
    _conf.setdefault(s.replace("O", "0").replace("I", "1"), []).append(s)
confusion = {x: [y for y in g if y != x] for g in _conf.values() if len(g) > 1 for x in g}

# Codigos de lote que no parecen codigos: placeholders, pruebas, texto libre.
def sospechoso(txt):
    t = str(txt).strip()
    return bool(re.search(r"\s", t) or re.search(r"PRUEBA|TEST", t, re.I) or not re.search(r"\d", t))

def veredicto_ope(crit, f, scope, contexto=None, objetivo=""):
    """(libera, texto) de un bloqueo declarado, evaluado contra el lab posterior.

    scope son las muestras de las unidades que el bloqueo alcanza (alcance_lab de
    sus trazas): con sufijo, solo esa unidad. Se cierra por unidad, con
    cierre_por_unidad(): hasta el 30/09/2026 bastaba un conforme posterior de
    cualquier unidad del lote base.

    Devuelve el veredicto sin el encabezado ni la aclaracion del motivo, para que
    quien lo llama los agregue una sola vez y no haya que repetirlos en cada rama.
    """
    if not crit:
        return False, ("NO LIBERABLE - el motivo no se mide en laboratorio; solo lo "
                       "cierra una decision firmada")
    inf = f"criterio {', '.join(crit)} inferido del motivo declarado"
    if pd.notna(f) and f > HOY:
        # una fecha de bloqueo en el futuro (tipeo de anio) deja el lote bloqueado
        # para siempre en silencio: ninguna muestra puede ser posterior
        return False, (f"NO LIBERABLE - la fecha de bloqueo ({f:%d/%m/%Y}) es futura, "
                       "probable error de tipeo en el registro: ninguna muestra puede ser "
                       "posterior. Corregir la fecha en " + config.ARCH_OPERATIVO)
    if pd.isna(f):
        return False, ("NO LIBERABLE - sin fecha de bloqueo no se puede acreditar que una "
                       f"muestra sea posterior ({inf})")
    libera, txt = cierre_por_unidad(scope, crit, f, contexto, objetivo)
    return libera, f"{txt} ({inf})" + (". Requiere firma de Calidad." if libera else "")


filas = []
for l in universo:
    en_stock = l in lotes_stock
    s = stock[stock["_L"] == l] if en_stock else stock.iloc[0:0]
    rows_lab = lab[lab["_L"].map(lambda x: emparenta(x, l))]
    dets = det[det["_L"].map(lambda x: emparenta(x, l))]
    dets_v = dets[dets["_VIGENTE"]]

    # ---- batches de ahumado: la letra final del lote es parte del codigo y configura
    # lote distinto. El lab y los correos trabajan a ese nivel; el stock solo registra el
    # lote base, asi que un lote de stock agrupa varios batches que no se pueden separar.
    agg, porbat = resume(rows_lab)
    batches = {b: [porbat[b][c]["txt"] for c in CRIT
                   if porbat[b][c]["estado"] == "NO CONFORME"] for b in porbat}
    malos_bat = {b: v for b, v in batches.items() if v}
    cand_bat = {b: [porbat[b][c]["txt"] for c in CRIT
                    if porbat[b][c]["estado"] == "REMUESTREO CONFORME"]
                for b in porbat if not batches[b]}
    cand_bat = {b: v for b, v in cand_bat.items() if v}

    causas = [c for c in CRIT if agg[c]["estado"] == "NO CONFORME"]
    causas_rem = [c for c in CRIT if agg[c]["estado"] == "REMUESTREO CONFORME"]
    motivos_lab = [agg[c]["txt"] for c in causas]
    motivos_rem = [agg[c]["txt"] for c in causas_rem]
    # Cada unidad que sigue no conforme, con su criterio y la fecha de la falla. Es lo
    # que el dialogo de firma muestra en rojo antes de firmar: si una unidad del lote
    # no tiene re-muestreo propio, quien firma tiene que verlo con nombre y fecha,
    # no enterrado en el texto del motivo.
    unidades_nc = [{"unidad": u, "criterio": c,
                    "fecha": f"{f:%Y-%m-%d}" if pd.notna(f) else None,
                    "detalle": t}
                   for c in CRIT for u, f, t in agg[c].get("unidades", [])]
    r, _ = evalua(rows_lab)   # solo para los valores que se muestran en columnas

    # Trazabilidad de la liberacion: por que quedo liberado, criterio por criterio.
    por_crit = "; ".join(f"{c}={agg[c]['estado']}" for c in CRIT)
    _con = mide(rows_lab, "LISTERIA")
    _mu = rows_lab[rows_lab["_LM_DATO"] | rows_lab["_RAM"].notna()
                  | rows_lab["_RAM_TECHO"] | rows_lab["_NIT"].notna()]
    evidencia = ", ".join(
        f"lab {cod_lab(x['CÓDIGO LAB'])} del {x['_FECHA']:%d/%m/%Y}"
        for _, x in _mu.sort_values("_FECHA").tail(4).iterrows()
        if pd.notna(x.get("CÓDIGO LAB")) and pd.notna(x["_FECHA"]))
    motivo_lib = [agg[c]["txt"] for c in CRIT
                  if agg[c]["estado"] in ("CONFORME", "NO APLICA") and agg[c]["txt"]]

    # ---- detenciones vigentes y su evaluabilidad
    motivos_det, propuestas = [], []
    hay_pnc = (dets_v["_ESTADO"] == "PNC").any()
    for _, d in dets_v.iterrows():
        etq = f"{d['ID']} {d['TIPO DE DESVIACION']}"
        if d["_ESTADO"] == "PNC":
            motivos_det.append(f"{etq} (PNC)")
            propuestas.append(f"{d['ID']}: PNC - no se libera contra laboratorio")
            continue
        motivos_det.append(etq)
        # El criterio se lee con lee_criterios(): de Postgres llega '{LISTERIA,RAM}'.
        # Un criterio que no se reconoce deja la detencion vigente, sin propuesta de
        # cierre. Y el cierre es por unidad: la detencion alcanza a las unidades de
        # su lote (con sufijo, solo a esa), y cada una con resultados previos al
        # evento necesita su propia muestra posterior conforme.
        if d["_CRIT_RARO"]:
            propuestas.append(f"{d['ID']}: NO LIBERABLE - criterio de liberacion no "
                              f"reconocido ({', '.join(d['_CRIT_RARO'])}): no se puede "
                              "acreditar que el laboratorio lo midio")
            continue
        libera, txt = cierre_por_unidad(alcance_lab(d["_U"]), d["_CRIT"], d["_EVENTO"],
                                        rows_lab, d["_U"])
        propuestas.append(f"{d['ID']}: {txt}"
                          + (". Requiere firma de Calidad." if libera else ""))

    # ---- bloqueos declarados en el Excel historico
    # Mismo tratamiento que una detencion: bloquea por SU motivo, y solo lo levanta
    # una muestra posterior al bloqueo que vuelva a medir ESE criterio y salga
    # conforme. La diferencia es que alla el criterio lo declara una persona y aca
    # se infiere del texto, asi que la propuesta lo deja dicho.
    opes = ope[ope["_L"].map(lambda x: emparenta(x, l))] if len(ope) else ope
    motivos_ope, propuestas_ope, ope_pend, ope_ok = [], [], 0, 0
    if len(opes):
        # el registro repite la misma fila por articulo, no por lote: se agrupa por
        # el criterio en juego para no repetir veinte veces el mismo veredicto
        for k, g in opes.assign(_K=opes["_CRIT"].map(",".join)).groupby("_K"):
            crit = [c for c in k.split(",") if c]
            f = g["FECHA"].max()
            txts = sorted({str(m).strip() for m in g["MOTIVO"] if str(m).strip()})
            etq = " / ".join(txts[:2])[:90] or "sin motivo escrito"
            motivos_ope.append(f"{etq} ({len(g)} registro(s)"
                               + (f", ultimo {f:%d/%m/%Y}" if pd.notna(f) else ", sin fecha") + ")")
            # Cada traza del grupo se cierra por separado, con las unidades que ella
            # alcanza (con sufijo, solo esa), y tienen que cerrarse todas: juntarlas
            # dejaba que el batch W, alcanzado por la traza del lote padre, cerrara la
            # traza del batch 1. Si todas cierran, el texto es el del conjunto.
            _tr = sorted(set(g["_U"]))
            libera, txt = True, ""
            for _t in _tr:
                libera, txt = veredicto_ope(crit, f, alcance_lab(_t), rows_lab, _t)
                if not libera:
                    break
            if libera and len(_tr) > 1:
                _sc = pd.concat([alcance_lab(t) for t in _tr])
                _sc = _sc[~_sc.index.duplicated()]
                libera, txt = veredicto_ope(crit, f, _sc, rows_lab, _lista(_tr, 3))
            # el motivo escrito puede leerse al reves de lo que significa -"vida util
            # transcurrida" no es producto vencido-, asi que la aclaracion viaja con
            # el veredicto y no en un pie de pagina que nadie lee
            nota = " ".join(dict.fromkeys(
                n for n in (config.nota_del_motivo(t) for t in txts) if n))
            if libera:
                ope_ok += 1
            else:
                ope_pend += 1
            propuestas_ope.append(f"Detencion historica [{etq}]: {txt}"
                                  + (f" {nota}." if nota else ""))
    propuestas += propuestas_ope

    # ---- materia prima: lo que estaba bloqueado antes de entrar a proceso
    motivos_mp, propuestas_mp, mp_pend, mp_cand, mp_falla, mp_crit = materia_prima(
        l, rows_lab, aplica_listeria(l, rows_lab))
    # El proceso -ahumado, altas presiones- es justamente lo que controla lo que
    # traia la materia prima. Si el producto ya se analizo despues y salio conforme
    # en TODO lo que la materia prima traia mal, el lote esta listo para liberarse
    # y lo unico que falta es la firma: candidato, no bloqueado.
    # Por unidad, como todo lo que se cierra con muestras posteriores: cada unidad del
    # lote con resultados al dia de la falla de la materia prima o antes necesita su
    # propia muestra posterior conforme; un conforme de otra unidad no la cubre.
    if mp_pend and pd.notna(mp_falla) and len(rows_lab):
        _post = rows_lab[rows_lab["_FECHA"] > mp_falla]
        if len(_post):
            _cie = {c: cierre_por_unidad(rows_lab, [c], mp_falla, rows_lab) for c in sorted(mp_crit)}
            _ok = {c for c, (ok, _t) in _cie.items() if ok}
            if mp_crit and mp_crit <= _ok:
                mp_cand += mp_pend
                mp_pend = 0
                # el tamano de la evidencia por criterio, y lo medido y no exigido
                # dicho como tal: "conforme" a secas escondia una PRESENCIA
                _det = " | ".join(_t.split(": ", 1)[-1] for c, (_o, _t) in _cie.items())
                propuestas.append(
                    f"Materia prima: el producto terminado tiene {len(_post)} muestra(s) "
                    f"posterior(es) al {mp_falla:%d/%m/%Y}, con muestra propia de cada "
                    f"unidad con resultados previos ({_det}), y es lo que la materia prima "
                    "traia mal. Queda listo para liberar, pero no se libera solo: la firma "
                    "es de Calidad.")
            else:
                # se dice por que no cubre: no es lo mismo que nadie lo haya medido, que
                # haya salido mal otra vez o que falte la muestra propia de una unidad
                _falta = sorted(mp_crit - _ok)
                propuestas.append(
                    "Materia prima: "
                    + (f"el producto terminado cubre {', '.join(sorted(_ok))}, pero no "
                       if _ok else "el producto terminado no cubre ")
                    + f"{', '.join(_falta)}, que es lo que fallo en la materia prima: "
                    + "; ".join(f"{c} {_cie[c][1].replace('NO LIBERABLE - ', '')}"
                                for c in _falta) + ". Sigue bloqueado.")
    if not mp_pend:
        # ya no bloquea: el "NO LIBERABLE" describiria el estado de la materia prima,
        # pero se lee como el veredicto del lote y lo contradice
        propuestas_mp = [p.replace("NO LIBERABLE - la materia prima entro con",
                                   "La materia prima entro con") for p in propuestas_mp]
    propuestas += propuestas_mp

    # ---- estado consolidado
    # Los origenes se acumulan y cada uno tiene que cerrarse por su cuenta.
    bloquean = [nombre for nombre, hay in (("LAB", motivos_lab), ("DETENCION", motivos_det),
                                           ("DETENCION HISTORICA", ope_pend),
                                           ("MATERIA PRIMA", mp_pend)) if hay]
    if hay_pnc:
        estado, origen = "PNC", "DETENCION"
    elif bloquean:
        estado, origen = "BLOQUEADO", " + ".join(bloquean)
    elif motivos_rem or ope_ok or mp_cand:
        # fallo y se re-muestreo conforme cubriendo el criterio: no se libera solo
        estado = "CANDIDATO A LIBERAR"
        origen = " + ".join((["LAB"] if motivos_rem else [])
                            + (["DETENCION HISTORICA"] if ope_ok else [])
                            + (["MATERIA PRIMA"] if mp_cand else []))
    elif len(rows_lab) == 0 or all(agg[c]["estado"] == "SIN DATO" for c in CRIT):
        estado, origen = "SIN ANALISIS", ""
    else:
        estado, origen = "LIBERADO", ""

    # ---- una liberacion firmada manda sobre el veredicto calculado
    # las causas vivas dicen si el tratamiento firmado alcanza: un APH no
    # arregla un nitrito bajo, por mucho que el lote haya ido en ese despacho
    _vivas = set(causas) | ({"LISTERIA"} if mp_pend else set())
    dfirm, aviso_firma = firmada(l, rows_lab, _vivas)
    obs = []
    if aviso_firma:
        obs.append(aviso_firma)
    if dfirm is not None and estado in ("BLOQUEADO", "CANDIDATO A LIBERAR"):
        estado = "LIBERADO POR DECISION"
        origen = "DECISION FIRMADA"
        obs.append(f"Liberado por {dfirm['ID']} el {dfirm['_FECHA']:%d/%m/%Y}, firmado por "
                   f"{dfirm.get('FIRMADO POR', 'sin registrar')}"
                   + (f" para {dfirm['MERCADOS']}" if pd.notna(dfirm.get("MERCADOS")) else "")
                   + (f". Evidencia: {dfirm['EVIDENCIA']}" if pd.notna(dfirm.get("EVIDENCIA")) else ""))
    # ---- cajas de distinto destino en el mismo lote
    # Quien va a firmar necesita saberlo ANTES: firmar solo Nacional sobre un lote
    # con cajas a EE.UU. no libera nada, y hoy eso se descubria despues de firmar.
    _rep, _, _tot = reparto_destino(l)
    _mix = len(_CAJAS_DEST.get(l) or {}) > 1
    if _mix and estado in ("BLOQUEADO", "CANDIDATO A LIBERAR"):
        # solo la listeria depende del destino. Si lo que bloquea es RAM o nitrito, el
        # reparto no ayuda: esos criterios se exigen en todos los mercados, y decir lo
        # contrario mandaria a firmar una liberacion que no corresponde
        _libres = (_CAJAS_DEST.get(l) or {}).get("", 0)
        obs.append(
            f"Cajas de distinto destino en el mismo lote: {_rep}. El estado se resuelve "
            "hacia lo mas estricto, asi que una firma por mercado no libera el lote"
            + (f". La listeria no se exige en los destinos sin restriccion: una firma "
               f"acotada a ellos cubriria {_libres} de {_tot} caja(s), y separarlas es "
               "posible porque el cliente esta registrado caja por caja"
               if "LISTERIA" in _vivas and _libres else ""))
    if not en_stock and len(dets):
        obs.append("Lote con detencion vigente que NO aparece en ningun stock: "
                   "puede ser lag de informacion, producto aun en proceso, ya despachado, "
                   "bodega no incluida, o lote mal escrito. Requiere revision.")
    elif not en_stock and len(opes) and not len(rows_lab):
        obs.append("Lote bloqueado en el Excel de detenciones historicas que no aparece en ningun stock "
                   "ni tiene resultados de laboratorio: probablemente ya despachado o de una "
                   "bodega que no se baja. Figura para que consultarlo no devuelva "
                   "'no reconocido'.")
    elif not en_stock:
        obs.append("Lote con resultado NO CONFORME que no aparece en ningun stock: "
                   "produccion reciente aun no ingresada a bodega, ya despachada, o bodega no "
                   "incluida. Verificar antes de despachar.")
    if l in casi:
        obs.append("Posible error de tipeo en prefijo @/B: se parece a " + ", ".join(casi[l]))
    if l in sospecha_pfx:
        obs.append("SOSPECHA DE TIPEO: convive en stock con " + ", ".join(sospecha_pfx[l]) +
                   ". @ (ASC) y B (BAP) configuran lotes distintos, pero un lote sin prefijo "
                   "junto a su gemelo prefijado no deberia existir: a uno le falta el prefijo")
    if l in gemelos:
        obs.append("Convive en stock con " + ", ".join(gemelos[l]) +
                   " (ASC vs BAP): son lotes distintos, sin accion")
    if l in confusion:
        obs.append("Se confunde con " + ", ".join(confusion[l]) + " por letra O contra cero")
    # manda la clasificacion de la muestra: el laboratorio nombra la linea, la
    # condicion de bodega solo dice como esta guardado hoy
    _lm = sorted({x for x in rows_lab["_LINEA"] if x})
    _ls = linea_stock(l)
    linea_l = " / ".join(_lm) if _lm else (_ls or "sin clasificar")
    if _lm and _ls and _ls not in _lm:
        obs.append(f"El laboratorio clasifica este lote como {' / '.join(_lm)} y en bodega "
                   f"figura como {_ls}: manda el laboratorio para aplicar el nitrito")
    if rows_lab["_BW"].any() and (rows_lab["_LINEA"] == "CONGELADA").any():
        obs.append("Bacon/wheel: figura congelado pero se vende refrigerado en destino, "
                   "asi que el nitrito se evalua igual que en linea refrigerada")
    ign = (rows_lab[~rows_lab["_NIT_APLICA"] & rows_lab.apply(
        lambda x: binomio(x["_NIT"], x["_WPS"])[0], axis=1)] if len(rows_lab) else rows_lab)
    if len(ign):
        obs.append("Binomio WPS/nitrito NO aplicado por ser linea congelada: "
                   + binomio(ign["_NIT"].iloc[0], ign["_WPS"].iloc[0])[1])
    lis_ex = rows_lab[rows_lab["_LM_P"] & ~rows_lab["_LIS_APLICA"]]
    if len(lis_ex):
        obs.append("Listeria PRESENCIA NO aplicada: linea congelada sin destino EE.UU. "
                   "ni Costa Rica (cliente " + " / ".join(sorted(set(
                       s["CLIENTE"].dropna().astype(str)))[:2] or ["sin dato"]) + ")")
    # ---- el bloqueo depende SOLO del destino?
    # La listeria es el unico criterio que el destino puede eximir: en linea congelada
    # se exige por ir a EE.UU. o Costa Rica, y no en otros mercados. Si eso es lo unico
    # vivo, un despacho a un destino sin restriccion no arrastra este bloqueo, y la
    # consulta de packing list puede decirlo sin volver a derivar criterios.
    #
    # Se exige TODO esto, y cada condicion evita un falso positivo:
    #   - nada declarado vivo: una detencion o un bloqueo del registro no caduca por
    #     destino, lo cierra su propio motivo
    #   - lo unico vivo es listeria, del laboratorio o heredado de la materia prima
    #   - la linea no es refrigerada: ahi la listeria se exige en todos los mercados
    #   - el lote esta marcado por destino restringido, que es lo que se estaria eximiendo
    _vivo_lis = set(causas) | (mp_crit if mp_pend else set())
    solo_destino = bool(
        estado in ("BLOQUEADO", "CANDIDATO A LIBERAR")
        and not motivos_det and not ope_pend
        and _vivo_lis and _vivo_lis <= {"LISTERIA"}
        and "REFRIGERADA" not in linea_l
        and destino_restringido(l) in ("EE.UU.", "Costa Rica"))
    if solo_destino:
        obs.append("Bloqueo dependiente del destino: lo unico vigente es listeria y la "
                   f"linea es {linea_l}, donde solo se exige por el destino "
                   f"{destino_restringido(l)}. Un despacho a un mercado sin esa "
                   "restriccion no arrastra este bloqueo, pero eso lo firma Calidad: el "
                   "sistema no lo libera solo")
    lib_f, lib_m, lib_o = liberacion(l)
    if lib_f and (motivos_lab or motivos_det):
        obs.append(f"CONFLICTO: figura liberado el {lib_f}"
                   + (f" para {lib_m}" if lib_m else "")
                   + f" en {lib_o}, pero el laboratorio mantiene un incumplimiento vigente")
    elif lib_f and motivos_rem:
        obs.append(f"Ya figura liberado el {lib_f}" + (f" para {lib_m}" if lib_m else "")
                   + f" en {lib_o}: el re-muestreo conforme respalda esa decision")
    if cand_bat:
        obs.append(f"Re-muestreo conforme posterior en {len(cand_bat)} batch(es): "
                   + " | ".join(t for v in cand_bat.values() for t in v)
                   + ". Requiere decision firmada de Calidad, el sistema no libera solo")
    if malos_bat and len(malos_bat) < len(batches):
        obs.append(f"Bloqueo originado en {len(malos_bat)} de {len(batches)} batches de ahumado "
                   "con resultado. El stock no registra la letra de batch, asi que las cajas de "
                   "los batches conformes no se pueden separar y quedan bloqueadas con el lote")
    if en_stock:
        etiqueta = s["LOTE DE PLANTA"].iloc[0]
    elif len(dets):
        etiqueta = dets["LOTE"].iloc[0]
    elif not len(rows_lab) and len(opes):
        etiqueta = opes["LOTE"].iloc[0]
    else:
        # rows_lab trae tambien muestras emparentadas del lote padre: si se toma
        # la primera al azar, la etiqueta puede ser la de OTRO lote. Se prefiere
        # la muestra cuyo codigo normalizado es exactamente este.
        _ex = rows_lab[rows_lab["_L"] == l]
        _f = _ex if len(_ex) else rows_lab
        etiqueta = str(_f["LOTE SW"].iloc[0]).strip().split("*")[0] if len(_f) else l
    if sospechoso(etiqueta):
        obs.append("El codigo de lote no parece un lote real (placeholder o texto libre): "
                   "revisar el origen en Fishken, agrupa cajas que no comparten lote")
    if len(rows_lab) == 0 and en_stock:
        obs.append("Sin resultados en LAB-REG-08 2026")
    else:
        faltan = [c for c in ("LISTERIA", "RAM") if agg[c]["estado"] == "SIN DATO"]
        if faltan:
            obs.append("Sin analisis de " + " y ".join(faltan))
    if r["ar"] == "R" and not any("Nitrito" in m for m in motivos_lab):
        obs.append("Lab marco nitrito RECHAZADO (criterio propio del producto)")
    tipos = set(rows_lab["TIPO "].dropna().astype(str).str.strip())
    if tipos - {"PT"}:
        obs.append("Incluye muestras tipo " + "/".join(sorted(tipos)))
    if (dets_v["ALCANCE"].astype(str).str.startswith("PARCIAL")).any():
        obs.append("Detencion de alcance PARCIAL: sin identificar cajas se marca el lote completo")

    filas.append({
        "LOTE": etiqueta,
        "LOTE (normalizado)": l,
        "ESTADO": estado,
        "ORIGEN DEL BLOQUEO": origen,
        "MOTIVO DE LA LIBERACION": (
            (f"Decision firmada {dfirm['ID']}: {dfirm.get('COMENTARIO', '')}"
             if dfirm is not None and estado == "LIBERADO POR DECISION"
             else " | ".join(motivo_lib))
            if estado in ("LIBERADO", "CANDIDATO A LIBERAR", "LIBERADO POR DECISION") else ""),
        "FIRMADA POR": (str(dfirm.get("FIRMADO POR", "")) if dfirm is not None
                        and estado == "LIBERADO POR DECISION" else ""),
        "MERCADOS FIRMADOS": (str(dfirm.get("MERCADOS", "") or "") if dfirm is not None
                              and estado == "LIBERADO POR DECISION" else ""),
        "TRATAMIENTO": (str(dfirm.get("TRATAMIENTO", "") or "") if dfirm is not None
                        and estado == "LIBERADO POR DECISION" else ""),
        "ESTADO POR CRITERIO": por_crit,
        "EVIDENCIA (ultimas muestras)": evidencia,
        "LINEA": linea_l,
        "DESTINO RESTRINGIDO": (lambda d: d if d else
                                ("sin determinar" if d is None else "no"))(destino_restringido(l)),
        # el reparto caja por caja, que es lo que permite firmar por mercado
        "CAJAS POR DESTINO": _rep,
        "BLOQUEO SOLO POR DESTINO": "SI" if solo_destino else "",
        "CAUSAS LAB": ",".join(causas),
        "CAUSAS CON REMUESTREO CONFORME": ",".join(causas_rem),
        "LIBERACION DECLARADA": lib_f,
        "MERCADOS LIBERADOS": lib_m,
        "FUENTE DE LA LIBERACION": lib_o,
        "HISTORIA DEL RE-MUESTREO": " | ".join(motivos_rem),
        "TIPOS DE DESVIACION": ",".join(sorted(
            dets_v["TIPO DE DESVIACION"].dropna().astype(str).str.strip().unique())),
        "MOTIVO - LABORATORIO": " | ".join(motivos_lab),
        "MOTIVO - DETENCION": " | ".join(motivos_det),
        "MOTIVO - DETENCION HISTORICA": " | ".join(motivos_ope),
        "MOTIVO - MATERIA PRIMA": " | ".join(motivos_mp),
        "FECHA DE DETENCION HISTORICA": (opes["FECHA"].max() if len(opes) else pd.NaT),
        # la consulta de packing list resuelve contra el laboratorio, que no sabe
        # nada de las detenciones historicas: sin esta marca un lote bloqueado por correo
        # con lab conforme saldria LIBERADO en la consulta
        "DETENCION HISTORICA BLOQUEA": "SI" if ope_pend else "",
        "MATERIA PRIMA BLOQUEA": "SI" if mp_pend else "",
        "PROPUESTA DE LIBERACION (no libera)": " || ".join(propuestas),
        "OBSERVACIONES": " | ".join(obs),
        "LISTERIA": lis_txt(r["listeria"], rows_lab) or ("sin dato" if len(rows_lab) else None),
        "RAM MAX (UFC/g)": r["ram"],
        "NITRITO PROM. MIN (ppm)": r["nitrito"],
        "WPS MIN (%)": r["wps"],
        "A/R NITRITO (lab)": r["ar"],
        "UNIDADES NO CONFORMES": (json.dumps(unidades_nc, ensure_ascii=False)
                                  if unidades_nc else ""),
        "BATCHES CON RESULTADO": len(batches),
        "BATCHES NO CONFORMES": "; ".join(f"{b[len(l):] or '(base)'}: {', '.join(v)}"
                                          for b, v in malos_bat.items()),
        "N MUESTRAS LAB": len(rows_lab),
        "N DETENCIONES VIGENTES": len(dets_v),
        "ULTIMA MUESTRA LAB": rows_lab["_FECHA"].max() if len(rows_lab) else pd.NaT,
        "EN STOCK": "SI" if en_stock else "NO",
        "BODEGA(S)": " / ".join(sorted(s["BODEGA"].dropna().astype(str).unique())) if en_stock else "",
        "PRODUCTOS": (" / ".join(sorted(s["NOMBRE PRODUCTO"].dropna().astype(str).unique())) if en_stock
                      else " / ".join(sorted(dets["PRODUCTO"].dropna().astype(str).unique())) if len(dets)
                      else " / ".join(sorted(rows_lab["PRESENTACIÓN"].dropna().astype(str).unique()))
                      or " / ".join(sorted({p for p in opes["PRODUCTO"] if p}) if len(opes) else [])),
        "CLIENTE(S)": " / ".join(sorted(s["CLIENTE"].dropna().astype(str).unique())) if en_stock else "",
        "CAJAS EN STOCK": len(s),
    })

res = pd.DataFrame(filas)
orden = {"PNC": 0, "BLOQUEADO": 1, "CANDIDATO A LIBERAR": 2, "SIN ANALISIS": 3,
         "LIBERADO POR DECISION": 4, "LIBERADO": 5}
res = res.sort_values(["ESTADO", "EN STOCK", "LOTE"],
                      key=lambda c: c.map(orden) if c.name == "ESTADO" else c).reset_index(drop=True)

# ------------------------------------------------- veredicto por batch (lab)
# Son DOS preguntas distintas contra la misma fuente, y no deben mezclarse:
#   packing list -> viene con el codigo exacto, sufijo incluido: se resuelve
#                   contra LAB-REG-08 y punto.
#   stock        -> solo trae el lote base: ahi si hay que agregar, con la
#                   perdida de precision que eso implica.
# Esta hoja responde la primera. La hoja RESUMEN POR LOTE responde la segunda.
#
# Se agrupa por _U -el codigo CON sufijo- y no por _L. Agrupar sin el sufijo
# juntaba dias de produccion distintos: bastaba que el ultimo saliera mal para
# bloquear a los anteriores, que estaban conformes y tenian lote juliano propio.
# Un codigo pegado sin sufijo sigue resolviendo contra todas sus unidades, que
# es lo correcto: sin el sufijo no hay con que precisar.
bat = []
_sin_forma = 0
for b, g in lab.groupby("_U"):
    # El laboratorio a veces anota un correlativo ('099', '107') en la columna del
    # lote. No es un lote y no puede tener veredicto: sin este filtro aparecian en
    # el listado de bloqueados como si fueran producto. Los lotes de recorte y
    # despunte (SW26107, 7 caracteres) si lo son: los reconoce es_lote().
    if not es_lote(b.split("*")[0]):
        _sin_forma += 1
        continue
    rb, _ = evalua(g)
    hb = {c: historia(g, c) for c in CRIT}
    causas_b = [c for c in CRIT if hb[c]["estado"] == "NO CONFORME"]
    rem_b = [c for c in CRIT if hb[c]["estado"] == "REMUESTREO CONFORME"]
    dv = det[det["_L"].map(lambda x: emparenta(x, b)) & det["_VIGENTE"]]
    # La detencion historica suele identificar el dia con el sufijo: aqui, que se
    # responde por unidad, hay que respetarlo. En el RESUMEN POR LOTE no se puede,
    # porque el stock no distingue dias y las cajas no se separan.
    ov = ope[ope["_U"].map(lambda x: alcanza(x, b))] if len(ope) else ope
    motivo_ov = " | ".join(sorted({str(m).strip() for m in ov["MOTIVO"]
                                   if str(m).strip()})[:2])[:150] if len(ov) else ""
    base = next((s for s in lotes_stock if emparenta(s, b)), "")
    juzgable = any(hb[c]["estado"] in ("CONFORME", "NO CONFORME", "REMUESTREO CONFORME")
                   for c in CRIT)
    if (dv["_ESTADO"] == "PNC").any():
        est = "PNC"
    elif causas_b or len(dv) or len(ov):
        est = "BLOQUEADO"
    elif rem_b:
        est = "CANDIDATO A LIBERAR"
    elif juzgable:
        est = "LIBERADO"
    else:
        est = "SIN ANALISIS"
    lb_f, lb_m, lb_o = liberacion(b)
    bat.append({
        "BATCH": str(g["LOTE SW"].iloc[0]).strip(),
        "BATCH (normalizado)": b,
        "ESTADO": est,
        "CAUSAS LAB": ",".join(causas_b),
        "MOTIVO - LABORATORIO": " | ".join(hb[c]["txt"] for c in causas_b),
        "RE-MUESTREO CONFORME": " | ".join(hb[c]["txt"] for c in rem_b),
        "MOTIVO - DETENCION": " | ".join(f"{d['ID']} {d['TIPO DE DESVIACION']}"
                                         for _, d in dv.iterrows()),
        "MOTIVO - DETENCION HISTORICA": motivo_ov,
        "LISTERIA": lis_txt(rb["listeria"], g) or "sin dato",
        "RAM MAX (UFC/g)": rb["ram"],
        "NITRITO PROMEDIO (ppm)": rb["nitrito"],
        "WPS (%)": rb["wps"],
        "N MUESTRAS": rb["n"],
        "PRIMERA MUESTRA": g["_FECHA"].min(),
        "ULTIMA MUESTRA": g["_FECHA"].max(),
        "TIPO": " / ".join(sorted(g["TIPO "].dropna().astype(str).str.strip().unique())),
        "PRESENTACION": " / ".join(sorted(g["PRESENTACIÓN"].dropna().astype(str).unique()))[:120],
        "OBSERVACION LAB": " / ".join(sorted(g["OBSERVACIÓN"].dropna().astype(str).unique()))[:120],
        "LINEA": " / ".join(sorted({x for x in g["_LINEA"] if x})) or "sin clasificar",
        "LIBERACION DECLARADA": lb_f,
        "MERCADOS LIBERADOS": lb_m,
        "FUENTE DE LA LIBERACION": lb_o,
        "LOTE BASE EN STOCK": base,
    })
bats = pd.DataFrame(bat).sort_values("BATCH (normalizado)")
if _sin_forma:
    print(f"  ({_sin_forma} codigos del laboratorio sin forma de lote omitidos del "
          "veredicto: son correlativos, no lotes)")
print(f"Veredicto por batch: {len(bats)} batches con resultado | "
      + " ".join(f"{k}={v}" for k, v in bats['ESTADO'].value_counts().items()))

# ------------------------------------------------- historial de veredictos
# El cruce se recalcula entero en cada corrida: sin esto la historia se pierde y
# no hay forma de saber que un lote estuvo bloqueado y despues se libero.
# estado_actual.csv se sobreescribe (es la foto contra la que se compara);
# cambios.csv solo crece y es el registro de transiciones.
HIST = config.ruta(config.DIR_HISTORIAL)
os.makedirs(HIST, exist_ok=True)
F_ACT = os.path.join(HIST, "estado_actual.csv")
F_CAM = os.path.join(HIST, "cambios.csv")
CORRIDA = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
# Huella de los criterios vigentes: sin esto no hay forma de saber si un lote
# cambio de estado porque llego un resultado nuevo o porque cambiamos la regla.
CRITERIOS = config.huella_criterios()
F_CRI = os.path.join(HIST, "criterios.csv")
_prev_cri = ""
if os.path.exists(F_CRI):
    _c = pd.read_csv(F_CRI, dtype=str).fillna("")
    _prev_cri = _c["CRITERIOS"].iloc[-1] if len(_c) else ""
CAMBIO_CRI = "SI" if (_prev_cri and _prev_cri != CRITERIOS) else "NO"
if _prev_cri != CRITERIOS:
    pd.DataFrame([[CORRIDA, CRITERIOS]], columns=["CORRIDA", "CRITERIOS"]).to_csv(
        F_CRI, mode="a", header=not os.path.exists(F_CRI), index=False, encoding="utf-8-sig")
    print(f"  criterios: {'CAMBIARON en esta corrida' if _prev_cri else 'registrados'}")

ahora = pd.concat([
    res.assign(NIVEL="lote")[["NIVEL", "LOTE (normalizado)", "ESTADO", "CAUSAS LAB",
                              "CAJAS EN STOCK"]]
       .rename(columns={"LOTE (normalizado)": "CLAVE", "CAJAS EN STOCK": "CAJAS"}),
    bats.assign(NIVEL="batch", CAJAS=0)[["NIVEL", "BATCH (normalizado)", "ESTADO",
                                         "CAUSAS LAB", "CAJAS"]]
        .rename(columns={"BATCH (normalizado)": "CLAVE"}),
], ignore_index=True)
ahora["CAUSAS LAB"] = ahora["CAUSAS LAB"].fillna("")
ahora["CAJAS"] = ahora["CAJAS"].fillna(0).astype(int)

prev = None
if os.path.exists(F_ACT):
    _a = pd.read_csv(F_ACT, dtype=str).fillna("")
    prev = dict(zip(_a["NIVEL"] + "|" + _a["CLAVE"], _a["ESTADO"]))

cambios = []
if prev is not None:
    for _, x in ahora.iterrows():
        k = f"{x['NIVEL']}|{x['CLAVE']}"
        ant = prev.get(k)
        if ant is None:
            cambios.append([CORRIDA, x["NIVEL"], x["CLAVE"], "(nuevo)", x["ESTADO"],
                            x["CAUSAS LAB"], x["CAJAS"], CAMBIO_CRI])
        elif ant != x["ESTADO"]:
            cambios.append([CORRIDA, x["NIVEL"], x["CLAVE"], ant, x["ESTADO"],
                            x["CAUSAS LAB"], x["CAJAS"], CAMBIO_CRI])
    vivos = set(ahora["NIVEL"] + "|" + ahora["CLAVE"])
    for k, v in prev.items():
        if k not in vivos:
            nv, cl = k.split("|", 1)
            cambios.append([CORRIDA, nv, cl, v, "(ya no aparece)", "", 0, CAMBIO_CRI])

COLS_CAM = ["CORRIDA", "NIVEL", "CLAVE", "ESTADO ANTERIOR", "ESTADO NUEVO", "CAUSAS", "CAJAS",
            "HUBO CAMBIO DE CRITERIO"]


def leer_cambios():
    """Lee el log tolerando que haya crecido de esquema entre versiones.

    Antes se hacia append y al agregar una columna el archivo quedo con filas de
    7 y de 8 campos, que el parser rapido no puede leer. Ahora se reescribe
    completo en cada corrida (son cientos de filas) y ademas se normaliza lo viejo.
    """
    if not os.path.exists(F_CAM):
        return pd.DataFrame(columns=COLS_CAM)
    for kw in ({}, {"engine": "python", "on_bad_lines": "skip"}):
        try:
            d = pd.read_csv(F_CAM, dtype=str, **kw).fillna("")
            break
        except Exception:                                        # noqa: BLE001
            d = None
    if d is None:
        bak = F_CAM + ".bak"
        os.replace(F_CAM, bak)
        print(f"  historial ilegible, se movio a {os.path.basename(bak)} y se empieza de nuevo")
        return pd.DataFrame(columns=COLS_CAM)
    for c in COLS_CAM:
        if c not in d.columns:
            d[c] = ""
    return d[d["CORRIDA"] != "CORRIDA"][COLS_CAM]


camlog = pd.concat([leer_cambios(), pd.DataFrame(cambios, columns=COLS_CAM)], ignore_index=True)
camlog.to_csv(F_CAM, index=False, encoding="utf-8-sig")
ahora.to_csv(F_ACT, index=False, encoding="utf-8-sig")

if prev is None:
    print("\nHistorial: linea base creada. Desde la proxima corrida se registran los cambios.")
else:
    print(f"\nHistorial: {len(cambios)} cambio(s) de estado desde la corrida anterior")
    for c in cambios[:12]:
        print(f"   {c[1]:5s} {c[2]:16s} {c[3]}  ->  {c[4]}"
              + (f"  ({c[6]} cajas)" if c[6] else ""))
    if len(cambios) > 12:
        print(f"   ... y {len(cambios) - 12} mas")

    # Un lote bloqueado que sale del stock es la unica transicion que el sistema
    # NO puede explicar solo: pudo despacharse, moverse a una bodega que no
    # bajamos -PNC entre ellas- o reprocesarse. Mezclado entre los demas cambios
    # pasa inadvertido, y es justo el que hay que ir a mirar.
    # Se descartan los que siguen representados por un pariente vivo: cuando un
    # lote sale de bodega deja de entrar con el codigo de Fishken -que no lleva
    # la letra del batch- y pasa a entrar con el del laboratorio, que si la
    # lleva. Es el mismo producto visto con otro codigo, no un lote que se fue.
    _vivos_lote = [k.split("|", 1)[1] for k in vivos if k.startswith("lote|")]
    _fue = [c for c in cambios
            if c[4] == "(ya no aparece)" and c[1] == "lote"
            and c[3] in ("BLOQUEADO", "PNC", "CANDIDATO A LIBERAR")
            and not any(emparenta(c[2], v) for v in _vivos_lote)]
    if _fue:
        print(f"\n   ATENCION: {len(_fue)} lote(s) que NO estaban liberados ya no aparecen "
              "en el stock.")
        print("   Puede ser despacho, traslado a una bodega que no se baja (PNC, VILA, "
              "VIMU) o reproceso.")
        print("   El sistema no puede distinguirlos: hay que verificar donde quedaron.")
        for c in _fue[:10]:
            print(f"      {c[2]:16s} estaba {c[3]}")
        if len(_fue) > 10:
            print(f"      ... y {len(_fue) - 10} mas, en la hoja CAMBIOS")

camlog = camlog.iloc[::-1]          # lo mas reciente primero

# ----------------------------------------------------------------- detalles
mapa = res.set_index("LOTE (normalizado)")
d_st = stock.copy()
for col in ("ESTADO", "ORIGEN DEL BLOQUEO", "MOTIVO - LABORATORIO", "MOTIVO - DETENCION",
            "MOTIVO - DETENCION HISTORICA", "MOTIVO - MATERIA PRIMA"):
    d_st[col] = d_st["_L"].map(mapa[col])
cols_st = (["ESTADO", "ORIGEN DEL BLOQUEO", "MOTIVO - LABORATORIO", "MOTIVO - DETENCION",
            "MOTIVO - DETENCION HISTORICA", "MOTIVO - MATERIA PRIMA", "BODEGA"]
           + [c for c in stock.columns if not c.startswith("_") and c != "BODEGA"])
d_st = d_st[cols_st]

lab["_LOTE_REF"] = None
for l in universo:
    m = lab["_L"].map(lambda x: emparenta(x, l))
    for i in lab.index[m]:
        p = lab.at[i, "_LOTE_REF"]
        if p is None or len(l) > len(p):
            lab.at[i, "_LOTE_REF"] = l
d_lab = lab[lab["_LOTE_REF"].notna()].copy()
d_lab["ESTADO LOTE"] = d_lab["_LOTE_REF"].map(mapa["ESTADO"])
d_lab = d_lab[["_LOTE_REF", "ESTADO LOTE", "FUENTE LAB", "CÓDIGO LAB", "FECHA INGRESO", "TIPO ",
               "GRUPO", "PRESENTACIÓN", "LOTE SW", "OBSERVACIÓN"] + LM + RAM + NIT +
              ["NITRITO PROMEDIO"] + WPS + ["WPS PROMEDIO", "A/R Nitrito"]].rename(
    columns={"_LOTE_REF": "LOTE (normalizado)"})
d_lab = d_lab.sort_values(["LOTE (normalizado)", "FECHA INGRESO"])

d_det = det.drop(columns=[c for c in det.columns if c.startswith("_")]).copy()
d_det["ESTADO DEL LOTE EN EL CRUCE"] = det["_L"].map(
    lambda x: next((mapa.at[l, "ESTADO"] for l in universo if emparenta(x, l)), "sin match"))
d_det["PROPUESTA DE LIBERACION"] = det["_L"].map(
    lambda x: next((mapa.at[l, "PROPUESTA DE LIBERACION (no libera)"]
                    for l in universo if emparenta(x, l)), ""))

# ----------------------------------------------------------------- escritura
# Ventana de cada fuente: es lo que explica el desfase entre bodega, laboratorio y correos.
fuentes = []
def _guardado(nombre):
    # fromtimestamp da hora local; pd.Timestamp(unit="s") da UTC y mostraria la
    # hora corrida cuatro horas, que en una hoja de auditoria confunde.
    r = config.ruta(nombre)
    return (pd.Timestamp(datetime.datetime.fromtimestamp(os.path.getmtime(r)))
            if os.path.exists(r) else pd.NaT)


for a, g in stock.groupby("ARCHIVO ORIGEN"):
    f = pd.to_datetime(g["FECHA INGRESO"], errors="coerce")
    fuentes.append({"FUENTE": "Stock", "ARCHIVO": a, "REGISTROS": len(g),
                    "DESDE": f.min(), "HASTA": f.max(), "ARCHIVO GUARDADO": _guardado(a)})
for h, g in lab.groupby("FUENTE LAB"):
    fuentes.append({"FUENTE": "Laboratorio", "ARCHIVO": h, "REGISTROS": len(g),
                    "DESDE": g["_FECHA"].min(), "HASTA": g["_FECHA"].max(),
                    "ARCHIVO GUARDADO": g["_GUARDADO"].max()})
fd = pd.to_datetime(det["FECHA CORREO"], errors="coerce")
fuentes.append({"FUENTE": "Detenciones", "ARCHIVO": FUENTE_DET, "REGISTROS": len(det),
                "DESDE": fd.min(), "HASTA": fd.max(),
                "ARCHIVO GUARDADO": (pd.Timestamp.now() if "Postgres" in FUENTE_DET
                                     else _guardado(os.path.basename(F_DET)))})
# Cada PRO-REG-46 declara LO SUYO: los enlaces lote de proveedor -> lote SW que
# aporta, y la ventana de sus propias recepciones. Antes esta fila repetia en los
# cuatro archivos el total de muestras de materia prima del laboratorio, que no
# sale de aqui: se leia como cuatro veces la cobertura que realmente hay.
for _n46 in _f46:
    _fr = _ap46.get(_n46, {}).get("fechas") or []
    _fr = pd.concat(_fr) if _fr else pd.Series(dtype="datetime64[ns]")
    fuentes.append({"FUENTE": "Materia prima (PRO-REG-46)", "ARCHIVO": _n46,
                    "REGISTROS": _ap46.get(_n46, {}).get("enlaces", 0),
                    "DESDE": _fr.min() if len(_fr) else pd.NaT,
                    "HASTA": _fr.max() if len(_fr) else pd.NaT,
                    "ARCHIVO GUARDADO": _guardado(_n46)})
# Las muestras de materia prima son del laboratorio, no del PRO-REG-46. Iban sin
# fila propia y por eso terminaron prestadas en la de los archivos de ingreso.
fuentes.append({"FUENTE": "Materia prima (muestras de laboratorio)",
                "ARCHIVO": "LAB-REG-08 (filas de MP, sin lote SW)", "REGISTROS": len(mp),
                "DESDE": mp["_FECHA"].min() if len(mp) else pd.NaT,
                "HASTA": mp["_FECHA"].max() if len(mp) else pd.NaT,
                "ARCHIVO GUARDADO": pd.NaT})
fuentes.append({"FUENTE": "Detenciones historicas (abiertas)",
                "ARCHIVO": config.ARCH_OPERATIVO, "REGISTROS": len(ope),
                "DESDE": ope["FECHA"].min() if len(ope) else pd.NaT,
                "HASTA": ope["FECHA"].max() if len(ope) else pd.NaT,
                "ARCHIVO GUARDADO": _guardado(config.ARCH_OPERATIVO)})
fuentes.append({"FUENTE": "Detenciones historicas (liberaciones)",
                "ARCHIVO": config.ARCH_OPERATIVO, "REGISTROS": len(libu),
                "DESDE": libu["FECHA"].min() if len(libu) else pd.NaT,
                "HASTA": libu["FECHA"].max() if len(libu) else pd.NaT,
                "ARCHIVO GUARDADO": _guardado(config.ARCH_OPERATIVO)})
fuentes = pd.DataFrame(fuentes)

with pd.ExcelWriter(OUT, engine="openpyxl") as xl:
    res.to_excel(xl, sheet_name="RESUMEN POR LOTE", index=False, startrow=3)
    bats.to_excel(xl, sheet_name="VEREDICTO POR BATCH", index=False)
    camlog.to_excel(xl, sheet_name="CAMBIOS", index=False)
    fuentes.to_excel(xl, sheet_name="FUENTES", index=False)
    d_st.to_excel(xl, sheet_name="DETALLE STOCK", index=False)
    d_lab.to_excel(xl, sheet_name="DETALLE LAB", index=False)
    d_det.to_excel(xl, sheet_name="DETENCIONES", index=False)

wb = load_workbook(OUT)
ws, wd = wb["RESUMEN POR LOTE"], wb["DETALLE STOCK"]
c_l = get_column_letter(list(d_st.columns).index("LOTE DE PLANTA") + 1)
c_kg = get_column_letter(list(d_st.columns).index("PESO NETO (KG)") + 1)
c_pz = get_column_letter(list(d_st.columns).index("PIEZAS") + 1)
nf = len(d_st) + 1
c_lr = get_column_letter(list(res.columns).index("LOTE") + 1)
k1, k2 = len(res.columns) + 1, len(res.columns) + 2
ws.cell(4, k1, "KG NETOS EN STOCK")
ws.cell(4, k2, "PIEZAS EN STOCK")
for i in range(len(res)):
    f = 5 + i
    rl = f"'DETALLE STOCK'!${c_l}$2:${c_l}${nf}"
    ws.cell(f, k1, f"=SUMIFS('DETALLE STOCK'!${c_kg}$2:${c_kg}${nf},{rl},${c_lr}{f})")
    ws.cell(f, k2, f"=SUMIFS('DETALLE STOCK'!${c_pz}$2:${c_pz}${nf},{rl},${c_lr}{f})")

ws["A1"] = "CRUCE DE BLOQUEOS - STOCK x LAB-REG-08 2026 x REGISTRO DE DETENCIONES"
ws["A2"] = (f"Laboratorio (derivado, se recalcula): Listeria PRESENCIA en toda linea | "
            f"RAM promedio de replicas > {LIM_RAM:,} UFC/g, o una replica incontable, en toda linea | Binomio WPS/nitrito: libera si "
            f"nitrito >= {LIM_NITRITO} ppm CON WPS > {WPS_MIN}%, o si el nitrito supera "
            f"{NIT_BINOMIO} ppm por si solo; bajo {LIM_NITRITO} ppm bloquea aunque el WPS "
            "sobre, y sin WPS medido no se puede acreditar. SOLO en linea refrigerada y en "
            "bacon/wheel, que salen congelados pero se venden refrigerados en destino (el "
            "resto de la congelada, incluidos los carpaccios, no lo aplica) | "
            "Listeria SOLO en linea refrigerada y en congelada con destino EE.UU. o "
            "Costa Rica (cliente con PMT); si el destino no se puede determinar, se aplica. "
            "Un criterio deja de estar vigente si hay re-muestreo posterior conforme que vuelva "
            "a medirlo en la MISMA unidad (lote con su sufijo *SSD): un conforme de otra unidad no "
            "la cierra, y una unidad no conforme deja no conforme al lote. Detencion (declarada por correo) y detencion historica "
            "(Bloqueo 2026.xlsm, donde el Estado se escribe solo al liberar): bloquean aunque "
            "no haya resultado, cada uno por su motivo.")
ws["A3"] = ("Los tres origenes se acumulan: un lote con varios debe cerrarlos todos. La columna de propuesta "
            "NO libera nada: exige muestra posterior a la fecha del evento o del bloqueo y que cubra el "
            "criterio desviado; la liberacion la firma Calidad en el REGISTRO DECISIONES. Un motivo que el "
            "laboratorio no mide (documentacion, reclamo, desvio de proceso) no se levanta con muestras.")
ws["A1"].font = Font(name="Arial", size=13, bold=True)
for r in (2, 3):
    ws[f"A{r}"].font = Font(name="Arial", size=9, italic=True)
    ws[f"A{r}"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[r].height = 30
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=k2)
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=k2)

hf = PatternFill("solid", fgColor="1F3864")
thin = Side(style="thin", color="BFBFBF")
fills = {"PNC": PatternFill("solid", fgColor="D9D9D9"),
         "LIBERADO POR DECISION": PatternFill("solid", fgColor="C6EFCE"),
         "BLOQUEADO": PatternFill("solid", fgColor="FFC7CE"),
         "CANDIDATO A LIBERAR": PatternFill("solid", fgColor="DDEBF7"),
         "SIN ANALISIS": PatternFill("solid", fgColor="FFEB9C"),
         "LIBERADO": PatternFill("solid", fgColor="C6EFCE")}
fonts = {"PNC": Font(name="Arial", size=10, bold=True, color="3F3F3F"),
         "LIBERADO POR DECISION": Font(name="Arial", size=10, bold=True, color="006100"),
         "BLOQUEADO": Font(name="Arial", size=10, bold=True, color="9C0006"),
         "CANDIDATO A LIBERAR": Font(name="Arial", size=10, bold=True, color="1F4E79"),
         "SIN ANALISIS": Font(name="Arial", size=10, bold=True, color="9C6500"),
         "LIBERADO": Font(name="Arial", size=10, bold=True, color="006100")}

for hoja, h in (("RESUMEN POR LOTE", 4), ("VEREDICTO POR BATCH", 1), ("CAMBIOS", 1),
                ("DETALLE STOCK", 1), ("DETALLE LAB", 1), ("DETENCIONES", 1), ("FUENTES", 1)):
    w = wb[hoja]
    for c in w[h]:
        if c.value is not None:
            c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            c.fill = hf
            c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            c.border = Border(bottom=thin)
    w.row_dimensions[h].height = 30
    w.freeze_panes = w.cell(h + 1, 3)
    w.auto_filter.ref = f"A{h}:{get_column_letter(w.max_column)}{w.max_row}"
    for col in range(1, w.max_column + 1):
        L = [len(str(w.cell(r, col).value or "")) for r in range(h, min(w.max_row, h + 300) + 1)]
        w.column_dimensions[get_column_letter(col)].width = min(max(10, max(L) + 2), 46)
    if hoja in ("RESUMEN POR LOTE", "DETALLE STOCK", "VEREDICTO POR BATCH"):
        ce = [c.column for c in w[h] if c.value == "ESTADO"][0]
        for r in range(h + 1, w.max_row + 1):
            c = w.cell(r, ce)
            if c.value in fills:
                c.fill, c.font = fills[c.value], fonts[c.value]

for nom, fmt in (("RAM MAX (UFC/g)", "#,##0"), ("NITRITO PROM. MIN (ppm)", "0.0"),
                 ("WPS MIN (%)", "0.00"),
                 ("KG NETOS EN STOCK", "#,##0.00"), ("PIEZAS EN STOCK", "#,##0"),
                 ("CAJAS EN STOCK", "#,##0")):
    col = [c.column for c in ws[4] if c.value == nom][0]
    for r in range(5, ws.max_row + 1):
        ws.cell(r, col).number_format = fmt
        ws.cell(r, col).font = Font(name="Arial", size=10)

wb.save(OUT)

# ----------------------------------------------------------------- consola
print("\nLotes evaluados:", len(res), "| en stock:", len(lotes_stock),
      "| solo detencion:", len(huerfanos), "| solo detencion historica:", len(ope_solo))
print(res["ESTADO"].value_counts().to_string())
print("\nOrigen del bloqueo (lotes con stock):")
print(res[(res["EN STOCK"] == "SI") & (res["ORIGEN DEL BLOQUEO"] != "")]
      .groupby("ORIGEN DEL BLOQUEO")
      .agg(LOTES=("LOTE", "size"), CAJAS=("CAJAS EN STOCK", "sum")).to_string())
print("\n--- BLOQUEADOS / PNC (en stock) ---")
v = res[res["ESTADO"].isin(["BLOQUEADO", "PNC"]) & (res["EN STOCK"] == "SI")]
print(v[["LOTE", "ESTADO", "ORIGEN DEL BLOQUEO", "MOTIVO - LABORATORIO", "MOTIVO - DETENCION",
         "MOTIVO - DETENCION HISTORICA", "CAJAS EN STOCK"]].to_string(index=False))
print("\n--- PROPUESTAS DE LIBERACION ---")
# Solo las accionables: con las detenciones historicas dentro, las no liberables son
# cientos y tapan justamente lo que hay que revisar.
_p = res[res["PROPUESTA DE LIBERACION (no libera)"] != ""]
_ac = _p[_p["PROPUESTA DE LIBERACION (no libera)"].str.contains("LIBERABLE segun lab")]
for _, x in _ac.iterrows():
    print(f"  {x['LOTE']:14s} {x['PROPUESTA DE LIBERACION (no libera)']}")
print(f"  ({len(_p) - len(_ac)} lote(s) mas con propuesta NO LIBERABLE, en el Excel)")
print("\n--- CALIDAD DE DATOS ---")
print("Sospecha de prefijo faltante:", {k: v for k, v in sospecha_pfx.items()} or "ninguna")
print("Pares ASC/BAP legitimos:", sorted({tuple(sorted([k] + v)) for k, v in gemelos.items()}) or "ninguno")
print("Confusion O/0:", sorted({tuple(sorted([k] + v)) for k, v in confusion.items()}) or "ninguna")
print("Detenciones sin lote en stock:", casi or "sin sospecha de tipeo")

sobre = res[(res["BATCHES NO CONFORMES"] != "") &
            (res["ESTADO"].isin(["BLOQUEADO", "PNC"]))].copy()
sobre["_nb"] = sobre["BATCHES NO CONFORMES"].str.count(";") + 1
parcial = sobre[sobre["_nb"] < sobre["BATCHES CON RESULTADO"]]
print(f"\nLotes bloqueados por un subconjunto de sus batches: {len(parcial)} "
      f"({int(parcial['CAJAS EN STOCK'].sum())} cajas) - no separables con el dato actual")
print("Salida:", OUT)
