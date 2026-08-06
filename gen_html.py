# -*- coding: utf-8 -*-
"""Genera CONSULTA BLOQUEOS.html: pagina autocontenida (sin internet) para pegar un
packing list y ver el estado de cada linea, con filtros por causa sobre el stock.

Paleta de causas validada con el port del validador de la skill dataviz
(scratchpad/valida.py): en claro sobre #fbfaf8 y en oscuro sobre #1e2024 pasa banda
de luminosidad, piso de croma, separacion CVD (dE 11.1), piso de vision normal
(dE 18.0) y contraste (>= 3.78:1), sin warnings.
"""
import json
import os
import pandas as pd

import config

BASE = config.BASE
SRC = config.ruta(config.ARCH_SALIDA)
OUT = config.ruta(config.ARCH_HTML)

res = pd.read_excel(SRC, sheet_name="RESUMEN POR LOTE", header=3)
det = pd.read_excel(SRC, sheet_name="DETALLE STOCK")
dets = pd.read_excel(SRC, sheet_name="DETENCIONES")
fue = pd.read_excel(SRC, sheet_name="FUENTES")
bats = pd.read_excel(SRC, sheet_name="VEREDICTO POR BATCH")
cam = pd.read_excel(SRC, sheet_name="CAMBIOS")

kg = det.groupby("LOTE DE PLANTA")["PESO NETO (KG)"].sum()
pz = det.groupby("LOTE DE PLANTA")["PIEZAS"].sum()
# desglose por bodega y por producto, para el panel de detalle
_bod = (det.groupby(["LOTE DE PLANTA", "BODEGA"])
        .agg(c=("PIEZAS", "size"), k=("PESO NETO (KG)", "sum")).reset_index())
_prd = (det.groupby(["LOTE DE PLANTA", "NOMBRE PRODUCTO"])
        .agg(c=("PIEZAS", "size")).reset_index())
BOD = {l: [[r["BODEGA"], int(r["c"]), round(float(r["k"]), 1)] for _, r in g.iterrows()]
       for l, g in _bod.groupby("LOTE DE PLANTA")}
PRD = {l: [[r["NOMBRE PRODUCTO"], int(r["c"])]
           for _, r in g.sort_values("c", ascending=False).head(12).iterrows()]
       for l, g in _prd.groupby("LOTE DE PLANTA")}
FECHA = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")


def txt(v):
    return "" if pd.isna(v) else str(v).strip()


def num(v):
    return None if pd.isna(v) else float(v)


def lista(v):
    return [x for x in txt(v).split(",") if x]


lotes = []
for _, r in res.iterrows():
    l = txt(r["LOTE"])
    lotes.append({
        "lote": l, "n": txt(r["LOTE (normalizado)"]), "estado": txt(r["ESTADO"]),
        "origen": txt(r["ORIGEN DEL BLOQUEO"]), "causas": lista(r["CAUSAS LAB"]),
        "tipos": lista(r["TIPOS DE DESVIACION"]),
        "lab": txt(r["MOTIVO - LABORATORIO"]), "det": txt(r["MOTIVO - DETENCION"]),
        "prop": txt(r["PROPUESTA DE LIBERACION (no libera)"]), "obs": txt(r["OBSERVACIONES"]),
        "listeria": txt(r["LISTERIA"]), "ram": num(r["RAM MAX (UFC/g)"]),
        "nit": num(r["NITRITO PROM. MIN (ppm)"]),
        "nbat": int(r["BATCHES CON RESULTADO"]) if not pd.isna(r["BATCHES CON RESULTADO"]) else 0,
        "batmal": txt(r["BATCHES NO CONFORMES"]),
        "nmue": int(r["N MUESTRAS LAB"]) if not pd.isna(r["N MUESTRAS LAB"]) else 0,
        "ult": txt(r["ULTIMA MUESTRA LAB"])[:10],
        "stock": txt(r["EN STOCK"]) == "SI", "bodegas": txt(r["BODEGA(S)"]),
        "prod": txt(r["PRODUCTOS"]), "cliente": txt(r["CLIENTE(S)"]),
        "cajas": int(r["CAJAS EN STOCK"]) if not pd.isna(r["CAJAS EN STOCK"]) else 0,
        "kg": round(float(kg.get(l, 0)), 1), "pz": int(pz.get(l, 0)),
        "rem": lista(r["CAUSAS CON REMUESTREO CONFORME"]),
        "hrem": txt(r["HISTORIA DEL RE-MUESTREO"]),
        "libf": txt(r["LIBERACION DECLARADA"])[:10], "libm": txt(r["MERCADOS LIBERADOS"]),
        "libo": txt(r["FUENTE DE LA LIBERACION"]), "linea": txt(r["LINEA"]), "dest": txt(r["DESTINO RESTRINGIDO"]),
        "mlib": txt(r["MOTIVO DE LA LIBERACION"]), "porcrit": txt(r["ESTADO POR CRITERIO"]),
        "evid": txt(r["EVIDENCIA (ultimas muestras)"]),
        "bod": BOD.get(l, []), "prd": PRD.get(l, []),
        "of": txt(r.get("OF", "")),
    })

# Indice de laboratorio a nivel de batch: es la referencia para consultar un
# packing list, que trae el lote con su letra de batch. No pasa por el stock.
batches = [{
    "b": txt(r["BATCH"]), "n": txt(r["BATCH (normalizado)"]), "estado": txt(r["ESTADO"]),
    "causas": lista(r["CAUSAS LAB"]), "lab": txt(r["MOTIVO - LABORATORIO"]),
    "det": txt(r["MOTIVO - DETENCION"]),
    "nm": int(r["N MUESTRAS"]) if not pd.isna(r["N MUESTRAS"]) else 0,
    "ult": txt(r["ULTIMA MUESTRA"])[:10], "pres": txt(r["PRESENTACION"]),
    "tipo": txt(r["TIPO"]), "obs": txt(r["OBSERVACION LAB"]),
    "rem": txt(r["RE-MUESTREO CONFORME"]), "libf": txt(r["LIBERACION DECLARADA"])[:10],
    "libm": txt(r["MERCADOS LIBERADOS"]), "libo": txt(r["FUENTE DE LA LIBERACION"]),
    "linea": txt(r["LINEA"]),
} for _, r in bats.iterrows()]

cambios = [{"corrida": txt(r["CORRIDA"]), "nivel": txt(r["NIVEL"]), "clave": txt(r["CLAVE"]),
            "de": txt(r["ESTADO ANTERIOR"]), "a": txt(r["ESTADO NUEVO"]),
            "causas": txt(r["CAUSAS"]), "regla": txt(r.get("HUBO CAMBIO DE CRITERIO", "")),
            "cajas": int(r["CAJAS"]) if not pd.isna(r["CAJAS"]) else 0}
           for _, r in cam.iterrows()]

detn = [{k: txt(v) for k, v in row.items()} for _, row in
        dets[["ID", "FECHA CORREO", "TIPO DE DESVIACION", "LOTE", "PRODUCTO", "ALCANCE",
              "FECHA DEL EVENTO", "CRITERIOS DE LIBERACION", "ESTADO",
              "PROPUESTA DE LIBERACION"]].iterrows()]

fue["HASTA"] = pd.to_datetime(fue["HASTA"], errors="coerce")
META = {
    "fecha": FECHA, "lotes": len(lotes), "cajas": int(res["CAJAS EN STOCK"].sum()),
    "bodegas": sorted({b for x in lotes for b in x["bodegas"].split(" / ") if b}),
    "fuentes": [{"f": txt(r["FUENTE"]), "a": txt(r["ARCHIVO"]), "n": int(r["REGISTROS"]),
                 "h": str(r["HASTA"])[:10]} for _, r in fue.iterrows()],
    "corte_lab": str(fue[fue["FUENTE"] == "Laboratorio"]["HASTA"].max())[:10],
}
META["batches"] = len(batches)
DATA = json.dumps({"lotes": lotes, "batches": batches, "det": detn, "cambios": cambios,
                   "meta": META},
                  ensure_ascii=False).replace("</", "<\\/")

