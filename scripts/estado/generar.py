#!/usr/bin/env python3
"""Genera el panel de estado del proyecto (una sola página HTML, sin dependencias).

Lee PRs, issues, revisiones y commits de la API REST de GitHub, cruza con
scripts/estado/equipo.json y scripts/estado/notas.json, y escribe site/index.html.
No hace commits ni modifica el repositorio.

Uso:
    python scripts/estado/generar.py --salida site
    python scripts/estado/generar.py --salida site --demo     # datos inventados, para probar el diseño
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
API = "https://api.github.com"


# ----------------------------------------------------------------- GitHub --
def _pedir(url: str, token: str | None, datos: bytes | None = None):
    cab = {"Accept": "application/vnd.github+json", "User-Agent": "panel-estado"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=datos, headers=cab)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), r.headers.get("Link", "")


def paginar(ruta: str, token: str | None):
    """Devuelve todos los elementos de un endpoint paginado."""
    url = f"{API}{ruta}{'&' if '?' in ruta else '?'}per_page=100"
    salida = []
    while url:
        datos, link = _pedir(url, token)
        salida.extend(datos)
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        url = m.group(1) if m else None
    return salida


def leer_project(notas: dict, token: str | None) -> dict[int, str]:
    """Estado (columna) de cada issue/PR en el Project. Opcional: necesita PROJECT_TOKEN."""
    if not token:
        return {}
    cfg = notas.get("project") or {}
    if not cfg.get("numero"):
        return {}
    tipo = "organization" if cfg.get("tipo", "organization") == "organization" else "user"
    consulta = (
        "query($o:String!,$n:Int!){%s(login:$o){projectV2(number:$n){items(first:100){nodes{"
        "content{... on Issue{number} ... on PullRequest{number}} "
        'fieldValueByName(name:"Status"){... on ProjectV2ItemFieldSingleSelectValue{name}}}}}}}' % tipo
    )
    cuerpo = json.dumps({"query": consulta, "variables": {"o": cfg["propietario"], "n": cfg["numero"]}}).encode()
    try:
        datos, _ = _pedir(f"{API}/graphql", token, cuerpo)
        nodos = datos["data"][tipo]["projectV2"]["items"]["nodes"]
    except Exception as e:  # el panel sigue funcionando sin el Project
        print(f"aviso: no se pudo leer el Project ({e})", file=sys.stderr)
        return {}
    res = {}
    for n in nodos:
        num = (n.get("content") or {}).get("number")
        est = (n.get("fieldValueByName") or {}).get("name")
        if num and est:
            res[num] = est
    return res


def descargar(repo: str, token: str | None):
    prs_raw = paginar(f"/repos/{repo}/pulls?state=all", token)
    issues_raw = [i for i in paginar(f"/repos/{repo}/issues?state=all", token) if "pull_request" not in i]
    revisiones = {}
    for p in prs_raw:
        try:
            revisiones[p["number"]] = paginar(f"/repos/{repo}/pulls/{p['number']}/reviews", token)
        except urllib.error.HTTPError:
            revisiones[p["number"]] = []
    try:
        commits = paginar(f"/repos/{repo}/commits?sha=main", token)
    except urllib.error.HTTPError:
        commits = []
    colab = []  # cada fuente es opcional: si el token no alcanza, se ignora
    for ruta in (f"/repos/{repo}/collaborators", f"/orgs/{repo.split('/')[0]}/members"):
        try:
            colab += [c["login"] for c in paginar(ruta, token)]
        except Exception:
            pass
    colab = sorted(set(colab))
    return prs_raw, issues_raw, revisiones, commits, colab


def nombres_reales(logins, token):
    res = {}
    for l in logins:
        try:
            d, _ = _pedir(f"{API}/users/{l}", token)
            res[l.lower()] = d.get("name") or l
        except Exception:
            res[l.lower()] = l
    return res


# ---------------------------------------------------------------- Proceso --
CIERRA = re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.I)


def estado_pr(p: dict, revs: list[dict]) -> str:
    if p.get("merged_at"):
        return "fusionado"
    if p["state"] == "closed":
        return "cerrado"
    if p.get("draft"):
        return "borrador"
    ultimo = {}
    for r in sorted(revs, key=lambda r: r.get("submitted_at") or ""):
        if r["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            ultimo[(r.get("user") or {}).get("login")] = r["state"]
    vals = set(ultimo.values())
    if "CHANGES_REQUESTED" in vals:
        return "cambios"
    if "APPROVED" in vals:
        return "aprobado"
    return "espera"


ALIAS = {"engine": "Engine", "topologias": "Topologías", "topologías": "Topologías", "metricas": "Métricas",
         "métricas": "Métricas", "ui": "UI", "config": "Config"}


def equipo_de(texto: str):
    t = texto.lower()
    for clave, nombre in ALIAS.items():
        if re.search(rf"(?<![a-z]){clave}(?![a-z])", t):
            return nombre
    return None


def construir_roster(equipo, prs_raw, issues_raw, commits, colaboradores, nombres):
    """Lista de integrantes: equipo.json (si existe) + colaboradores + asignados + autores de PR y commits."""
    roster = {}
    excluir = {x.lower() for x in equipo.get("excluir", [])}
    for m in equipo.get("integrantes", []):
        if not m["login"].startswith("usuario-ejemplo"):
            roster[m["login"].lower()] = dict(m)
    votos = defaultdict(Counter)
    vistos = set(colaboradores)
    for p in prs_raw:
        a = (p.get("user") or {}).get("login")
        if a:
            vistos.add(a)
            e = equipo_de(p["head"]["ref"])
            if e:
                votos[a.lower()][e] += 1
    for i in issues_raw:
        for a in i.get("assignees", []):
            vistos.add(a["login"])
            for l in i.get("labels", []):
                e = equipo_de(l["name"])
                if e:
                    votos[a["login"].lower()][e] += 1
    for c in commits:
        a = (c.get("author") or {}).get("login")
        if a:
            vistos.add(a)
    for a in vistos:
        if a.endswith("[bot]") or a.lower() in roster or a.lower() in excluir:
            continue
        v = votos.get(a.lower())
        roster[a.lower()] = {"login": a, "nombre": nombres.get(a.lower(), a),
                             "equipo": v.most_common(1)[0][0] if v else "Sin equipo", "lider": False}
    for k, m in roster.items():  # completa los que vienen de equipo.json sin nombre/equipo
        m.setdefault("nombre", nombres.get(k, m["login"]))
        if not m.get("equipo"):
            v = votos.get(k)
            m["equipo"] = v.most_common(1)[0][0] if v else "Sin equipo"
    return roster


def procesar(prs_raw, issues_raw, revisiones, commits, equipo, notas, proyecto, colaboradores=(), nombres=None):
    roster = construir_roster(equipo, prs_raw, issues_raw, commits, list(colaboradores), nombres or {})

    prs = []
    for p in prs_raw:
        revs = revisiones.get(p["number"], [])
        autor = (p.get("user") or {}).get("login", "?")
        cuerpo = p.get("body") or ""
        prs.append({
            "n": p["number"], "titulo": p["title"], "autor": autor, "url": p["html_url"],
            "estado": estado_pr(p, revs), "rama": p["head"]["ref"],
            "creado": p["created_at"], "fusionado": p.get("merged_at"),
            "cierra": sorted({int(x) for x in CIERRA.findall(cuerpo)}),
            "revisores": sorted({(r.get("user") or {}).get("login") for r in revs
                                 if r["state"] in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED")} - {autor, None}),
            "columna": proyecto.get(p["number"]),
        })

    issues = []
    for i in issues_raw:
        issues.append({
            "n": i["number"], "titulo": i["title"], "url": i["html_url"],
            "abierto": i["state"] == "open",
            "asignados": [a["login"] for a in i.get("assignees", [])],
            "etiquetas": [l["name"] for l in i.get("labels", [])],
            "creado": i["created_at"], "cerrado": i.get("closed_at"),
            "columna": proyecto.get(i["number"]),
        })

    commits_por = Counter(((c.get("author") or {}).get("login") or "").lower() for c in commits)
    commits_por.pop("", None)

    # --- personas
    personas = []
    for login, m in roster.items():
        mios = [p for p in prs if p["autor"].lower() == login]
        abiertos = [p for p in mios if p["estado"] in ("espera", "cambios", "aprobado", "borrador")]
        fusionados = [p for p in mios if p["estado"] == "fusionado"]
        rev_hechas = sum(1 for p in prs if login in [r.lower() for r in p["revisores"]])
        iss_abiertos = [i for i in issues if i["abierto"] and login in [a.lower() for a in i["asignados"]]]
        iss_cerrados = [i for i in issues if not i["abierto"] and login in [a.lower() for a in i["asignados"]]]
        aportes = len(mios) + commits_por.get(login, 0) + rev_hechas
        etiquetas = []
        if aportes == 0:
            etiquetas.append("sin_aportes")
        if abiertos:
            etiquetas.append("pr_espera")
        if iss_abiertos:
            etiquetas.append("con_issues")
        if fusionados or rev_hechas:
            etiquetas.append("activo")
        personas.append({
            "login": m["login"], "nombre": m.get("nombre") or m["login"], "equipo": m.get("equipo", "—"),
            "lider": bool(m.get("lider")), "etiquetas": etiquetas,
            "prs_abiertos": [p["n"] for p in abiertos], "prs_fusionados": [p["n"] for p in fusionados],
            "issues_abiertos": [i["n"] for i in iss_abiertos], "issues_cerrados": [i["n"] for i in iss_cerrados],
            "commits": commits_por.get(login, 0), "revisiones": rev_hechas,
        })

    # --- equipos
    por_equipo = defaultdict(lambda: {"abiertos": 0, "cerrados": 0, "prs_fusionados": 0, "prs_abiertos": 0, "personas": 0})
    for p in personas:
        e = por_equipo[p["equipo"]]
        e["personas"] += 1
        e["abiertos"] += len(p["issues_abiertos"])
        e["cerrados"] += len(p["issues_cerrados"])
        e["prs_fusionados"] += len(p["prs_fusionados"])
        e["prs_abiertos"] += len(p["prs_abiertos"])
    sin = [i for i in issues if not i["asignados"]]
    if sin:
        por_equipo["Sin asignar"]["abiertos"] = sum(1 for i in sin if i["abierto"])
        por_equipo["Sin asignar"]["cerrados"] = sum(1 for i in sin if not i["abierto"])
    equipos = [{"nombre": k, **v} for k, v in por_equipo.items()]

    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notas": {k: v for k, v in notas.items() if not k.startswith("_")},
        "prs": prs, "issues": issues, "personas": personas, "equipos": equipos,
        "project_activo": bool(proyecto),
    }



# ------------------------------------------------- Lista de integrantes --
EQUIPOS = {"engine": "Engine", "topologias": "Topologías", "metricas": "Métricas", "ui": "UI", "config": "Config"}


def _norm(t: str) -> str:
    return (t.lower().replace("í", "i").replace("é", "e").replace("á", "a").replace("ó", "o").replace("ú", "u"))


# ------------------------------------------------------------------- Demo --
def datos_demo():
    """Datos inventados (nombres falsos) solo para revisar el diseño."""
    import random
    random.seed(7)
    ahora = datetime.now(timezone.utc)
    eq = {"Config": 1, "Topologías": 4, "Engine": 4, "Métricas": 3, "UI": 2}
    integrantes, k = [], 0
    for e, n in eq.items():
        for j in range(n):
            k += 1
            integrantes.append({"login": f"persona{k:02d}", "nombre": f"Integrante {k:02d}", "equipo": e, "lider": j == 0})
    iso = lambda d: (ahora - timedelta(days=d)).isoformat(timespec="seconds")
    log = lambda n: f"persona{n:02d}"
    prs_raw, revs, commits = [], {}, []
    plan = [  # (n, autor, estado, dias)
        (23, 1, "merged", 9), (24, 12, "merged", 7), (25, 10, "merged", 6), (27, 3, "merged", 3),
        (28, 11, "merged", 1), (26, 2, "cambios", 2), (29, 6, "open", 1), (30, 7, "aprobado", 1)]
    for n, a, est, d in plan:
        p = {"number": n, "title": f"feat: entrega de ejemplo #{n}", "user": {"login": log(a)}, "html_url": "#",
             "state": "closed" if est == "merged" else "open", "draft": False, "head": {"ref": f"feature/x-{n}"},
             "created_at": iso(d + 1), "merged_at": iso(d) if est == "merged" else None, "body": f"Closes #{n - 16}"}
        prs_raw.append(p)
        r = []
        if est == "cambios":
            r = [{"state": "CHANGES_REQUESTED", "user": {"login": log(1)}, "submitted_at": iso(d)}]
        if est in ("aprobado", "merged"):
            r = [{"state": "APPROVED", "user": {"login": log(1)}, "submitted_at": iso(d)}]
        revs[n] = r
        if est == "merged":
            commits.append({"author": {"login": log(a)}})
    issues_raw = []
    for i in range(3, 15):
        asig = [log(random.choice([2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]))] if i != 9 else []
        cerr = i in (3, 4, 5, 6, 11)
        issues_raw.append({"number": i, "title": f"Tarea {i}: descripción de ejemplo", "html_url": "#",
                           "state": "closed" if cerr else "open", "assignees": [{"login": x} for x in asig],
                           "labels": [], "created_at": iso(12), "closed_at": iso(2) if cerr else None})
    notas = json.loads((AQUI / "notas.json").read_text(encoding="utf-8"))
    notas["entrega"]["fecha"] = (ahora + timedelta(days=5, hours=3)).isoformat()
    return {"integrantes": integrantes}, notas, prs_raw, issues_raw, revs, commits


# ------------------------------------------------------------------- Main --
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="site")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        equipo, notas, prs_raw, issues_raw, revs, commits = datos_demo()
        proyecto, colab, nombres = {}, [], {}
    else:
        repo = os.environ["GITHUB_REPOSITORY"]
        token = os.environ.get("GITHUB_TOKEN")
        ruta_eq = AQUI / "equipo.json"
        equipo = json.loads(ruta_eq.read_text(encoding="utf-8")) if ruta_eq.exists() else {"integrantes": []}
        notas = json.loads((AQUI / "notas.json").read_text(encoding="utf-8"))
        prs_raw, issues_raw, revs, commits, colab = descargar(repo, token)
        proyecto = leer_project(notas, os.environ.get("PROJECT_TOKEN"))
        quienes = {(p.get("user") or {}).get("login") for p in prs_raw} | set(colab) | \
                  {x["login"] for i in issues_raw for x in i.get("assignees", [])}
        nombres = nombres_reales([q for q in quienes if q and not q.endswith("[bot]")], token)
    datos = procesar(prs_raw, issues_raw, revs, commits, equipo, notas, proyecto, colab, nombres)
    datos["repo"] = "equipo/demo (datos inventados)" if a.demo else os.environ["GITHUB_REPOSITORY"]

    plantilla = (AQUI / "plantilla.html").read_text(encoding="utf-8")
    js = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    html = plantilla.replace("/*__DATOS__*/null", js)
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "estado.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Panel escrito en {out / 'index.html'}")


if __name__ == "__main__":
    main()
