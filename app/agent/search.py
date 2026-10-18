"""Key-free web search (DuckDuckGo HTML, Bing HTML fallback). May be blocked on the grader; then we rely on
resolvers and start URLs."""
from __future__ import annotations
import base64, re, urllib.parse, html
from .net import fetch, Deadline

BAD = ("duckduckgo.com", "bing.com", "microsoft.com/en-us/bing", "go.microsoft.com", "youtube.com", "facebook.com",
       "instagram.com", "tiktok.com", "pinterest.", "x.com", "twitter.com", "linkedin.com")


def _clean(urls):
    out = []
    for u in urls:
        u = html.unescape(u)
        if not u.startswith("http") or any(b in u for b in BAD) or u in out:
            continue
        out.append(u)
    return out


def ddg(q, dl):
    r = fetch("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q), dl, timeout=5, ua="Mozilla/5.0", cache=False)
    if not r:
        return []
    urls = [urllib.parse.unquote(m) for m in re.findall(r'uddg=([^&"]+)', r[1])]
    return _clean(urls)


def bing(q, dl):
    r = fetch("https://www.bing.com/search?setlang=en&form=QBLH&q=" + urllib.parse.quote(q), dl, timeout=5, cache=False)
    if not r:
        return []
    out = []
    for blk in re.findall(r'<li class="b_algo"(.*?)</li>', r[1], re.S):
        m = re.search(r'<h2[^>]*>\s*<a [^>]*href="([^"]+)"', blk)
        if not m:
            continue
        u = html.unescape(m.group(1))
        mu = re.search(r'[?&]u=a1([^&]+)', u)
        if mu:
            try:
                b = mu.group(1); u = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
            except Exception:
                continue
        out.append(u)
    return _clean(out)


def brave(q, dl):
    r = fetch("https://search.brave.com/search?q=" + urllib.parse.quote(q), dl, timeout=5, cache=False)
    if not r:
        return []
    out = []
    for b in re.findall(r'<div class="snippet[^"]*"[^>]*data-type="web"(.*?)</a>', r[1], re.S):
        m = re.search(r'href="(https?://[^"]+)"', b)
        if m:
            out.append(m.group(1))
    return _clean(out)


def search(q, dl: Deadline, n=6):
    res = brave(q, dl)
    if len(res) >= 2:
        return res[:n]
    res = bing(q, dl)
    if len(res) < 2 and dl.ok(8):
        res += [u for u in ddg(q, dl) if u not in res]
    return res[:n]
