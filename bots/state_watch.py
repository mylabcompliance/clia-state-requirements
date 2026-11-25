"""Daily monitor of state and federal clinical-lab regulator pages.

For each source page: fetch, reduce to readable text lines plus document links, compare with the
previous snapshot, and record what changed (new text, new documents/publications). Results go to
data/state-watch.json, which soundlabconsult.com reads to show "last checked" and "change detected"
notices on each state's pages. A GitHub issue is opened for every run with changes so a person can
review the requirement text; the site never rewrites legal requirements automatically.
"""
import datetime, hashlib, html, json, os, pathlib, re, subprocess, sys, urllib.request, urllib.parse
from watch_sources import sources

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "watch"
OUT = ROOT / "data" / "state-watch.json"
UA = "Mozilla/5.0 (compatible; SLC-RegWatch/1.0; +https://soundlabconsult.com/state-lab-requirements/)"
TODAY = datetime.date.today().isoformat()
DOC = re.compile(r"\.(pdf|docx?|xlsx?)(\?|#|$)", re.I)
NOISE = re.compile(r"(copyright|©|all rights reserved|last (updated|modified|reviewed)|page (loaded|generated)|cookie|javascript|skip to (main )?content|^\W*$)", re.I)
DATEISH = re.compile(r"\b(\d{1,2}:\d{2}\s*(am|pm)?|\d{1,2}/\d{1,2}/\d{2,4})\b", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read(4_000_000)
        cs = r.headers.get_content_charset() or "utf-8"
        return r.status, raw.decode(cs, "replace")

def extract(url, page):
    body = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", page)
    links = []
    for m in re.finditer(r'(?is)<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body):
        href = urllib.parse.urljoin(url, html.unescape(m.group(1)).strip())
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        if DOC.search(href):
            links.append({"url": href, "title": text[:160] or href.rsplit("/", 1)[-1]})
    body = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr|/td|/section|/article)[^>]*>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    lines = []
    for ln in text.split("\n"):
        ln = re.sub(r"\s+", " ", ln).strip()
        if len(ln) < 25 or NOISE.search(ln) or DATEISH.search(ln) and len(ln) < 60:
            continue
        lines.append(ln)
    seen, uniq = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln); uniq.append(ln)
    dl, du = [], set()
    for l in links:
        if l["url"] not in du:
            du.add(l["url"]); dl.append(l)
    return uniq, dl

INDEXNOW_KEY = "b51c23e3811f3f78887fda7d097bc985"  # public key file served at soundlabconsult.com/<key>.txt

def reindex(keys):
    """Ask search engines to recrawl the pages that show regulation-watch data for the changed states."""
    rows = json.loads((ROOT / "data" / "clia-state-requirements.json").read_text())
    by = {r["slug"].replace("-", ""): r for r in rows}
    urls = ["https://soundlabconsult.com/state-lab-requirements/"]
    for k in keys:
        if k == "newyork":
            urls += ["https://soundlabconsult.com/new-york-genetic-testing-requirements/",
                     "https://soundlabconsult.com/new-york-genetic-testing-requirements/ldt-test-approval/",
                     "https://soundlabconsult.com/new-york-genetic-testing-requirements/single-use-permit/"]
        if k in by:
            urls.append(f"https://soundlabconsult.com/lab-consultant-{by[k]['slug']}")
    body = json.dumps({"host": "soundlabconsult.com", "key": INDEXNOW_KEY,
                       "keyLocation": f"https://soundlabconsult.com/{INDEXNOW_KEY}.txt", "urlList": sorted(set(urls))}).encode()
    try:
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow", r.status, len(urls), "urls")
    except Exception as e:
        print("IndexNow failed:", e)

def main():
    SNAP.mkdir(parents=True, exist_ok=True)
    state = json.loads(OUT.read_text()) if OUT.exists() else {"sources": {}}
    changed = []
    for src in sources():
        sid = src["id"]; f = SNAP / (hashlib.sha1(sid.encode()).hexdigest()[:16] + ".json")
        rec = state["sources"].get(sid, {"state": src["state"], "name": src["name"], "label": src["label"], "url": src["url"], "changes": []})
        rec.update({"state": src["state"], "name": src["name"], "label": src["label"], "url": src["url"], "lastChecked": TODAY})
        try:
            status, page = fetch(src["url"])
            lines, docs = extract(src["url"], page)
            rec["lastStatus"] = status
            rec.pop("manualCheck", None)
        except Exception as e:
            rec["lastStatus"] = f"error: {str(e)[:80]}"
            rec["manualCheck"] = True  # site blocks automated checks or is unreachable; reviewed by hand
            state["sources"][sid] = rec
            continue
        prev = json.loads(f.read_text()) if f.exists() else None
        f.write_text(json.dumps({"url": src["url"], "lines": lines, "docs": docs}, indent=0))
        if prev is None:
            rec.setdefault("baseline", TODAY)
        else:
            old_lines, old_docs = set(prev["lines"]), {d["url"] for d in prev["docs"]}
            added = [l for l in lines if l not in old_lines]
            removed = [l for l in prev["lines"] if l not in set(lines)]
            new_docs = [d for d in docs if d["url"] not in old_docs]
            meaningful = [l for l in added if len(l) >= 40]
            if new_docs or len(meaningful) >= 1 and (len(meaningful) + len(removed)) >= 2:
                ch = {"date": TODAY, "added": meaningful[:8], "removedCount": len(removed), "newDocs": new_docs[:10], "reviewed": False}
                rec["changes"] = ([ch] + rec.get("changes", []))[:12]
                rec["lastChanged"] = TODAY
                changed.append((src, ch))
        state["sources"][sid] = rec
    state["generated"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    state["changedToday"] = sorted({s["state"] for s, _ in changed})
    OUT.write_text(json.dumps(state, indent=1, sort_keys=True))
    if changed:
        body = ["Automated check of state and federal lab regulator pages found changes. Review each item and update the requirement text on soundlabconsult.com and the state sites if the rules changed.\n"]
        for s, ch in changed:
            body.append(f"### {s['name']}: {s['label']}\n{s['url']}\n")
            for d in ch["newDocs"]:
                body.append(f"- New document: [{d['title']}]({d['url']})")
            for a in ch["added"]:
                body.append(f"- New text: {a[:300]}")
            if ch["removedCount"]:
                body.append(f"- {ch['removedCount']} line(s) removed")
            body.append("")
        pathlib.Path("issue.md").write_text("\n".join(body)[:60000])
    if changed:
        reindex(state["changedToday"])
    print(f"checked {len(state['sources'])} sources, {len(changed)} changed: {state['changedToday']}")

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    main()
