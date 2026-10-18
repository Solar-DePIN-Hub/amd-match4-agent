"""Typed candidate extraction from page text. Every candidate is a literal span of a fetched page."""
from __future__ import annotations
import re

STOP = set("""a an the of in on at for to from by with and or is are was were be been what which who whom whose when
where how much many does do did latest current newest recent most official exact value number version give me find
tell please its it this that these those as into about there their than then also can could should would will
website site page web according per number""".split())

MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december"
RX = {
    "version": re.compile(r"(?<![\d.])v?(\d{1,4}\.\d{1,4}(?:\.\d{1,5}){0,2}(?:[-.]?(?:post|rc|a|b|beta|alpha|dev)\.?\d*)?)(?![\w.]*\d)"),
    "phone": re.compile(r"(?<![\w/.])(\+?\d{1,3}[\s.\-]?)?(\(?\d{2,4}\)?[\s.\-]?)\d{2,4}[\s.\-]\d{2,4}(?:[\s.\-]\d{2,4})?(?![\w/])"),
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "date": re.compile(rf"\b(?:\d{{4}}-\d{{2}}-\d{{2}}|(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\.?,?\s+\d{{4}})\b", re.I),
    "year": re.compile(r"\b(1[5-9]\d\d|20\d\d)\b"),
    "price": re.compile(r"(?:[$€£¥₹]\s?\d[\d,]*(?:\.\d{1,2})?|\b\d[\d,]*(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|US\$))"),
    "number": re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|thousand|%))?(?![\w])", re.I),
}

LABELS = {
    "phone": ["phone", "call", "tel", "telephone", "customer service", "support", "contact", "toll", "hotline", "reservations"],
    "version": ["version", "release", "latest", "stable", "download", "current"],
    "email": ["email", "e-mail", "contact", "mail"],
    "date": ["released", "release", "date", "on", "launched", "published"],
    "price": ["price", "cost", "per", "month", "plan", "$"],
    "year": ["founded", "established", "year", "since", "released"],
    "number": [],
}


def keywords(q: str) -> list[str]:
    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#\-]*", q.lower())
    return [t.strip(".-") for t in toks if t not in STOP and len(t) > 1]


def classify(q: str) -> str:
    s = q.lower()
    if re.search(r"\b(phone|telephone|tel\.?|hotline|call (?:center|centre)|toll[- ]free|number to call|contact number)\b", s):
        return "phone"
    if re.search(r"\be-?mail\b", s):
        return "email"
    if re.search(r"\b(price|cost|how much|fee|pricing|msrp)\b", s):
        return "price"
    if re.search(r"\b(what|which) year\b|\byear (?:was|did)\b|\bin what year\b", s):
        return "year"
    if re.search(r"\b(when|date|end[- ]of[- ]life|eol|released on|release date)\b", s):
        return "date"
    if re.search(r"\bversion\b|\brelease\b|\bv\d|\btag\b", s):
        return "version"
    if re.search(r"\bhow many\b|\bpopulation\b|\bnumber of\b|\bhow (?:tall|long|big|high|old)\b", s):
        return "number"
    return "text"


def _valid_phone(m: str) -> bool:
    d = re.sub(r"\D", "", m)
    if not (10 <= len(d) <= 15 or (m.strip().startswith("+") and len(d) >= 8)):
        return False
    if re.fullmatch(r"(19|20)\d\d[\s.\-]\d{1,2}[\s.\-]\d{1,2}", m.strip()):
        return False  # a date
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", m.strip()):
        return False  # an IP
    return True


def candidates(page: dict, atype: str, kws: list[str], q: str) -> list[dict]:
    text = page["text"]
    low = text.lower()
    out = []
    if atype == "text" or atype not in RX:
        return out
    srcs = [(m.group(0) if atype not in ("version",) else m.group(1), m.start(), m.end())
            for m in RX[atype].finditer(text)]
    if atype == "phone":
        for t in page.get("tels", []):
            i = text.find(t)
            srcs.append((t.strip(), i if i >= 0 else 0, (i if i >= 0 else 0) + len(t)))
    if atype == "email":
        for t in page.get("mails", []):
            srcs.append((t.strip(), 0, 0))
    for val, s, e in srcs:
        val = val.strip().strip(",;:")
        if atype == "phone" and not _valid_phone(val):
            continue
        if atype == "number" and val in ("0", "1"):
            continue
        ctx = low[max(0, s - 160): e + 160]
        line = low[max(0, low.rfind("\n", 0, s)): (low.find("\n", e) if low.find("\n", e) > 0 else e + 80)]
        score = 0.0
        score += sum(1.5 for k in kws if k in ctx)
        score += sum(1.0 for k in kws if k in line)
        score += sum(1.0 for l in LABELS.get(atype, []) if l in line)
        if atype == "phone":
            if "isbn" in ctx or "doi" in ctx:
                continue
            if re.search(r"\bfax\b|\btty\b|\btdd\b", line):
                score -= 4
            if re.match(r"\(?\+?1?[\s\-.(]*8(00|88|77|66|55|44|33)\b", val) and not re.search(r"international|outside", q.lower()):
                score += 1.5
        if atype == "version":
            pre = low[max(0, s - 30):s]
            if any(k in pre for k in kws if not re.search(r"\d", k) and k not in ("version", "latest", "stable", "current")):
                score += 3
            score += 0.5 * val.count(".")
        if atype == "version" and re.search(r"(rc|a|b|beta|alpha|dev)\d*$", val, re.I) \
                and not re.search(r"beta|alpha|rc|pre", q.lower()):
            score -= 3
        out.append({"value": val, "score": score, "ctx": text[max(0, s - 160): e + 160].replace("\n", " "),
                    "url": page["url"]})
    return out


def passages(page: dict, kws: list[str], n: int = 4, size: int = 700) -> list[tuple[float, str, str]]:
    text = page["text"]
    res = []
    for i in range(0, max(1, len(text)), size // 2):
        chunk = text[i:i + size]
        lc = chunk.lower()
        sc = sum(1 for k in kws if k in lc)
        if sc:
            res.append((sc, chunk, page["url"]))
    res.sort(key=lambda x: -x[0])
    return res[:n]
