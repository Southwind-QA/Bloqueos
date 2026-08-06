# -*- coding: utf-8 -*-
"""Port en Python del validador de paletas de la skill dataviz (mismas formulas y
umbrales: banda OKLCH L, piso de croma, delta-E OKLab con simulacion Machado 2009,
piso de vision normal y contraste WCAG contra la superficie)."""
import math
import itertools
import sys

BAND = {"light": (0.43, 0.77), "dark": (0.48, 0.67)}
CHROMA_FLOOR = 0.10
CVD_TARGET, CVD_FLOOR = 8.0, 6.0
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0

MACHADO = {
    "protan": [[0.152286, 1.052583, -0.204868],
               [0.114503, 0.786281, 0.099216],
               [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968],
               [0.280085, 0.672501, 0.047413],
               [-0.011820, 0.042940, 0.968881]],
    "tritan": [[1.255528, -0.076749, -0.178779],
               [-0.078411, 0.930809, 0.147602],
               [0.004733, 0.691367, 0.303900]],
}


def hex2srgb(h):
    h = h.strip().lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def s2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin(h):
    return [s2lin(c) for c in hex2srgb(h)]


def rel_lum(h):
    r, g, b = lin(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    x, y = sorted([rel_lum(a), rel_lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


def oklab_from_lin(rgb):
    r, g, b = rgb
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklch(h):
    L, a, b = oklab_from_lin(lin(h))
    return L, math.hypot(a, b)


def simulate(h, kind):
    r, g, b = lin(h)
    M = MACHADO[kind]
    return [min(1, max(0, M[i][0] * r + M[i][1] * g + M[i][2] * b)) for i in range(3)]


def dE(h1, h2, kind=None):
    a = oklab_from_lin(simulate(h1, kind) if kind else lin(h1))
    b = oklab_from_lin(simulate(h2, kind) if kind else lin(h2))
    return 100 * math.dist(a, b)


def validate(pal, mode="light", surface=None, pairs="adjacent"):
    surface = surface or ("#fcfcfb" if mode == "light" else "#1a1a19")
    lo, hi = BAND[mode]
    rep, ok = [], True

    off = [(c, round(oklch(c)[0], 3)) for c in pal if not (lo <= oklch(c)[0] <= hi)]
    ok &= not off
    rep.append(("Lightness band", "PASS" if not off else "FAIL",
                f"fuera de banda: {off}" if off else f"los {len(pal)} dentro de L {lo}-{hi}"))

    lowc = [(c, round(oklch(c)[1], 3)) for c in pal if oklch(c)[1] < CHROMA_FLOOR]
    ok &= not lowc
    rep.append(("Chroma floor", "PASS" if not lowc else "FAIL",
                f"bajo el piso (lee gris): {lowc}" if lowc else f"los {len(pal)} >= {CHROMA_FLOOR}"))

    n = len(pal)
    pl = (list(itertools.combinations(range(n), 2)) if pairs == "all"
          else [(i, i + 1) for i in range(n - 1)])
    worst = min(((dE(pal[i], pal[j], k), k, pal[i], pal[j])
                 for k in ("protan", "deutan") for i, j in pl), default=(99, "", "", ""))
    tri = min((dE(pal[i], pal[j], "tritan") for i, j in pl), default=99)
    st = "PASS" if worst[0] >= CVD_TARGET else ("WARN" if worst[0] >= CVD_FLOOR else "FAIL")
    ok &= st != "FAIL"
    rep.append(("CVD separation", st,
                f"peor {pairs} {worst[3]}<->{worst[2]} dE {worst[0]:.1f} ({worst[1]}) - tritan {tri:.1f}"))

    nw = min(((dE(pal[i], pal[j]), pal[i], pal[j]) for i, j in pl), default=(99, "", ""))
    st2 = "PASS" if nw[0] >= NORMAL_FLOOR else "FAIL"
    ok &= st2 == "PASS"
    rep.append(("Normal-vision floor", st2, f"peor {pairs} {nw[2]}<->{nw[1]} dE {nw[0]:.1f}"))

    low = [(c, round(contrast(c, surface), 2)) for c in pal if contrast(c, surface) < CONTRAST_MIN]
    rep.append(("Contrast vs surface", "WARN" if low else "PASS",
                f"bajo {CONTRAST_MIN}:1, exige rotulo visible: {low}" if low
                else f"los {len(pal)} >= {CONTRAST_MIN}:1"))
    return rep, ok


def informe(pal, mode, surface, pairs="all"):
    rep, ok = validate(pal, mode, surface, pairs)
    print(f"\n{mode.upper()} sobre {surface} | {len(pal)} slots | pares: {pairs}")
    for n, s, d in rep:
        print(f"  [{s:4s}] {n:22s} {d}")
    print("  =>", "TODO PASA" if ok else "FALLA")
    return ok


if __name__ == "__main__":
    pal = [c.strip() for c in sys.argv[1].split(",") if c.strip()]
    informe(pal, sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "all")