HTML = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Consulta de bloqueos - South Wind</title>
<style>
:root{
  color-scheme:light;
  --canvas:#f6f5f2; --surface:#fbfaf8; --surface-2:#f1efe9; --surface-3:#eceae3;
  --ink:#1a1a18; --ink-2:#5a5852; --ink-3:#8a8880;
  --line:#e4e1d9; --line-2:#d3cfc4; --focus:#5181c7;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
  --t-good:#e3f3e1; --t-warning:#fdf0d6; --t-serious:#fbe7dd; --t-critical:#f8e0e0;
  --t-neutral:#eceae3;
  --c-listeria:#b85f81; --c-ram:#987e0c; --c-nitrito:#5181c7;
  --t-listeria:#f5e4ea; --t-ram:#efeada; --t-nitrito:#e2eaf7;
  --shadow:0 1px 2px rgba(26,26,24,.04),0 4px 16px rgba(26,26,24,.05);
}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){
  color-scheme:dark;
  --canvas:#16171a; --surface:#1e2024; --surface-2:#262930; --surface-3:#2e323a;
  --ink:#f2f1ee; --ink-2:#b6b4ad; --ink-3:#8a8880;
  --line:#2e3138; --line-2:#3c4048; --focus:#5a8ad1;
  --t-good:#1d3320; --t-warning:#38300f; --t-serious:#3a2a20; --t-critical:#3a2224;
  --t-neutral:#2a2d33;
  --c-listeria:#c2688a; --c-ram:#a1871e; --c-nitrito:#5a8ad1;
  --t-listeria:#33222a; --t-ram:#2f2a17; --t-nitrito:#1f2a3b;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 4px 16px rgba(0,0,0,.24);
}}
:root[data-theme=dark]{
  color-scheme:dark;
  --canvas:#16171a; --surface:#1e2024; --surface-2:#262930; --surface-3:#2e323a;
  --ink:#f2f1ee; --ink-2:#b6b4ad; --ink-3:#8a8880;
  --line:#2e3138; --line-2:#3c4048; --focus:#5a8ad1;
  --t-good:#1d3320; --t-warning:#38300f; --t-serious:#3a2a20; --t-critical:#3a2224;
  --t-neutral:#2a2d33;
  --c-listeria:#c2688a; --c-ram:#a1871e; --c-nitrito:#5a8ad1;
  --t-listeria:#33222a; --t-ram:#2f2a17; --t-nitrito:#1f2a3b;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 4px 16px rgba(0,0,0,.24);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--canvas);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.bar{position:sticky;top:0;z-index:30;background:color-mix(in srgb,var(--canvas) 88%,transparent);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.bar-in{max-width:1460px;margin:0 auto;padding:14px 24px;display:flex;gap:18px;
  align-items:center;flex-wrap:wrap}
.brand{font-size:16px;font-weight:640;letter-spacing:-.01em;margin:0}
.brand small{display:block;font-size:12px;font-weight:400;color:var(--ink-3);
  letter-spacing:0;margin-top:1px}
.spacer{flex:1}
.wrap{max-width:1460px;margin:0 auto;padding:22px 24px 80px}
.seg{display:inline-flex;gap:3px;background:var(--surface-2);border:1px solid var(--line);
  border-radius:11px;padding:3px;flex-wrap:wrap}
.seg button{background:transparent;border:0;color:var(--ink-2);padding:8px 15px;
  border-radius:8px;cursor:pointer;font:inherit;font-size:13.5px;font-weight:550;
  white-space:nowrap}
.seg button:hover{color:var(--ink)}
.seg button[aria-selected=true]{background:var(--surface);color:var(--ink);
  box-shadow:0 1px 2px rgba(0,0,0,.07)}
.icobtn{background:var(--surface);border:1px solid var(--line);color:var(--ink-2);
  width:36px;height:36px;border-radius:10px;cursor:pointer;font-size:15px;line-height:1}
.icobtn:hover{color:var(--ink);border-color:var(--line-2)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;
  padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow)}
.card h2{margin:0 0 3px;font-size:15px;font-weight:620;letter-spacing:-.005em}
.card .lead{color:var(--ink-2);font-size:13px;margin:0 0 14px}
label.fld{display:block;font-size:11.5px;font-weight:620;letter-spacing:.05em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:6px}
textarea,input[type=text],select{width:100%;background:var(--surface-2);color:var(--ink);
  border:1px solid var(--line);border-radius:10px;padding:11px 13px;font:inherit;font-size:14px}
textarea{min-height:150px;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;
  line-height:1.5;resize:vertical}
textarea:focus,input:focus,select:focus{outline:2px solid var(--focus);outline-offset:-1px;
  border-color:transparent}
.toolbar{display:grid;grid-template-columns:minmax(220px,1.6fr) minmax(150px,1fr) auto;
  gap:12px;align-items:end}
@media(max-width:760px){.toolbar{grid-template-columns:1fr}}
.acts{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin-top:14px}
.btn{background:var(--ink);color:var(--canvas);border:0;padding:10px 20px;border-radius:10px;
  cursor:pointer;font:inherit;font-size:14px;font-weight:600}
.btn:hover{opacity:.88}
.btn.ghost{background:transparent;color:var(--ink-2);border:1px solid var(--line)}
.btn.ghost:hover{color:var(--ink);border-color:var(--line-2)}
.kbd{font-size:11.5px;color:var(--ink-3)}
.switch{display:inline-flex;gap:8px;align-items:center;font-size:13.5px;color:var(--ink-2);
  cursor:pointer;white-space:nowrap;padding:10px 0}
.switch input{accent-color:var(--focus);width:15px;height:15px}
.chips{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}
.fchip{display:flex;flex-direction:column;gap:2px;background:var(--surface-2);
  border:1px solid var(--line);border-radius:11px;padding:9px 14px;cursor:pointer;
  font:inherit;text-align:left;min-width:118px;color:var(--ink)}
.fchip:hover{border-color:var(--line-2)}
.fchip[aria-pressed=true]{border-color:currentColor;box-shadow:inset 0 0 0 1px currentColor}
.fchip .nm{display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:620;
  letter-spacing:.01em}
.fchip .dot{width:9px;height:9px;border-radius:3px;background:currentColor;flex:none}
.fchip .vl{font-size:19px;font-weight:640;letter-spacing:-.02em;color:var(--ink)}
.fchip .sb{font-size:11.5px;color:var(--ink-3)}
.fchip.listeria{color:var(--c-listeria)} .fchip.ram{color:var(--c-ram)}
.fchip.nitrito{color:var(--c-nitrito)} .fchip.det{color:var(--serious)}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:13px;
  padding:13px 17px;flex:1 1 130px;min-width:130px;max-width:230px;box-shadow:var(--shadow)}
.tile b{display:block;font-size:25px;font-weight:640;letter-spacing:-.025em;line-height:1.15}
.tile span{font-size:11.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.05em}
.plot{display:grid;grid-template-columns:auto 1fr auto;gap:9px 12px;align-items:center;
  margin-top:6px}
.plot .lb{font-size:13px;color:var(--ink-2);white-space:nowrap}
.plot .tr{background:var(--surface-2);border-radius:4px;height:14px;overflow:hidden}
.plot .fl{height:100%;border-radius:0 4px 4px 0}
.plot .vl{font-size:13px;font-weight:620;font-variant-numeric:tabular-nums;white-space:nowrap}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface);
  box-shadow:var(--shadow)}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
/* el detalle del motivo necesita ancho para leerse: antes de aplastarlo, que la
   tabla desborde y la tarjeta haga scroll horizontal */
table.t-lotes{min-width:1180px}
td.pq{min-width:310px}
td.sec{min-width:130px}
th{background:var(--surface-2);text-align:left;padding:11px 13px;position:sticky;top:0;
  font-weight:620;font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;
  color:var(--ink-2);white-space:nowrap;border-bottom:1px solid var(--line);z-index:2}
