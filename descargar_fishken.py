# -*- coding: utf-8 -*-
"""Descarga los reportes de stock desde Fishken, sin abrir el navegador.

    Requiere FISHKEN_USER y FISHKEN_PWD en las variables de entorno.
    python descargar_fishken.py            # las tres bodegas que usa el cruce
    python descargar_fishken.py C6         # una en particular

Fishken es ASP.NET WebForms: no hay una URL de exportacion. Cada formulario
viaja con tokens que el servidor genera en cada carga -__VIEWSTATE,
__VIEWSTATEGENERATOR, __EVENTVALIDATION- y que no se pueden guardar. Por eso el
flujo es pedir la pagina, leer los tokens, y recien ahi enviar el formulario;
tres veces, porque buscar y exportar son dos envios distintos.

Si algun dia cambian los nombres de los controles de esa pantalla, este script
falla con un mensaje claro en vez de bajar un archivo vacio. Es a proposito:
mejor que se note.
"""
import os
import re
import sys
import urllib.parse

import config

try:
    import requests
except ImportError:
    sys.exit("Falta requests. Instala:  python -m pip install requests")

BASE = os.environ.get("FISHKEN_URL", "http://192.168.2.202/FishKenWeb")
LOGIN = BASE + "/index"
REPORTE = BASE + "/SistemaInformesAdministrativos/Menus/MenuStockProductosTerminadosIA"
PFX = "ctl00$ASPxRoundPanel2$ContentPlaceHolder2$"

BODEGAS = {
    "T0": "TODAS",
    "C1": "CAMARA CONGELADOS 1", "C2": "CAMARA CONGELADOS 2", "C3": "BODEGA REPROCESO",
    "C4": "VILA", "C5": "VIMU", "C6": "CAMARA PNC",
    "C7": "INVENTARIO PT CAMARA CONG 1", "C8": "INVENTARIO PT CAMARA CONG 2",
}

# Se aceptan los dos juegos de nombres: los que ya estaban configurados en el
# equipo y los que proponia este script. Aqui solo aparecen los NOMBRES; los
# valores no se imprimen ni se registran en ninguna parte.
USUARIO = os.environ.get("FISHKEN_USER") or os.environ.get("FISHKEN_USUARIO")
CLAVE = os.environ.get("FISHKEN_PWD") or os.environ.get("FISHKEN_CLAVE")
if not USUARIO or not CLAVE:
    sys.exit("Faltan las credenciales en las variables de entorno.\n"
             "Se buscan FISHKEN_USER y FISHKEN_PWD (o FISHKEN_USUARIO y FISHKEN_CLAVE).\n"
             "No las escribas en el script ni las pases por linea de comandos.")


def tokens(html, donde):
    """Los tres campos ocultos que ASP.NET exige en cada envio."""
    t = {}
    for campo in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'id="' + campo + r'"[^>]*value="([^"]*)"', html) \
            or re.search(r'name="' + campo + r'"[^>]*value="([^"]*)"', html)
        if not m:
            if campo == "__EVENTVALIDATION":
                continue          # algunas paginas no lo usan
            sys.exit(f"No encontre {campo} en {donde}. La pantalla cambio de estructura.")
        t[campo] = urllib.parse.unquote(m.group(1)) if "%" in m.group(1) else m.group(1)
    return t


def estado_grilla(html):
    """DevExpress manda el estado de la grilla junto con el formulario."""
    g = {}
    for m in re.finditer(r'name="(' + re.escape(PFX) + r'Gridview\d)"[^>]*value="([^"]*)"', html):
        g[m.group(1)] = m.group(2)
    return g


s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (descarga automatica de reportes South Wind)"

print("Autenticando...")
r = s.get(LOGIN, timeout=60)
r.raise_for_status()
datos = tokens(r.text, "la pagina de login")
datos.update({"usuario": USUARIO, "password": CLAVE, "logon": "Ingresar"})
r = s.post(LOGIN, data=datos, timeout=60)
r.raise_for_status()
# Un login correcto NO redirige: devuelve la misma pantalla de acceso con un
# window.open('Principal.aspx') arriba, que es lo que en el navegador abre la
# segunda pestania. Buscar la ausencia del formulario da un falso negativo.
if "Principal.aspx" not in r.text:
    sys.exit("El login no prospero: la respuesta no abre Principal.aspx. "
             "Revisa las credenciales o si la pantalla de acceso cambio.")
s.get(BASE + "/Principal.aspx", timeout=60)   # el navegador la abre; se replica

# T0 (TODAS) sirve para mirar en pantalla pero NO para exportar: la busqueda
# arma una grilla por bodega y el boton baja solo la primera, asi que el archivo
# sale con una sola. Por eso el valor por omision son las tres que usa el cruce.
PREDETERMINADAS = ["C3", "C1", "C2"]
pedidas = [a.upper() for a in sys.argv[1:]] or PREDETERMINADAS
if "T0" in pedidas:
    print("AVISO: T0 exporta solo la primera bodega de la grilla, no todas. "
          "Pide las bodegas por separado si quieres todas.\n")
desconocidas = [b for b in pedidas if b not in BODEGAS]
if desconocidas:
    sys.exit(f"Bodega desconocida: {desconocidas}. Validas: {', '.join(BODEGAS)}")

for sala in pedidas:
    print(f"\n{sala} ({BODEGAS[sala]})")
    r = s.get(REPORTE, timeout=120)
    r.raise_for_status()

    print("  buscando...", end="", flush=True)
    f = tokens(r.text, "la pantalla de stock")
    f.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "",
              PFX + "DropDownListSala": sala,
              PFX + "DropDownList1": "0",
              PFX + "Boton_Buscar": "BUSCAR"})
    r = s.post(REPORTE, data=f, timeout=600)
    r.raise_for_status()
    print(f" {len(r.content) // 1024} KB de resultados")

    print("  exportando...", end="", flush=True)
    f = tokens(r.text, "los resultados")
    f.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "",
              PFX + "DropDownListSala": sala,
              PFX + "DropDownList1": "0",
              PFX + "btnExportXls1.x": "26",
              PFX + "btnExportXls1.y": "32"})
    f.update(estado_grilla(r.text))
    r = s.post(REPORTE, data=f, timeout=600, stream=True)
    r.raise_for_status()

    disp = r.headers.get("content-disposition", "")
    m = re.search(r'filename="?([^";]+)', disp)
    if not m:
        sys.exit("  El servidor no devolvio un archivo. Puede que la sesion expirara "
                 "o que el boton de exportar cambiara de nombre.")
    # El servidor manda el nombre en latin-1; en Windows llega con la Í rota.
    nombre = m.group(1)
    try:
        nombre = nombre.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    destino = config.ruta(nombre)
    with open(destino, "wb") as fh:
        for trozo in r.iter_content(65536):
            fh.write(trozo)
    kb = os.path.getsize(destino) // 1024
    if kb < 5:
        sys.exit(f"  El archivo salio de {kb} KB: casi seguro esta vacio. Revisa la pantalla.")
    # El nombre lo pone el servidor segun la grilla exportada: si no coincide con
    # lo pedido, bajamos otra bodega y hay que enterarse.
    esperado = BODEGAS[sala].upper()
    if sala != "T0" and esperado not in nombre.upper():
        print(f"\n  ATENCION: se pidio {sala} ({esperado}) y el servidor devolvio "
              f"'{nombre}'. Revisa antes de usar este archivo.")
    print(f" {nombre}  ({kb} KB)")

print("\nListo.")
