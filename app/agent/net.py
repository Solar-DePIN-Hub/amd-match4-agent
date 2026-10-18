"""Tiny stdlib HTTP layer: timeouts, gzip, disk cache, HTML->text, link extraction."""
from __future__ import annotations
import gzip, hashlib, html, json, os, re, time, urllib.parse, urllib.request, zlib
from html.parser import HTMLParser

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0 Safari/537.36")
API_UA = "amd-match4-agent/0.1 (research; contact via github Solar-DePIN-Hub)"
CACHE = os.environ.get("AGENT_CACHE", "/tmp/agent-cache")


class Deadline:
    def __init__(self, seconds: float):
        self.end = time.monotonic() + seconds

    def left(self) -> float:
        return self.end - time.monotonic()

    def ok(self, margin: float = 0.0) -> bool:
        return self.left() > margin


def fetch(url: str, dl: Deadline | None = None, timeout: float = 6.0, api: bool = False,
          max_bytes: int = 3_000_000, ua: str | None = None, cache: bool = True) -> tuple[str, str] | None:
    """Return (final_url, text) or None. Never raises."""
    if dl is not None:
        timeout = min(timeout, dl.left() - 0.5)
        if timeout <= 0.3:
            return None
    key = hashlib.sha1(url.encode()).hexdigest()
    cp = os.path.join(CACHE, key)
    try:
        if cache and os.path.exists(cp) and time.time() - os.path.getmtime(cp) < 3600:
            with open(cp) as f:
                d = json.load(f)
            return d["u"], d["t"]
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ua or (API_UA if api else BROWSER_UA),
            "Accept": "application/json" if api else "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(max_bytes)
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw)
            cs = r.headers.get_content_charset() or "utf-8"
            text = raw.decode(cs, errors="replace")
            final = r.geturl()
    except Exception:
        return None
    if not cache:
        return final, text
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(cp + ".tmp", "w") as f:
            json.dump({"u": final, "t": text}, f)
        os.replace(cp + ".tmp", cp)
    except Exception:
        pass
    return final, text


def fetch_json(url: str, dl: Deadline | None = None, timeout: float = 6.0):
    r = fetch(url, dl, timeout, api=True)
    if not r:
        return None
    try:
        return json.loads(r[1])
    except Exception:
        return None


class _Page(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article",
             "td", "th", "dt", "dd", "header", "footer", "table", "ul", "ol", "title", "pre"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.parts, self.links, self.skip = base, [], [], 0
        self._a = None
        self.tels, self.mails, self.jsonld, self._ld = [], [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip += 1
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._ld = []
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "td" or tag == "th":
            self.parts.append(" | ")
        if tag == "a" and a.get("href"):
            href = a["href"].strip()
            if href.lower().startswith("tel:"):
                self.tels.append(urllib.parse.unquote(href[4:]))
            elif href.lower().startswith("mailto:"):
                self.mails.append(urllib.parse.unquote(href[7:]).split("?")[0])
            else:
                self._a = [urllib.parse.urljoin(self.base, href), []]

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
            if tag == "script" and self._ld is not None:
                self.jsonld.append("".join(self._ld))
                self._ld = None
        if tag == "a" and self._a:
            self.links.append((self._a[0].split("#")[0], " ".join("".join(self._a[1]).split())))
            self._a = None
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        if self.skip:
            return
        self.parts.append(data)
        if self._a:
            self._a[1].append(data)


def parse_html(base: str, text: str) -> dict:
    p = _Page(base)
    try:
        p.feed(text)
    except Exception:
        pass
    body = "".join(p.parts)
    body = re.sub(r"[ \t\r\f\v\u00a0]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n", body).strip()
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if m:
        title = html.unescape(" ".join(m.group(1).split()))
    return {"url": base, "title": title, "text": body, "links": p.links, "tels": p.tels,
            "mails": p.mails, "jsonld": p.jsonld}
