"""Direct-source resolvers: authoritative structured APIs, tried before any crawling.
Each returns {"answer", "source", "confidence", "via"} or None."""
from __future__ import annotations
import datetime, re, urllib.parse
from .net import fetch_json, Deadline
from .extract import STOP

PKG_PATTERNS = [
    r"(?:package|library|module|crate|gem)\s+[\"'`“]?([@\w][\w.\-/@]*)",
    r"[\"'`“]([@\w][\w.\-/@]*)[\"'`”]",
    r"\bof\s+([@\w][\w.\-/@]*)\s+(?:on|in|from)\s+(?:pypi|npm|crates|the python|the npm)",
    r"\b([@\w][\w.\-/@]*)\s+(?:python|npm|node|rust)?\s*(?:package|library|module|crate)\b",
    r"\bversion of\s+(?:the\s+)?([@\w][\w.\-/@]*)",
    r"\bpip install\s+([\w.\-]+)", r"\bnpm (?:i|install)\s+([@\w][\w.\-/@]*)",
]
VERSION_STOP = STOP | {"python", "npm", "node", "pypi", "package", "library", "module", "rust", "crate", "stable",
                       "released", "release", "published", "registry", "javascript", "js"}


def _pkg_names(q: str) -> list[str]:
    names = []
    for p in PKG_PATTERNS:
        for m in re.finditer(p, q, re.I):
            n = re.sub(r"'s$", "", m.group(1).strip(".,?!"))
            if n.lower() not in VERSION_STOP and n not in names and not re.fullmatch(r"\d[\d.]*", n):
                names.append(n)
    return names


def _clean_ver(v: str) -> str:
    v = v.strip()
    return v[1:] if re.match(r"v\d", v) else v


def pypi(q, names, dl):
    for n in names:
        d = fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(n)}/json", dl)
        if d and d.get("info", {}).get("version"):
            return {"answer": d["info"]["version"], "source": f"https://pypi.org/project/{d['info']['name']}/",
                    "confidence": 0.95, "via": "pypi"}


def npm(q, names, dl):
    for n in names:
        d = fetch_json(f"https://registry.npmjs.org/{n.replace('/', '%2F') if n.startswith('@') else n}/latest", dl)
        if d and d.get("version"):
            return {"answer": d["version"], "source": f"https://www.npmjs.com/package/{n}",
                    "confidence": 0.95, "via": "npm"}


def crates(q, names, dl):
    for n in names:
        d = fetch_json(f"https://crates.io/api/v1/crates/{n}", dl)
        if d and d.get("crate", {}).get("max_stable_version"):
            return {"answer": d["crate"]["max_stable_version"], "source": f"https://crates.io/crates/{n}",
                    "confidence": 0.95, "via": "crates"}