th.s{cursor:pointer;user-select:none} th.s:hover{color:var(--ink)}
th .ar{color:var(--ink-3);font-size:10px}
td{padding:11px 13px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--surface-2)}
td.n{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.mono{font-family:ui-monospace,Consolas,monospace;font-weight:620;white-space:nowrap;
  font-size:12.5px}
.mut{color:var(--ink-3);font-size:12px}
.sec{color:var(--ink-2);font-size:12.5px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px 3px 8px;
  border-radius:20px;font-size:11.5px;font-weight:620;white-space:nowrap;
  background:var(--t-neutral);color:var(--ink)}
.chip::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--ink-3);flex:none}
.chip.BLOQUEADO{background:var(--t-critical)} .chip.BLOQUEADO::before{background:var(--critical)}
.chip.LIBERADO{background:var(--t-good)} .chip.LIBERADO::before{background:var(--good)}
.chip.SINANALISIS{background:var(--t-warning)} .chip.SINANALISIS::before{background:var(--warning)}
.chip.PNC{background:var(--t-serious)} .chip.PNC::before{background:var(--serious)}
.chip.CANDIDATOALIBERAR{background:var(--t-nitrito);color:var(--ink)}
.chip.CANDIDATOALIBERAR::before{background:var(--c-nitrito)}
.chip.SINRESULTADODELAB{background:var(--t-warning)}
.chip.SINRESULTADODELAB::before{background:var(--warning)}
.flecha{color:var(--ink-3);padding:0 6px}
.chip.NOESTAENLABASE{background:var(--t-warning)}
.chip.NOESTAENLABASE::before{background:var(--warning)}
.chip.ABIERTA{background:var(--t-critical)} .chip.ABIERTA::before{background:var(--critical)}
.chip.LIBERADA{background:var(--t-good)} .chip.LIBERADA::before{background:var(--good)}
.tag{display:inline-block;padding:1px 8px;border-radius:6px;font-size:11px;font-weight:620;
  margin:0 4px 3px 0}
.tag.listeria{background:var(--t-listeria);color:var(--c-listeria)}
.tag.ram{background:var(--t-ram);color:var(--c-ram)}
.tag.nitrito{background:var(--t-nitrito);color:var(--c-nitrito)}
.tag.det{background:var(--t-serious);color:var(--serious)}
.why{font-size:12.5px;line-height:1.5}
.why .hd{font-weight:620;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
  color:var(--ink-3)}
.note{color:var(--ink-2);font-size:12px;margin-top:3px}
.aviso{display:flex;gap:11px;background:var(--t-warning);border:1px solid var(--warning);
  border-radius:12px;padding:12px 15px;font-size:13px;margin-bottom:16px;line-height:1.5}
.aviso b{font-weight:640}
.empty{padding:46px 20px;text-align:center;color:var(--ink-3);font-size:14px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-2);margin-top:12px}
tbody tr.clic{cursor:pointer}
tbody tr.clic:hover td{background:var(--surface-2)}
tbody tr.clic:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
.bd{position:fixed;inset:0;background:rgba(10,10,12,.42);z-index:40;opacity:0;
  pointer-events:none;transition:opacity .15s}
.bd.on{opacity:1;pointer-events:auto}
.dw{position:fixed;top:0;right:0;height:100%;width:min(820px,97vw);background:var(--surface);
  border-left:1px solid var(--line);z-index:50;transform:translateX(102%);
  transition:transform .2s ease;overflow-y:auto;box-shadow:-10px 0 44px rgba(0,0,0,.20)}
.dw.on{transform:none}
.dh{position:sticky;top:0;z-index:2;background:var(--surface);border-bottom:1px solid var(--line);
  padding:16px 20px;display:flex;gap:12px;align-items:flex-start}
.dh .t{flex:1;min-width:0}
.dh .t b{font-family:ui-monospace,Consolas,monospace;font-size:15px;display:block}
.db{padding:18px 20px 70px}
.grp{margin-bottom:22px}
.grp h3{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);
  margin:0 0 9px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:13px;margin:0}
.kv dt{color:var(--ink-3);white-space:nowrap} .kv dd{margin:0}
.mini{width:100%;font-size:12.5px;border-collapse:collapse}
.mini th{position:static;background:transparent;color:var(--ink-3);font-size:10.5px;
  padding:5px 8px;border-bottom:1px solid var(--line)}
.mini td{padding:6px 8px;border-bottom:1px solid var(--line)}
.mini tr:last-child td{border-bottom:0}
.vacio{color:var(--ink-3);font-size:12.5px}
.pista{font-size:11.5px;color:var(--ink-3);margin-top:10px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px}
</style></head><body>

<div class="bar"><div class="bar-in">
  <h1 class="brand">Consulta de bloqueos<small id="sub"></small></h1>
  <div class="spacer"></div>
  <div class="seg" role="tablist" id="nav"></div>
  <button class="icobtn" id="tbtn" onclick="tema()" title="Cambiar tema">&#9681;</button>
</div></div>

<div class="bd" id="bd" onclick="cerrar()"></div>
<aside class="dw" id="dw" role="dialog" aria-modal="true" aria-label="Detalle">
  <div class="dh" id="dh"></div><div class="db" id="db"></div>
</aside>

<div class="wrap">
<div id="alerta"></div>

<section id="v-consulta">
  <div class="card">
    <h2>Consulta con packing list</h2>
    <p class="lead">Cada linea se resuelve <b>contra el laboratorio</b>, al nivel de batch que
      venga en el packing list. No interviene el stock: la pregunta es si ese lote esta liberado,
      no cuanto hay en bodega. <b>Haz clic en una fila para ver el detalle.</b> Se lee linea por linea y se busca el codigo en cualquier columna.</p>
    <label class="fld" for="pl">Contenido</label>
    <textarea id="pl" placeholder="Pega aqui el packing list, directo desde Excel o desde el PDF..."></textarea>
    <div class="acts">
      <button class="btn" onclick="correr()">Analizar</button>
      <button class="btn ghost" onclick="limpiar()">Limpiar</button>
      <span class="kbd">o Ctrl + Enter</span>
      <div class="spacer"></div>
      <button class="btn ghost" id="csvbtn" hidden onclick="csv()">Descargar CSV</button>
    </div>
  </div>
  <div id="k-consulta"></div>
  <div id="r-consulta"></div>
</section>

<section id="v-bloqueados" hidden>
  <div class="card">
    <h2>Estado de stock</h2>
    <p class="lead">Cuanto de lo que hay en bodega esta bloqueado, y por que causa. Elige una o
      mas causas; un lote puede tener varias, por eso los totales por causa no suman el total.
      <b>Haz clic en cualquier fila para ver el detalle.</b><br>
      Criterios: RAM en toda linea; nitrito en refrigerada y en bacon/wheel; Listeria en
      refrigerada y en congelada con destino EE.UU. o Costa Rica.</p>
    <div class="aviso"><span>&#9432;</span><div>Se usa el stock de <b>Fishken</b>, que registra
      el lote hasta el numero pero <b>no la letra del batch de ahumado</b>. Por eso aca un lote
      arrastra a todos sus batches: si uno solo incumple, no hay forma de separar las cajas de
      los batches conformes. Para consultar un batch puntual usa
      <b>Consulta con packing list</b>, que si trabaja a ese nivel.</div></div>
    <div class="toolbar">
      <div><label class="fld" for="f2">Buscar</label>
        <input type="text" id="f2" placeholder="Lote, producto, cliente, motivo..."
          oninput="pintaBloq()"></div>
      <div><label class="fld" for="fb">Bodega</label><select id="fb" onchange="pintaBloq()"></select></div>
      <div><label class="fld" for="fl">Linea</label><select id="fl" onchange="pintaBloq()">
        <option value="">Todas</option><option>REFRIGERADA</option><option>CONGELADA</option>
        <option value="sin clasificar">Sin clasificar</option></select></div>
      <div><label class="fld" for="fd">Destino</label><select id="fd" onchange="pintaBloq()">
        <option value="">Todos</option><option value="EE.UU.">EE.UU.</option>
        <option value="Costa Rica">Costa Rica</option><option value="no">Sin restriccion</option>
        <option value="sin determinar">Sin determinar</option></select></div>
      <div><label class="fld" for="fe">Estado</label><select id="fe" onchange="pintaBloq()">
        <option value="BLOQ">Bloqueados y PNC</option>
        <option value="CAND">Candidatos a liberar</option>
        <option value="SIN">Sin analisis</option>
        <option value="TODOS">Todos menos liberados</option></select></div>
      <label class="switch"><input type="checkbox" id="soloStock" checked onchange="pintaBloq()">
        Solo lo que esta en bodega</label>
    </div>
    <div class="chips" id="chips"></div>
  </div>
  <div id="k-bloq"></div>
  <div id="g-bloq"></div>
  <div id="r-bloq"></div>
</section>

