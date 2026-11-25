"""Builds the list of official pages to monitor: each state's CLIA/lab-licensing agency page plus key federal and New York pages."""
import json, pathlib
STATES = json.loads(pathlib.Path(__file__).resolve().parent.parent.joinpath("data/clia-state-requirements.json").read_text())

EXTRA = [
    ("newyork", "New York", "CLEP home and news", "https://www.wadsworth.org/regulatory/clep"),
    ("newyork", "New York", "CLEP test approval (LDT submissions)", "https://www.wadsworth.org/regulatory/clep/clinical-labs/obtain-permit/test-approval"),
    ("newyork", "New York", "CLEP Single Use Permits", "https://www.wadsworth.org/regulatory/clep/clinical-labs/single-use-permits"),
    ("newyork", "New York", "CLEP laws and regulations", "https://www.wadsworth.org/regulatory/clep/laws"),
    ("newyork", "New York", "CLEP laboratory standards", "https://www.wadsworth.org/regulatory/clep/clinical-labs/laboratory-standards"),
    ("newyork", "New York", "Wadsworth Center news", "https://www.wadsworth.org/news"),
    ("newyork", "New York", "NY DOH recently adopted regulations", "https://regs.health.ny.gov/regulations/recently-adopted"),
    ("federal", "Federal", "CMS CLIA program", "https://www.cms.gov/medicare/quality/clinical-laboratory-improvement-amendments"),
    ("federal", "Federal", "CMS CLIA state agency contacts", "https://www.cms.gov/medicare/quality/clinical-laboratory-improvement-amendments/state-agency-regional-office-clia-contacts"),
    ("federal", "Federal", "CDC CLIA law and regulations", "https://www.cdc.gov/clia/php/regulations/index.html"),
]

def sources():
    out = []
    rows = STATES if isinstance(STATES, list) else list(STATES.values())
    for r in rows:
        key = (r.get("key") or r.get("state") or r.get("name", "")).lower().replace(" ", "")
        url = r.get("agencyUrl") or r.get("agency_url") or r.get("url")
        name = r.get("name") or r.get("state")
        seen = set()
        if url and name:
            out.append({"id": f"{key}:agency", "state": key, "name": name, "label": f"{name} lab regulator", "url": url}); seen.add(url)
        for i, src in enumerate(r.get("sources") or []):
            if src and src not in seen and src.startswith("http"):
                seen.add(src); out.append({"id": f"{key}:source{i+1}", "state": key, "name": name, "label": f"{name} rule or guidance source", "url": src})
    for key, name, label, url in EXTRA:
        out.append({"id": f"{key}:{label.lower().replace(' ', '-')[:40]}", "state": key, "name": name, "label": label, "url": url})
    return out

if __name__ == "__main__":
    s = sources(); print(len(s)); print(json.dumps(s[:3], indent=1))