def github(q, dl):
    m = re.search(r"github\.com/([\w.\-]+)/([\w.\-]+)", q) or re.search(r"\b([\w.\-]+)/([\w.\-]+)\b", q)
    if not m or "." in m.group(1)[:1]:
        return None
    owner, repo = m.group(1), m.group(2).removesuffix(".git")
    d = fetch_json(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", dl)
    if d and d.get("tag_name"):
        tag = d["tag_name"]
        mv = re.search(r"\d+(?:\.\d+)+[\w.\-]*", tag)
        return {"answer": mv.group(0) if mv else _clean_ver(tag), "source": d.get("html_url"),
                "confidence": 0.85, "via": "github"}


_EOL = None


def _eol_products(dl):
    global _EOL
    if _EOL is None:
        _EOL = fetch_json("https://endoflife.date/api/all.json", dl) or []
    return _EOL


def _canon(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


ALIASES = {"node": "nodejs", "nodejs": "nodejs", "node.js": "nodejs", "golang": "go", "go": "go",
           "postgres": "postgresql", "k8s": "kubernetes", "ror": "rails", "ruby on rails": "rails",
           "dotnet": "dotnet", ".net": "dotnet", "mac os": "macos", "os x": "macos", "ms windows": "windows"}


def endoflife(q, atype, dl):
    prods = _eol_products(dl)
    if not prods:
        return None
    s = q.lower()
    toks = re.findall(r"[a-z0-9][a-z0-9.+\-]*", s)
    found = None
    cands = set()
    for i in range(len(toks)):
        for j in (3, 2, 1):
            phrase = " ".join(toks[i:i + j])
            c = ALIASES.get(phrase) or _canon(phrase)
            cands.add(c)
    best = [p for p in prods if _canon(p) in cands and len(_canon(p)) > 1]
    if not best:
        return None
    found = max(best, key=len)
    rows = fetch_json(f"https://endoflife.date/api/{found}.json", dl)
    if not rows:
        return None
    src = f"https://endoflife.date/{found}"
    today = datetime.date.today().isoformat()
    cyc = None
    m = re.search(r"\b(?:%s)\s*v?(\d+(?:\.\d+)?)\b" % "|".join(re.escape(t) for t in
                  {found, found.replace("-", " "), "node", "node.js", "python", "java", "go", "php"}), s)
    if m:
        for r in rows:
            if str(r.get("cycle")) == m.group(1):
                cyc = r
    lts_q = bool(re.search(r"\blts\b|long[- ]term", s))
    if cyc is None:
        if lts_q:
            lts = [r for r in rows if r.get("lts") and (r["lts"] is True or str(r["lts"]) <= today)]
            cyc = lts[0] if lts else None
        else:
            cyc = rows[0]
    if cyc is None:
        return None
    if re.search(r"end[- ]of[- ]life|\beol\b|support end|supported until|end of support", s):
        v = cyc.get("eol")
        if isinstance(v, str):
            return {"answer": v, "source": src, "confidence": 0.8, "via": "endoflife"}
        return None
    if atype in ("date", "year") and m is None:
        return None
    if atype in ("date", "year") or re.search(r"\breleased?\b.*\bwhen\b|\bwhen\b.*\breleased?\b|release date", s):
        key = "latestReleaseDate" if re.search(r"latest (?:patch|point)", s) else "releaseDate"
        v = cyc.get(key)
        if v and m is not None:
            return {"answer": v[:4] if atype == "year" else v, "source": src, "confidence": 0.75, "via": "endoflife"}
    if atype == "version" or "version" in s:
        if m and not re.search(r"latest|newest|current|most recent|patch", s):
            return None
        v = cyc.get("latest")
        if v:
            return {"answer": str(v), "source": src, "confidence": 0.85, "via": "endoflife"}
    return None


# ---------------- Wikidata ----------------
WD_PROPS = [
    (r"\b(?:phone|telephone)\b", "P1329", "phone"),
    (r"\b(?:official (?:web)?site|website|homepage)\b", "P856", "url"),
    (r"\be-?mail\b", "P968", "email"),
    (r"\b(?:directed by|director of|who directed|directed)\b", "P57", "item"),
    (r"\b(?:ceo|chief executive(?: officer)?)\b", "P169", "item"),
    (r"\b(?:who founded|founded by|founders?)\b", "P112", "item"),
    (r"\b(?:headquartered|headquarters|headquarter|hq)\b", "P159", "item"),
    (r"\b(?:founded|established|formed|incorporated)\b", "P571", "time"),
    (r"\bcapital\b", "P36", "item"),
    (r"\bpopulation\b", "P1082", "quantity"),
    (r"\b(?:written by|author of|who wrote)\b", "P50", "item"),
    (r"\b(?:developed by|developer of|who developed)\b", "P178", "item"),
    (r"\b(?:date of birth|born)\b", "P569", "time"),
    (r"\b(?:ticker|stock symbol)\b", "P249", "string"),
    (r"\bcurrency\b", "P38", "item"),
    (r"\b(?:first released|publication date|release date|released|launched)\b", "P577", "time"),
]
WD = "https://www.wikidata.org/w/api.php"


def _entity_phrase(q, prop_rx):
    s = re.sub(prop_rx, " ", q, flags=re.I)
    s = re.sub(r"[?!.,\"“”]", " ", s)
    words = [w for w in s.split() if w.lower() not in STOP | {"customer", "service", "main", "general", "headquarters",
                                                            "company", "corporation", "inc", "located", "city",
                                                            "year", "film", "movie", "programming", "first"}]
    return " ".join(words)


def wd_label(qid, dl):
    d = fetch_json(f"{WD}?action=wbgetentities&ids={qid}&props=labels&languages=en&format=json", dl)
    try:
        return d["entities"][qid]["labels"]["en"]["value"]
    except Exception:
        return None


def wikidata(q, atype, dl):
    for rx, prop, kind in WD_PROPS:
        if re.search(rx, q, re.I):
            break
    else:
        return None
    if kind == "time" and atype not in ("date", "year"):
        return None
    ent = _entity_phrase(q, rx)
    if not ent:
        return None
    ids = []
    for phrase in dict.fromkeys([ent, " ".join(ent.split()[:2]), ent.split()[0]]):
        d = fetch_json(f"{WD}?action=wbsearchentities&search={urllib.parse.quote(phrase)}&language=en&limit=3&format=json", dl)
        if d and d.get("search"):
            ids = [x["id"] for x in d["search"]]
            break
    if not ids:
        return None
    props = [prop] + (["P571", "P577"] if kind == "time" and prop in ("P571", "P577") else [])
    e = fetch_json(f"{WD}?action=wbgetentities&ids={'|'.join(ids)}&props=claims&format=json", dl)
    if not e:
        return None
    for qid, pr in ((i, p) for i in ids for p in dict.fromkeys(props)):
        claims = e.get("entities", {}).get(qid, {}).get("claims", {}).get(pr)
        if not claims:
            continue
        pref = [c for c in claims if c.get("rank") == "preferred"] or [c for c in claims if c.get("rank") != "deprecated"]
        # a claim with an end date (P582) is historical
        cur = [c for c in pref if "P582" not in c.get("qualifiers", {})] or pref
        c = cur[0]
        dv = c.get("mainsnak", {}).get("datavalue", {})
        v = dv.get("value")
        if v is None:
            continue
        src = f"https://www.wikidata.org/wiki/{qid}"
        if kind == "item":
            lab = wd_label(v["id"], dl)
            if lab:
                return {"answer": lab, "source": src, "confidence": 0.7, "via": "wikidata"}
        elif kind == "time":
            t = v["time"].lstrip("+")
            prec = v.get("precision", 11)
            ans = t[:4] if atype == "year" or prec <= 9 else (t[:7] if prec == 10 else t[:10])
            return {"answer": ans, "source": src, "confidence": 0.7, "via": "wikidata"}
        elif kind == "quantity":
            amt = v["amount"].lstrip("+")
            return {"answer": amt, "source": src, "confidence": 0.6, "via": "wikidata"}
        elif kind in ("phone", "email", "url", "string"):
            ans = str(v)
            if kind == "email":
                ans = ans.replace("mailto:", "")
            return {"answer": ans, "source": src, "confidence": 0.55 if kind == "phone" else 0.7, "via": "wikidata"}
    return None


def resolve(q: str, atype: str, dl: Deadline):
    s = q.lower()
    names = _pkg_names(q)
    if atype == "version" or "version" in s:
        if re.search(r"\bpypi\b|\bpip\b|python (?:package|library|module)", s):
            r = pypi(q, names, dl)
            if r: return r
        if re.search(r"\bnpm\b|node(?:\.js)? (?:package|module)|javascript (?:package|library)", s):
            r = npm(q, names, dl)
            if r: return r
        if re.search(r"\bcrates?\b|\brust\b", s):
            r = crates(q, names, dl)
            if r: return r
        if names and re.search(r"\bpypi\b|\bnpm\b|\bcrates\.io\b", s):
            return {"answer": "", "source": None, "confidence": 0.9, "via": "registry-miss"}
        if "github" in s or re.search(r"\b[\w.\-]+/[\w.\-]+\b", q) and not q.strip().lower().startswith("http"):
            r = github(q, dl)
            if r: return r
    r = endoflife(q, atype, dl)
    if r:
        return r
    if atype == "version" and names:
        for f in (pypi, npm):
            r = f(q, names, dl)
            if r:
                r["confidence"] = 0.5
                return r
    if atype != "version":
        r = wikidata(q, atype, dl)
        if r:
            return r
    return None