<section id="v-buscar" hidden>
  <div class="card">
    <h2>Buscar</h2>
    <p class="lead">Busqueda libre sobre cualquier atributo del lote: codigo (con o sin el
      prefijo @ o B), nombre del producto, cliente o bodega. Incluye todos los estados, este el
      lote en bodega o no. Haz clic en un resultado para ver el detalle.</p>
    <label class="fld" for="f3">Termino</label>
    <input type="text" id="f3" placeholder="Lote, producto, cliente o bodega..."
      oninput="pintaBusca()">
  </div>
  <div id="r-buscar"></div>
</section>

<section id="v-cambios" hidden>
  <div class="card">
    <h2>Movimientos historicos</h2>
    <p class="lead">Cada vez que se corre el cruce se guarda el veredicto de cada lote y batch.
      Aca quedan las transiciones: lo que estuvo bloqueado y despues se libero, y al reves.
      La columna <b>Por que</b> distingue un cambio por resultado nuevo de uno por cambio de
      criterio. El historial empieza en la primera corrida, no reconstruye el pasado.</p>
    <div class="toolbar">
      <div><label class="fld" for="f6">Buscar</label>
        <input type="text" id="f6" placeholder="Lote, batch, estado..." oninput="pintaCambios()"></div>
      <div><label class="fld" for="fn">Nivel</label><select id="fn" onchange="pintaCambios()">
        <option value="">Todos</option><option value="lote">Lote</option>
        <option value="batch">Batch</option></select></div>
    </div>
  </div>
  <div id="k-cam"></div>
  <div id="r-cambios"></div>
</section>

<section id="v-detenciones" hidden>
  <div class="card">
    <h2>Detenciones declaradas por correo</h2>
    <p class="lead">Detenciones declaradas <b>por correo</b> ante una desviacion de proceso
      (vida util excedida, curado excedido, contaminacion fisica). Son un bloqueo <b>declarado</b>,
      no calculado: valen aunque el laboratorio no tenga resultado, y la ausencia de evidencia no
      libera. Se cierran contra un resultado de laboratorio posterior al evento que cubra el
      criterio desviado, o contra una decision de Calidad; un PNC no se libera, se dispone.
      La columna de propuesta <b>no libera nada</b>: quien firma es Calidad, en
      REGISTRO DETENCIONES.xlsx.</p>
    <div class="toolbar">
      <div><label class="fld" for="f4">Buscar</label>
        <input type="text" id="f4" placeholder="Lote, producto, ID..." oninput="pintaDet()"></div>
      <div><label class="fld" for="fd1">Estado</label><select id="fd1" onchange="pintaDet()"></select></div>
      <div><label class="fld" for="fd2">Tipo</label><select id="fd2" onchange="pintaDet()"></select></div>
    </div>
  </div>
  <div id="k-det"></div>
  <div id="r-detenciones"></div>
</section>

<section id="v-fuentes" hidden>
  <div class="card">
    <h2>Origen de datos</h2>
    <p class="lead">Cada fuente tiene su propio corte. Un lote puede faltar solo porque su bodega
      se exporto antes de que ingresara, no porque este liberado.</p>
  </div>
  <div id="r-fuentes"></div>
</section>
</div>

<script>
const D = __DATA__, L = D.lotes, MIN = 8;
const CAUSAS = [
  {k:'LISTERIA', nm:'Listeria',  c:'listeria'},
  {k:'RAM',      nm:'RAM',       c:'ram'},
  {k:'NITRITO',  nm:'Nitrito',   c:'nitrito'},
  {k:'DETENCION',nm:'Detencion', c:'det'},
];
const VIEWS = [['consulta','Consulta con packing list'],['bloqueados','Estado de stock'],
  ['buscar','Buscar'],['cambios','Movimientos historicos'],['detenciones','Detenciones'],
  ['fuentes','Origen de datos']];
let vista='consulta', sel=new Set(), ULT=[], ordB={k:'cajas',d:-1};

const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const nf=n=>Number(n||0).toLocaleString('es-CL');
const cls=e=>String(e).toUpperCase().replace(/[^A-Z]/g,'');
const chip=e=>'<span class="chip '+cls(e)+'">'+esc(e)+'</span>';
const norm=s=>String(s).trim().toUpperCase().split('*')[0].replace(/[^A-Z0-9@]/g,'');
const causasDe=o=>o.causas.concat(o.det?['DETENCION']:[]);

document.getElementById('sub').innerHTML = D.meta.lotes+' lotes &middot; '+nf(D.meta.cajas)+
  ' cajas &middot; '+nf(D.meta.batches)+' batches con resultado &middot; laboratorio hasta '+
  D.meta.corte_lab+' &middot; generado '+D.meta.fecha;
document.getElementById('nav').innerHTML = VIEWS.map(([k,n])=>
  '<button role="tab" data-v="'+k+'" aria-selected="'+(k===vista)+'" onclick="ir(\''+k+'\')">'+
  n+'</button>').join('');

function ir(v){
  vista=v;
  VIEWS.forEach(([k])=>document.getElementById('v-'+k).hidden=(k!==v));
  document.querySelectorAll('#nav button').forEach(b=>
    b.setAttribute('aria-selected', b.dataset.v===v));
  if(v==='bloqueados')pintaBloq(); if(v==='detenciones')pintaDet();
  if(v==='fuentes')pintaFuentes(); if(v==='cambios')pintaCambios();
}
function tema(){const r=document.documentElement;
  const d=r.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.dataset.theme=(d==='dark'?'light':'dark');}

// Un archivo de stock exportado mucho antes que los demas produce falsos "no esta
// en la base": se avisa arriba, no se esconde en una pestania.
(function(){
  const st=D.meta.fuentes.filter(f=>f.f==='Stock'), mx=st.map(f=>f.h).sort().pop();
  const v=st.filter(f=>(new Date(mx)-new Date(f.h))/864e5 > 7);
  if(v.length) document.getElementById('alerta').innerHTML='<div class="aviso"><span>&#9888;</span>'+
    '<div><b>Stock desactualizado en '+v.length+' bodega(s).</b> '+
    v.map(f=>esc(f.a.replace(/^FRIGOR.*?- /,'').replace(/ \(STOCK.*$/,''))+' llega hasta '+f.h)
      .join('; ')+', contra '+mx+' del resto. Lo ingresado despues no aparece aca: '+
    'un lote ausente no es un lote liberado.</div></div>';
})();

function tiles(a){return '<div class="tiles">'+a.map(([k,v])=>
  '<div class="tile"><b>'+(typeof v==='number'?nf(v):esc(v))+'</b><span>'+esc(k)+
  '</span></div>').join('')+'</div>';}

function porque(o){
  const t=[];
  causasDe(o).forEach(k=>{const c=CAUSAS.find(x=>x.k===k);
    if(c)t.push('<span class="tag '+c.c+'">'+c.nm+'</span>');});
  let h = t.length ? '<div>'+t.join('')+'</div>' : '';
  if(o.lab) h+='<div><span class="hd">Lab</span> '+esc(o.lab)+'</div>';
  if(o.det) h+='<div><span class="hd">Detencion</span> '+esc(o.det)+'</div>';
  if(o.mlib) h+='<div class="note"><b>Por que quedo asi:</b> '+esc(o.mlib)+'</div>';
  if(o.porcrit) h+='<div class="note">'+esc(o.porcrit)+
    (o.evid?' &middot; '+esc(o.evid):'')+'</div>';
  if(o.linea) h+='<div class="note">Linea '+esc(o.linea)+
    (o.dest&&o.dest!=='no'&&o.dest!=='sin determinar'?' &middot; destino '+esc(o.dest):'')+
    (o.linea.indexOf('CONGELADA')>=0&&o.linea.indexOf('REFRIGERADA')<0?
      ': no aplica nitrito'+((o.dest==='no')?' ni listeria':''):'')+'</div>';
  if(o.hrem) h+='<div class="note"><b>Re-muestreo conforme:</b> '+esc(o.hrem)+'</div>';
  if(o.libf) h+='<div class="note"><b>Liberacion declarada</b> el '+esc(o.libf)+
    (o.libm?' para '+esc(o.libm):'')+(o.libo?' ('+esc(o.libo)+')':'')+'</div>';
  if(o.batmal) h+='<div class="note">Batches no conformes: '+esc(o.batmal)+'</div>';
  if(o.obs) h+='<div class="note">'+esc(o.obs)+'</div>';
  if(!h) h='<span class="mut">Sin incumplimientos'+(o.nmue?' &middot; '+o.nmue+
    ' muestra(s) de laboratorio':'')+'.</span>';
  return '<div class="why">'+h+'</div>';
}

// ---------- packing list contra el laboratorio ----------
// El packing list trae el lote CON su letra de batch, que es la granularidad del
// LAB-REG-08. Se resuelve ahi directamente: el stock no participa de esta pregunta
// (el stock solo guarda el lote base, y esa limitacion pertenece a la otra vista).
const B = D.batches, BIDX = new Map(B.map(x => [x.n, x]));
const ORD = {'PNC':0,'BLOQUEADO':1,'CANDIDATO A LIBERAR':2,'SIN ANALISIS':3,'LIBERADO':4};

// Forma de un lote de planta: prefijo opcional @ (ASC) o B (BAP), digito de anio,
// dos letras de planta y al menos cuatro digitos. Sin esta puerta, una fecha como
// 01/07/2026 se normaliza a 01072026 y calza como si fuera un lote.
const RX_LOTE = /^[@B]?\d[A-Z]{2}\d{4,}/;
const esLote = tok => RX_LOTE.test(norm(tok)) && norm(tok).length >= MIN;

function resolver(tok){
  const q = norm(tok); if(!esLote(tok)) return null;
  // startsWith(q) incluye al propio q: si el laboratorio tiene un registro sin letra
  // de batch, no debe tapar a los batches del mismo lote. Con descendientes, la
  // respuesta correcta es el agregado; solo si esta solo es un match exacto.
  const hijos = B.filter(x => x.n.startsWith(q)).sort((a,b)=>ORD[a.estado]-ORD[b.estado]);
  if(hijos.length === 1 && hijos[0].n === q) return {nivel:'EXACTO', hits:hijos};
  if(hijos.length) return {nivel:'LOTE BASE', hits:hijos};
  // El ancestro tambien tiene que ser un codigo de lote completo: el laboratorio
  // tiene registros cortos ('010', '107') que si no, calzan con cualquier cosa.
  const padres = B.filter(x => x.n.length >= MIN && RX_LOTE.test(x.n) && q.startsWith(x.n))
    .sort((a,b) => b.n.length - a.n.length);
  if(padres.length) return {nivel:'APROXIMADO', hits:[padres[0]]};
  return null;
}
// Una linea puede traer varios tokens con forma de lote (codigo de articulo, traza).
// Se prueban todos y gana el mejor match, no el primero.
const RANK = {'EXACTO':0,'LOTE BASE':1,'APROXIMADO':2};
function resolverLinea(toks){
  const cands = toks.filter(esLote);
  let best = null;
  for(const t of cands){
    const m = resolver(t); if(!m) continue;
    const rk = RANK[m.nivel];
    if(!best || rk < best.rk){best = {nivel:m.nivel, hits:m.hits, rk:rk, tok:t};}
    if(rk === 0) break;
  }
  return {best: best, cand: best ? best.tok : (cands[0] || '')};
}
function detsDe(q){
  return D.det.filter(d => {const m = norm(d['LOTE']);
    return m.length >= MIN && (q.startsWith(m) || m.startsWith(q)) &&
      (d['ESTADO'] === 'ABIERTA' || d['ESTADO'] === 'PNC');});
}
function parecidos(tok){
  const bare = x => x.replace(/^[@B]/,''), raiz = bare(norm(tok)).slice(0,9);
  return raiz.length < 7 ? [] : B.filter(x => x.n.length >= MIN && bare(x.n).slice(0,9) === raiz)
    .slice(0,6);
}
function limpiar(){document.getElementById('pl').value=''; correr();}
document.getElementById('pl').addEventListener('keydown', e => {
  if((e.ctrlKey||e.metaKey) && e.key === 'Enter'){e.preventDefault(); correr();}});

function estadoLinea(x){
  if(!x.usado) return 'SIN LOTE';
  if(x.dts.some(d => d['ESTADO'] === 'PNC')) return 'PNC';
  if(x.r){let e = x.r.hits.map(h => h.estado).sort((a,b)=>ORD[a]-ORD[b])[0];
    // El resultado del batch vecino no libera este batch, solo puede bloquearlo.
    if(x.r.nivel === 'APROXIMADO' && e !== 'BLOQUEADO') e = 'SIN RESULTADO DE LAB';
    return (e === 'LIBERADO' && x.dts.length) ? 'BLOQUEADO' : e;}
  return x.dts.length ? 'BLOQUEADO' : 'SIN RESULTADO DE LAB';
}
function detalle(x){
  const h = [];
  if(x.r){
    const nivel = x.r.nivel, hits = x.r.hits;
    const malos = hits.filter(b => b.estado === 'BLOQUEADO' || b.estado === 'PNC');
    const cands = hits.filter(b => b.estado === 'CANDIDATO A LIBERAR');
    const relev = malos.concat(cands);
    if(nivel === 'LOTE BASE'){
      const det = [];
      if(malos.length) det.push('<b>'+malos.length+' bloquea(n)</b>');
      if(cands.length) det.push(cands.length+' con re-muestreo conforme');
      h.push('<div class="note">Pegaste el <b>lote base</b>. El laboratorio tiene '+hits.length+
        ' batch(es) de este lote'+(det.length?': '+det.join(', ')+'.':', todos conformes.')+
        '</div>');
    }
    if(nivel === 'APROXIMADO')
      h.push('<div><b>El laboratorio no tiene resultado para ese batch.</b></div>'+
        '<div class="note">Abajo va el resultado del lote mas cercano ('+esc(hits[0].b)+
        ') solo como referencia. <b>No libera este batch</b>: si sale bloqueado, se hereda el '+
        'bloqueo; si sale conforme, igual queda sin resultado propio.</div>');
    (relev.length ? relev : hits).slice(0,6).forEach(b => {
      const tg = b.causas.map(k => {const c = CAUSAS.find(y=>y.k===k);
        return c ? '<span class="tag '+c.c+'">'+c.nm+'</span>' : '';}).join('');
      h.push('<div>'+(hits.length>1?'<span class="mono">'+esc(b.b)+'</span> ':'')+tg+
        (b.lab?'<span class="hd">Lab</span> '+esc(b.lab):'')+
        (b.det?' <span class="hd">Detencion</span> '+esc(b.det):'')+
        (b.rem?'<span class="hd">Re-muestreo</span> '+esc(b.rem)+
          '<div class="note">Un re-muestreo conforme no libera solo: requiere decision '+
          'firmada de Calidad.</div>':'')+
        (b.libf?'<div class="note"><b>Liberacion declarada</b> el '+esc(b.libf)+
          (b.libm?' para '+esc(b.libm):'')+(b.libo?' ('+esc(b.libo)+')':'')+'</div>':'')+
        (!b.lab&&!b.det&&!b.rem?'<span class="mut">Conforme en '+b.nm+
          ' muestra(s).</span>':'')+'</div>');
    });
    const b0 = hits[0];
    h.push('<div class="note">'+hits.reduce((a,b)=>a+b.nm,0)+' muestra(s) de laboratorio'+
      (b0.ult?' &middot; ultima '+esc(hits.map(b=>b.ult).sort().pop()):'')+
      (b0.tipo&&b0.tipo!=='PT'?' &middot; incluye muestras tipo '+esc(b0.tipo):'')+'</div>');
  }
  x.dts.forEach(d => h.push('<div><span class="tag det">Detencion</span>'+esc(d['ID'])+' '+
    esc(d['TIPO DE DESVIACION'])+'. <span class="mut">'+esc(d['PROPUESTA DE LIBERACION'])+
    '</span></div>'));
  if(!x.r && x.usado){
    const p = parecidos(x.usado);
    h.push('<div><b>El laboratorio aun no tiene resultado para este lote.</b></div>'+
      '<div class="note">No es una liberacion: puede ser produccion posterior al corte del '+
      'registro, o el lote esta mal escrito. Verificar antes de despachar.</div>'+
      (p.length?'<div class="note">Batches parecidos: '+p.map(b=>esc(b.b)+' ('+esc(b.estado)+
      ')').join(', ')+'</div>':''));
  }
  if(!x.usado) h.push('<span class="mut">No hay ningun codigo con forma de lote. '+
    'Probablemente es una cabecera, un subtotal o un separador.</span>');
  return '<div class="why">'+h.join('')+'</div>';
}

function correr(){
  const out = [];
  for(const linea of document.getElementById('pl').value.split(/\r?\n/)){
    if(!linea.trim()) continue;
    const toks = linea.split(/[\t,;|\s]+/).filter(t => t.length >= MIN);
    const rl = resolverLinea(toks);
    out.push({linea: linea, usado: rl.cand, r: rl.best,
              dts: rl.cand ? detsDe(norm(rl.cand)) : []});
  }
  ULT = out;
  document.getElementById('csvbtn').hidden = !out.length;
  if(!out.length){document.getElementById('k-consulta').innerHTML = '';
    document.getElementById('r-consulta').innerHTML =
      '<div class="card empty">Pega un packing list y presiona Analizar.</div>'; return;}
  const c = {};
  out.forEach(x => {const e = estadoLinea(x); c[e] = (c[e]||0)+1;});
  document.getElementById('k-consulta').innerHTML = tiles([
    ['Lineas', out.length], ['Bloqueadas', c['BLOQUEADO']||0], ['PNC', c['PNC']||0],
    ['Liberadas', c['LIBERADO']||0], ['Sin analisis', c['SIN ANALISIS']||0],
    ['Sin resultado de lab', c['SIN RESULTADO DE LAB']||0], ['Sin lote', c['SIN LOTE']||0]]);

  document.getElementById('r-consulta').innerHTML =
    '<div class="tw"><table class="t-lotes"><thead><tr><th>Linea del packing list</th>'+
    '<th>Lote detectado</th><th>Match</th><th>Estado</th><th>Que dice el laboratorio</th>'+
    '<th>Presentacion</th></tr></thead><tbody>'+
    out.map(function(x, i){const e = estadoLinea(x);
      return '<tr class="clic" tabindex="0" onclick="abrirLinea('+i+')" '+
      'onkeydown="if(event.key===\'Enter\')abrirLinea('+i+')">'+
      '<td class="mut" style="max-width:250px"><div style="overflow:hidden;'+
      'text-overflow:ellipsis;white-space:nowrap" title="'+esc(x.linea)+'">'+esc(x.linea)+
      '</div></td><td class="mono">'+(x.usado?esc(x.usado):'&mdash;')+'</td>'+
      '<td class="mut">'+(x.r?esc(x.r.nivel):'&mdash;')+'</td><td>'+chip(e)+'</td>'+
      '<td class="pq">'+detalle(x)+'</td><td class="sec">'+
      esc(x.r?(x.r.hits[0].pres||'').slice(0,70):'')+'</td></tr>';}).join('')+
    '</tbody></table></div>';
}
function csv(){
  const f = ['LINEA','LOTE DETECTADO','MATCH','ESTADO','CAUSAS','MOTIVO LAB','MOTIVO DETENCION',
    'MUESTRAS','ULTIMA MUESTRA','PRESENTACION'];
  const q = v => '"'+String(v==null?'':v).replace(/"/g,'""')+'"';
  const r = [f.map(q).join(';')];
  for(const x of ULT){
    const e = estadoLinea(x), dt = x.dts.map(d=>d['ID']+' '+d['TIPO DE DESVIACION']).join(' | ');
    if(!x.r){r.push([x.linea, x.usado, '', e, '', '', dt, '', '', ''].map(q).join(';')); continue;}
    for(const b of x.r.hits) r.push([x.linea, b.b, x.r.nivel, b.estado, b.causas.join('+'),
      b.lab, b.det||dt, b.nm, b.ult, b.pres].map(q).join(';'));
  }
  const bl = new Blob(['\ufeff'+r.join('\r\n')], {type:'text/csv;charset=utf-8'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(bl);
  a.download = 'packing_list_vs_lab.csv'; a.click();
}

// ---------- bloqueados ----------
document.getElementById('fb').innerHTML='<option value="">Todas</option>'+
  D.meta.bodegas.map(b=>'<option>'+esc(b)+'</option>').join('');

const GRUPO={BLOQ:['BLOQUEADO','PNC'],CAND:['CANDIDATO A LIBERAR'],SIN:['SIN ANALISIS'],
  TODOS:['BLOQUEADO','PNC','CANDIDATO A LIBERAR','SIN ANALISIS']};
function baseBloq(){
  const g=GRUPO[document.getElementById('fe').value]||GRUPO.BLOQ;
  let d=L.filter(o=>g.includes(o.estado));
  if(document.getElementById('soloStock').checked) d=d.filter(o=>o.stock);
  const b=document.getElementById('fb').value;
  if(b) d=d.filter(o=>o.bodegas.split(' / ').includes(b));
  const li=document.getElementById('fl').value;
  if(li) d=d.filter(o=>(o.linea||'').indexOf(li)>=0);
  const de=document.getElementById('fd').value;
  if(de) d=d.filter(o=>(o.dest||'')===de);
  const f=document.getElementById('f2').value.toLowerCase().trim();
  if(f) d=d.filter(o=>(o.lote+' '+o.lab+' '+o.det+' '+o.bodegas+' '+o.prod+' '+o.cliente+' '+
    o.obs+' '+o.batmal).toLowerCase().includes(f));
  return d;
}
function toggle(k){sel.has(k)?sel.delete(k):sel.add(k);pintaBloq();}
function pintaBloq(){
  const base=baseBloq();
  document.getElementById('chips').innerHTML=CAUSAS.map(c=>{
    const m=base.filter(o=>causasDe(o).concat(o.rem||[]).includes(c.k));
    return '<button class="fchip '+c.c+'" aria-pressed="'+sel.has(c.k)+'" onclick="toggle(\''+
      c.k+'\')"><span class="nm"><i class="dot"></i>'+c.nm+'</span><span class="vl">'+
      nf(m.reduce((s,x)=>s+x.cajas,0))+'</span><span class="sb">cajas &middot; '+m.length+
      ' lotes</span></button>';}).join('');
  const d = sel.size ? base.filter(o=>causasDe(o).concat(o.rem||[]).some(k=>sel.has(k))) : base;
  document.getElementById('k-bloq').innerHTML=tiles([['Lotes',d.length],
    ['Cajas',d.reduce((s,x)=>s+x.cajas,0)],
    ['Kg netos',Math.round(d.reduce((s,x)=>s+x.kg,0))],
    ['Piezas',d.reduce((s,x)=>s+x.pz,0)]]);

  // magnitud por causa: barras horizontales, una por causa, rotuladas directamente
  const filas=CAUSAS.map(c=>{const m=base.filter(o=>causasDe(o).concat(o.rem||[]).includes(c.k));
    return {c,cajas:m.reduce((s,x)=>s+x.cajas,0),lotes:m.length};})
    .filter(x=>x.cajas||x.lotes).sort((a,b)=>b.cajas-a.cajas);
  const mx=Math.max(1,...filas.map(f=>f.cajas));
  document.getElementById('g-bloq').innerHTML = filas.length ? '<div class="card">'+
    '<h2>Cajas en bodega por causa</h2>'+
    '<p class="lead">Un lote con dos causas se cuenta en ambas barras.</p><div class="plot">'+
    filas.map(f=>'<span class="lb">'+f.c.nm+'</span><div class="tr"><div class="fl" style="width:'+
      Math.max(2,100*f.cajas/mx)+'%;background:var(--c-'+f.c.c+')"></div></div>'+
      '<span class="vl">'+nf(f.cajas)+' <span class="mut">('+f.lotes+' lotes)</span></span>')
    .join('')+'</div></div>' : '';

  d.sort((a,b)=>{const k=ordB.k,x=a[k],y=b[k];
    return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*ordB.d;});
  document.getElementById('r-bloq').innerHTML=tabla(d);
}
function ord(k){ordB = ordB.k===k?{k,d:-ordB.d}:{k,d:-1}; pintaBloq();}
function th(k,n,al){return '<th class="s'+(al?' ':'')+'" onclick="ord(\''+k+'\')"'+
  (al?' style="text-align:right"':'')+'>'+n+(ordB.k===k?' <span class="ar">'+
  (ordB.d<0?'&#9660;':'&#9650;')+'</span>':'')+'</th>';}
function tabla(d,plano){
  if(!d.length)return '<div class="card empty">Sin resultados con estos filtros.</div>';
  const H = plano ? '<th>Lote</th><th>Estado</th><th>Por que</th><th>Producto</th>'+
      '<th>Cliente</th><th>Bodega</th><th style="text-align:right">Cajas</th>'+
      '<th style="text-align:right">Kg</th>'
    : th('lote','Lote')+th('estado','Estado')+'<th>Por que</th>'+th('prod','Producto')+
      th('cliente','Cliente')+th('bodegas','Bodega')+th('cajas','Cajas',1)+th('kg','Kg',1);
  return '<div class="tw"><table class="t-lotes"><thead><tr>'+H+'</tr></thead><tbody>'+d.map(o=>
    '<tr class="clic" tabindex="0" onclick="abrirLote(\''+o.n+'\')" '+
    'onkeydown="if(event.key===\'Enter\')abrirLote(\''+o.n+'\')">'+
    '<td class="mono">'+esc(o.lote)+(o.stock?'':'<div class="mut">no esta en bodega</div>')+
    (o.ult?'<div class="mut">lab '+esc(o.ult)+'</div>':'')+'</td><td>'+chip(o.estado)+
    '</td><td class="pq">'+porque(o)+'</td><td class="sec">'+esc(o.prod.slice(0,80))+
    '</td><td class="sec">'+esc(o.cliente.slice(0,50))+'</td><td class="sec">'+esc(o.bodegas)+
    '</td><td class="n">'+nf(o.cajas)+'</td><td class="n">'+nf(o.kg)+'</td></tr>').join('')+
    '</tbody></table></div>';
}

// ---------- buscar ----------
function pintaBusca(){
  const f=document.getElementById('f3').value.toLowerCase().trim();
  if(f.length<2){document.getElementById('r-buscar').innerHTML=
    '<div class="card empty">Escribe al menos 2 caracteres.</div>';return;}
  const d=L.filter(o=>(o.lote+' '+o.prod+' '+o.cliente+' '+o.bodegas).toLowerCase().includes(f))
    .sort((a,b)=>b.cajas-a.cajas);
  document.getElementById('r-buscar').innerHTML=d.length?tabla(d,1):
    '<div class="card empty">Sin coincidencias.</div>';
}

// ---------- detenciones ----------
const uniq=k=>[...new Set(D.det.map(x=>x[k]).filter(Boolean))].sort();
document.getElementById('fd1').innerHTML='<option value="">Todos</option>'+
  uniq('ESTADO').map(v=>'<option>'+esc(v)+'</option>').join('');
document.getElementById('fd2').innerHTML='<option value="">Todos</option>'+
  uniq('TIPO DE DESVIACION').map(v=>'<option>'+esc(v)+'</option>').join('');
function pintaDet(){
  const f=document.getElementById('f4').value.toLowerCase().trim();
  const e=document.getElementById('fd1').value, t=document.getElementById('fd2').value;
  let d=D.det;
  if(e) d=d.filter(x=>x['ESTADO']===e);
  if(t) d=d.filter(x=>x['TIPO DE DESVIACION']===t);
  if(f) d=d.filter(x=>Object.values(x).join(' ').toLowerCase().includes(f));
  const ab=d.filter(x=>x['ESTADO']==='ABIERTA').length;
  document.getElementById('k-det').innerHTML=tiles([['Detenciones',d.length],['Abiertas',ab],
    ['PNC',d.filter(x=>x['ESTADO']==='PNC').length],
    ['Liberables hoy',d.filter(x=>/LIBERABLE segun lab/.test(x['PROPUESTA DE LIBERACION'])).length]]);
  document.getElementById('r-detenciones').innerHTML = d.length ?
    '<div class="tw"><table><thead><tr><th>ID</th><th>Correo</th><th>Tipo</th><th>Lote</th>'+
    '<th>Producto</th><th>Alcance</th><th>Evento</th><th>Criterios</th><th>Estado</th>'+
    '<th>Propuesta</th></tr></thead><tbody>'+d.map(x=>'<tr class="clic" tabindex="0" '+
    'onclick="abrirDetencion(\''+x['ID']+'\')"><td class="mono">'+esc(x['ID'])+
    '</td><td class="sec">'+esc(String(x['FECHA CORREO']).slice(0,10))+'</td><td class="sec">'+
    esc(x['TIPO DE DESVIACION'])+'</td><td class="mono">'+esc(x['LOTE'])+'</td><td class="sec">'+
    esc(x['PRODUCTO'])+'</td><td class="sec">'+esc(x['ALCANCE'])+'</td><td class="sec">'+
    esc(String(x['FECHA DEL EVENTO']).slice(0,10))+'</td><td class="sec">'+
    esc(x['CRITERIOS DE LIBERACION'])+'</td><td>'+chip(x['ESTADO'])+'</td><td class="sec">'+
    esc(x['PROPUESTA DE LIBERACION'])+'</td></tr>').join('')+'</tbody></table></div>'
    : '<div class="card empty">Sin detenciones con estos filtros.</div>';
}

// ---------- panel de detalle ----------
function cerrar(){document.getElementById('bd').classList.remove('on');
  document.getElementById('dw').classList.remove('on');}
addEventListener('keydown', e => {if(e.key === 'Escape') cerrar();});
function abrir(tit, sub, est, html){
  document.getElementById('dh').innerHTML = '<div class="t"><b>'+esc(tit)+'</b>'+
    '<span class="mut">'+esc(sub)+'</span></div>'+(est?chip(est):'')+
    '<button class="icobtn" onclick="cerrar()" aria-label="Cerrar">&times;</button>';
  document.getElementById('db').innerHTML = html;
  document.getElementById('bd').classList.add('on');
  document.getElementById('dw').classList.add('on');
  document.getElementById('dw').scrollTop = 0;
}
const grp = (t, c) => '<div class="grp"><h3>'+t+'</h3>'+(c||'<div class="vacio">Sin datos.</div>')+
  '</div>';
const kv = a => '<dl class="kv">'+a.filter(x=>x[1]!=null&&x[1]!=='')
  .map(x=>'<dt>'+esc(x[0])+'</dt><dd>'+x[1]+'</dd>').join('')+'</dl>';
const mini = (h, r) => r.length ? '<table class="mini"><thead><tr>'+
  h.map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>'+
  r.map(f=>'<tr>'+f.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table>' : '';

const emparenta = (a, b) => a.length>=MIN && b.length>=MIN &&
  (a.startsWith(b) || b.startsWith(a));
const batchesDe = n => B.filter(x => emparenta(x.n, n));
const detsDeLote = n => D.det.filter(d => emparenta(norm(d['LOTE']), n));
const cambiosDe = k => D.cambios.filter(x => x.clave === k);

function histHtml(k){
  const c = cambiosDe(k);
  return mini(['Corrida','Cambio','Por que'], c.map(x=>[esc(x.corrida),
    chip(x.de)+'<span class="flecha">&rarr;</span>'+chip(x.a),
    x.regla==='SI'?'cambio de criterio':x.regla==='NO'?'resultado de lab':
      '<span class="mut">sin registro</span>']));
}
function critHtml(txt){
  if(!txt) return '';
  return mini(['Criterio','Estado'], txt.split(';').map(x=>{
    const [a,b] = x.split('='); return ['<b>'+esc((a||'').trim())+'</b>', esc((b||'').trim())];}));
}

function abrirLote(n){
  const o = L.find(x => x.n === n); if(!o) return;
  const bs = batchesDe(n), dts = detsDeLote(n);
  abrir(o.lote, (o.linea||'')+(o.dest&&o.dest!=='no'?' · destino '+o.dest:'')+
    (o.stock?' · '+nf(o.cajas)+' cajas':' · no esta en bodega'), o.estado,
    grp('Por que esta asi', (o.mlib?'<div style="margin-bottom:8px">'+esc(o.mlib)+'</div>':'')+
      (o.lab?'<div class="mot">LAB '+esc(o.lab)+'</div>':'')+
      (o.det?'<div class="mot">DETENCION '+esc(o.det)+'</div>':'')+
      (o.hrem?'<div class="note">Re-muestreo conforme: '+esc(o.hrem)+'</div>':'')+
      critHtml(o.porcrit)+(o.evid?'<div class="pista">Evidencia: '+esc(o.evid)+'</div>':''))+
    grp('Batches del laboratorio ('+bs.length+')', mini(['Batch','Estado','Detalle','Muestras'],
      bs.map(b=>['<span class="mono">'+esc(b.b)+'</span>', chip(b.estado),
        esc(b.lab||b.rem||b.det||'conforme'), b.nm]))) +
    grp('En bodega', o.stock ? kv([['Cajas', nf(o.cajas)],['Kg netos', nf(o.kg)],
        ['Piezas', nf(o.pz)],['OF', esc(o.of)],['Clientes', esc(o.cliente)]])+
        mini(['Bodega','Cajas','Kg'], (o.bod||[]).map(b=>[esc(b[0]), nf(b[1]), nf(b[2])]))+
        mini(['Producto','Cajas'], (o.prd||[]).map(b=>[esc(b[0]), nf(b[1])]))
      : '<div class="vacio">Este lote no aparece en ningun stock.</div>')+
    grp('Detenciones ('+dts.length+')', mini(['ID','Tipo','Estado','Propuesta'],
      dts.map(d=>[esc(d['ID']), esc(d['TIPO DE DESVIACION']), chip(d['ESTADO']),
        esc(d['PROPUESTA DE LIBERACION'])])))+
    (o.libf ? grp('Liberacion declarada', kv([['Fecha', esc(o.libf)],
      ['Mercados', esc(o.libm)],['Fuente', esc(o.libo)]])) : '')+
    grp('Historial de este lote', histHtml(n))+
    (o.obs ? grp('Observaciones', '<div class="note">'+esc(o.obs)+'</div>') : ''));
}

function abrirBatch(n){
  const b = BIDX.get(n) || B.find(x => x.n === n); if(!b) return;
  const lote = L.find(x => emparenta(x.n, n));
  abrir(b.b, (b.linea||'')+' · '+b.nm+' muestra(s)'+(b.ult?' · ultima '+b.ult:''), b.estado,
    grp('Veredicto del laboratorio',
      (b.lab?'<div class="mot">'+esc(b.lab)+'</div>':'')+
      (b.det?'<div class="mot">DETENCION '+esc(b.det)+'</div>':'')+
      (b.rem?'<div class="note"><b>Re-muestreo conforme:</b> '+esc(b.rem)+
        '<br>No libera solo: requiere decision firmada de Calidad.</div>':'')+
      (!b.lab&&!b.det&&!b.rem?'<div class="vacio">Sin incumplimientos vigentes.</div>':''))+
    grp('Muestra', kv([['Presentacion', esc(b.pres)],['Tipo', esc(b.tipo)],
      ['Observacion del lab', esc(b.obs)],['Muestras', b.nm],['Ultima', esc(b.ult)]]))+
    (b.libf ? grp('Liberacion declarada', kv([['Fecha', esc(b.libf)],
      ['Mercados', esc(b.libm)],['Fuente', esc(b.libo)]])) : '')+
    grp('Historial de este batch', histHtml(n))+
    (lote ? grp('Lote en bodega', '<button class="btn ghost" onclick="abrirLote(\''+
      lote.n+'\')">Ver '+esc(lote.lote)+' ('+nf(lote.cajas)+' cajas)</button>') : ''));
}

function abrirDetencion(id){
  const d = D.det.find(x => x['ID'] === id); if(!d) return;
  const n = norm(d['LOTE']), lote = L.find(x => emparenta(x.n, n));
  abrir(d['ID'], esc(d['LOTE'])+' · '+esc(d['TIPO DE DESVIACION']), d['ESTADO'],
    grp('Detencion', kv([['Lote', esc(d['LOTE'])],['Producto', esc(d['PRODUCTO'])],
      ['Alcance', esc(d['ALCANCE'])],['Fecha del correo', esc(String(d['FECHA CORREO']).slice(0,10))],
      ['Fecha del evento', esc(String(d['FECHA DEL EVENTO']).slice(0,10))],
      ['Criterios de liberacion', esc(d['CRITERIOS DE LIBERACION'])]]))+
    grp('Propuesta del sistema', '<div class="note">'+esc(d['PROPUESTA DE LIBERACION'])+
      '<br>La propuesta no libera: la liberacion la firma Calidad en el registro.</div>')+
    (lote ? grp('Lote', '<button class="btn ghost" onclick="abrirLote(\''+lote.n+
      '\')">Ver '+esc(lote.lote)+'</button>') : ''));
}

function abrirLinea(i){
  const x = ULT[i]; if(!x) return;
  if(x.r && x.r.hits.length === 1) return abrirBatch(x.r.hits[0].n);
  if(x.r) return abrirLote((L.find(o => emparenta(o.n, norm(x.usado))) || {}).n ||
    x.r.hits[0].n) || abrirBatch(x.r.hits[0].n);
  abrir(x.usado || 'Sin lote', 'Linea del packing list', estadoLinea(x),
    grp('Linea pegada', '<div class="mut mono">'+esc(x.linea)+'</div>')+
    grp('Resultado', detalle(x)));
}

// ---------- cambios entre corridas ----------
function pintaCambios(){
  const f=document.getElementById('f6').value.toLowerCase().trim();
  const nv=document.getElementById('fn').value;
  let d=D.cambios;
  if(nv) d=d.filter(x=>x.nivel===nv);
  if(f) d=d.filter(x=>(x.clave+' '+x.de+' '+x.a+' '+x.causas).toLowerCase().includes(f));
  const lib=d.filter(x=>(x.de==='BLOQUEADO'||x.de==='PNC')&&
    (x.a==='LIBERADO'||x.a==='CANDIDATO A LIBERAR')).length;
  const blo=d.filter(x=>x.de!=='BLOQUEADO'&&(x.a==='BLOQUEADO'||x.a==='PNC')).length;
  document.getElementById('k-cam').innerHTML=tiles([['Cambios',d.length],
    ['Salieron de bloqueo',lib],['Entraron a bloqueo',blo],
    ['Corridas',new Set(D.cambios.map(x=>x.corrida)).size]]);
  document.getElementById('r-cambios').innerHTML = d.length ?
    '<div class="tw"><table><thead><tr><th>Corrida</th><th>Nivel</th><th>Lote o batch</th>'+
    '<th>Cambio</th><th>Causas</th><th>Por que</th><th style="text-align:right">Cajas</th>'+
    '</tr></thead><tbody>'+
    d.map(x=>'<tr class="clic" tabindex="0" onclick="'+(x.nivel==='batch'?'abrirBatch':'abrirLote')+
    '(\''+x.clave+'\')"><td class="sec">'+esc(x.corrida)+'</td><td class="sec">'+esc(x.nivel)+
    '</td><td class="mono">'+esc(x.clave)+'</td><td>'+chip(x.de)+
    '<span class="flecha">&rarr;</span>'+chip(x.a)+'</td><td class="sec">'+esc(x.causas)+
    '</td><td class="sec">'+(x.regla==='SI'?'<b>cambio de criterio</b>':
      x.regla==='NO'?'resultado de lab':'<span class="mut">sin registro</span>')+
    '</td><td class="n">'+nf(x.cajas)+'</td></tr>').join('')+'</tbody></table></div>'
    : '<div class="card empty">Todavia no hay cambios registrados. Se van a listar aca '+
      'a medida que corras el cruce y el veredicto de algun lote cambie.</div>';
}

// ---------- fuentes ----------
function pintaFuentes(){
  document.getElementById('r-fuentes').innerHTML='<div class="tw"><table><thead><tr>'+
    '<th>Fuente</th><th>Archivo u hoja</th><th style="text-align:right">Registros</th>'+
    '<th>Datos hasta</th></tr></thead><tbody>'+D.meta.fuentes.map(f=>'<tr><td><b>'+esc(f.f)+
    '</b></td><td class="sec">'+esc(f.a)+'</td><td class="n">'+nf(f.n)+'</td>'+
    '<td class="mono">'+esc(f.h)+'</td></tr>').join('')+'</tbody></table></div>';
}
correr();
</script></body></html>
"""

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(HTML.replace("__DATA__", DATA))
print("Creado:", OUT, "|", len(lotes), "lotes |", os.path.getsize(OUT) // 1024, "KB")
