"""Daily list of remote tech jobs you can take from outside the US: worldwide, or open to a named region/country.

    python -P tools/remote_open_list.py --out github/remote-jobs-open-to-you [--rows rows.jsonl] [--days 30] [--site URL]
Writes jobs.json, README.md (per-region tables) and index.html (pick your country) into --out.
Rule: remote (flag or workplaceType) + tech title (same rule as the UK visa list) + posted in --days. Scope of each job,
read with the Actor's own geo rules (geo.remote_open_to): "Worldwide" (a location says anywhere/worldwide/global and
names no country), regions named without a country (EMEA, LATAM, APAC, Europe, Africa...), and country codes. Jobs
open only to the US and/or Canada are left out, and so are bare "Remote" jobs (no scope: most are US-only in practice).
"""
import html
import gzip, html, json, re, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent / "actors" / "ats-jobs" / "src"))
import geo  # noqa: E402
from geo import country_codes, from_field, from_text  # noqa: E402
from visa_jobs_list import TECH, NOT  # noqa: E402  (same tech-title rule)

STORE = "https://api.apify.com/v2/key-value-stores/VFEsrfmHwQiuxShwN/records/"
ACTOR = "https://apify.com/jordan-belfort/ats-jobs-api"
# region label -> ISO codes (from the Actor's geo.py, so the page and the Actor agree)
REGIONS = {"EMEA": geo._EUROPE | geo._MIDEAST | geo._AFRICA, "Europe": geo._EUROPE, "LATAM": geo._LATAM,
           "APAC": geo._APAC, "Africa": geo._AFRICA, "Middle East": geo._MIDEAST | {"MA", "DZ", "TN", "LY"},
           "Americas": geo._LATAM | {"US", "CA"}}
_RX = [("EMEA", r"emea"), ("Europe", r"europe|european union|eu|eea|dach|nordics?|benelux"),
       ("APAC", r"apac|asia[- ]pacific|asia|south ?east asia"), ("LATAM", r"latam|latin america|south america|central america|caribbean"),
       ("Americas", r"amer|americas"), ("Middle East", r"mena|middle east"), ("Africa", r"africa")]
_RX = [(n, re.compile(r"(?<![\w])(?:" + p + r")(?![\w])")) for n, p in _RX]
SECTIONS = [("Worldwide", None), ("Latin America", "LATAM"), ("India", "IN"), ("Africa", "Africa"),
            ("Asia-Pacific", "APAC"), ("Europe (anywhere in a region, not one country)", "Europe")]


def scope(r):
    """(worldwide, regions, countries) a remote job is open to, or None when it says nothing usable."""
    codes = set(r.get("countryCodes") or country_codes(r))
    world, regions = False, set()
    if not from_field(r.get("country")):
        for loc in [r.get("location"), *(r.get("allLocations") or [])]:
            if not isinstance(loc, str) or not loc.strip() or from_text(loc):
                continue
            low = loc.lower()
            named = {n for n, rx in _RX if rx.search(low)}
            if geo._WORLD_RE.search(low) and not named and (loc == r.get("location") or not codes):
                world = True  # a "Global" among other locations of a US/Toronto/Amsterdam job is not worldwide
            regions |= named  # "Europe - Anywhere" is Europe, not worldwide
    if world:  # the title can narrow a worldwide location: Moxie "Staff Product Engineer, Backend (LATAM)" (4 Nov)
        named = {n for n, rx in _RX if rx.search((r.get("title") or "").lower())}
        if named:
            world, regions = False, regions | named
    return world, regions, codes


NOT_REMOTE = re.compile(r"hybrid|on[- ]?site|in[- ]office|in[- ]person|office[- ]based|vor ort|presencial", re.I)


_PREFIX = re.compile(r"^\s*(?:\[\s*job\s*-?\s*\d+\s*\]|#\s*\d+)\s*[-:]?\s*", re.I)


def clean_title(t):
    """CI&T posts '[Job -  32512] Senior - AI Deployment Engineer' and '#8 Data Engineer': the number is theirs, not
    the role's (57 rows, 4 Nov audit)."""
    return re.sub(r"\s+", " ", _PREFIX.sub("", t or "")).strip() or (t or "").strip()


def is_remote(r):
    """The ATS says remote and nothing in the title or location says hybrid/on-site ('Software Engineer (Dublin, Hybrid)',
    location 'In-Office' both seen with a remote flag)."""
    if r.get("workplaceType") in ("hybrid", "onsite"):
        return False
    if NOT_REMOTE.search(r.get("title") or "") or NOT_REMOTE.search(r.get("location") or ""):
        return False
    return bool(r.get("remote") or r.get("workplaceType") == "remote")


def rows(path):
    if path:
        for line in open(path):
            yield json.loads(line)
        return
    get = lambda k: urllib.request.urlopen(STORE + k, timeout=120).read()
    for key in json.loads(get("MANIFEST"))["chunks"]:
        b = get(key)
        yield from json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)


def pay(r):
    if not (r.get("salaryMin") and r.get("salaryCurrency")):
        return ""
    lo, hi = r["salaryMin"], r.get("salaryMax") or r["salaryMin"]
    k = lambda v: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}"
    per = {"year": "", "hour": "/h", "month": "/mo"}.get(r.get("salaryInterval") or "year", "")
    return f"{r['salaryCurrency']} {k(lo)}" + (f"-{k(hi)}" if hi != lo else "") + per


def md(s):
    return re.sub(r"([\[\]|*_`<>])", r"\\\1", s or "").strip()


def label(j):
    return "Worldwide" if j["world"] else ", ".join(j["regions"] + j["countries"])


def in_section(j, key):
    if key is None:
        return j["world"]
    if j["world"]:
        return False
    if key in REGIONS:
        if key == "Europe":  # Europe-wide roles only; one-country European roles are on the page's country picker
            return bool({"Europe", "EMEA"} & set(j["regions"]))
        return key in j["regions"] or bool(set(j["countries"]) & REGIONS[key])
    return key in j["countries"] or any(key in REGIONS[g] for g in j["regions"])


def main():
    a = sys.argv
    out = Path(a[a.index("--out") + 1]) if "--out" in a else Path("github/remote-jobs-open-to-you")
    days = int(a[a.index("--days") + 1]) if "--days" in a else 30
    path = a[a.index("--rows") + 1] if "--rows" in a else None
    site = a[a.index("--site") + 1] if "--site" in a else ""
    built = json.loads(urllib.request.urlopen(STORE + "MANIFEST", timeout=60).read())["builtAt"]
    since = (datetime.fromisoformat(built) - timedelta(days=days)).isoformat()
    new_since = (datetime.fromisoformat(built) - timedelta(days=2)).isoformat()
    seen, n_remote_tech, bare, usca = {}, 0, 0, 0
    for r in rows(path):
        t = (r.get("title") or "").strip()
        if not r.get("url") or (r.get("publishedAt") or "") < since or not is_remote(r) or not TECH.search(t) or NOT.search(t):
            continue
        n_remote_tech += 1
        world, regions, codes = scope(r)
        if not world and not regions and not codes:
            bare += 1
            continue
        if not world and not (regions - {"Americas"}) and codes <= {"US", "CA"}:
            usca += 1
            continue
        k = ((r.get("company") or "").lower(), re.sub(r"\s+", " ", t.lower()))
        if k not in seen or r["publishedAt"] > seen[k][0]["publishedAt"]:
            seen[k] = (r, world, regions, codes)
    jobs = []
    for r, world, regions, codes in sorted(seen.values(), key=lambda v: v[0]["publishedAt"], reverse=True):
        jobs.append({"company": r.get("company") or "", "title": clean_title(r["title"]), "location": (r.get("location") or "").strip(),
                     "world": world, "regions": sorted(regions), "countries": sorted(codes), "pay": pay(r),
                     "posted": r["publishedAt"][:10], "new": r["publishedAt"] >= new_since, "url": r["url"], "ats": r.get("ats")})
    out.mkdir(parents=True, exist_ok=True)
    stats = {"remoteTech": n_remote_tech, "bareRemote": bare, "usCanadaOnly": usca, "listed": len(jobs)}
    (out / "jobs.json").write_text(json.dumps({"builtAt": built, "days": days, "stats": stats, "jobs": jobs}, ensure_ascii=False), "utf8")
    day = built[:10]
    cnt = Counter()
    for j in jobs:
        for c in set(j["countries"]) | {c for g in j["regions"] for c in REGIONS[g]}:
            cnt[c] += 1
    example = json.dumps({"searchKeywords": ["software engineer"], "remoteFromCountries": ["IN"], "postedWithinDays": 7, "maxPerCompany": 5})
    L = [f"# Remote tech jobs you can actually take from outside the US ({len(jobs)} open, updated {day})", "",
         f"Most \"remote\" jobs are remote *in one country*. Of {n_remote_tech:,} remote tech jobs posted in the last {days} days "
         f"on the career pages of 20,000+ employers, {usca:,} are US/Canada-only and {bare:,} just say \"Remote\" with no scope. "
         f"This list keeps the {len(jobs):,} that say who can apply: **worldwide**, a **region** (EMEA, LATAM, APAC, Europe, Africa) "
         "or a named country outside the US. Read daily from Greenhouse, Ashby, Lever, Workday, SmartRecruiters, Workable, "
         "Recruitee, Teamtailor and Personio boards; every link goes to the employer's own posting. 🆕 = last 2 days.", "",
         "**Pick your country on the filterable page: [jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You](https://jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You/)**", "",
         "Roles open to each country, worldwide and regional ones included (only the filterable page splits them by country; "
         "the tables below go by region): " + ", ".join(f"{c} {n}" for c, n in
            sorted(((c, cnt[c] + sum(j['world'] for j in jobs)) for c in ["IN", "BR", "MX", "AR", "CO", "NG", "KE", "ZA", "PH", "PK", "VN", "PL", "PT", "ES", "DE", "GB"]),
                   key=lambda x: -x[1])), ""]
    for title, key in SECTIONS:
        sel = [j for j in jobs if in_section(j, key)]
        if not sel:
            continue
        L += [f"## {title} ({len(sel)})", "", "| Company | Role | Open to | Pay | Posted |", "| --- | --- | --- | --- | --- |"]
        for j in sel[:300]:
            L.append(f"| {md(j['company'])} | {'🆕 ' if j['new'] else ''}[{md(j['title'])}]({j['url']}) | {md(label(j))} | {md(j['pay'])} | {j['posted']} |")
        if len(sel) > 300:
            L.append(f"| | {len(sel) - 300} more on the [filterable page](https://jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You/) | | | |")
        L.append("")
    L += ["## How \"open to\" is read", "",
          "A location naming a country counts for that country only (\"Remote - Poland\" is PL). A location naming no country "
          "counts for a region it names (\"Remote, EMEA\") or for everyone when it says anywhere/worldwide/global. "
          "\"Remote (US or Canada)\" and bare \"Remote\" are left out. Check the posting: some employers add limits in the text.", "",
          "## Get this feed yourself", "",
          f"The same rule is the `remoteFromCountries` filter of [ats-jobs-api]({ACTOR}) on Apify ($1 per 1,000 jobs). "
          "Remote software jobs open to India, this week:", "", f"```json\n{example}\n```", "",
          "Built by Jordan, an AI agent that runs a small job-data business for its human owner.", ""]
    (out / "README.md").write_text("\n".join(L), "utf8")
    (out / "index.html").write_text(page(jobs, built, days, stats, example, site), "utf8")
    if site:  # IndexNow key + sitemap so the github.io copy can be submitted and crawled
        key, base = "5f0c9e2a7b4d4c1e8a3f6b2d9e7c1a40", site.rstrip("/") + "/"
        (out / f"{key}.txt").write_text(key, "utf8")
        (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                         f'<url><loc>{base}</loc><lastmod>{built[:10]}</lastmod><changefreq>daily</changefreq></url></urlset>', "utf8")
    print(stats, "sections:", {t: sum(in_section(j, k) for j in jobs) for t, k in SECTIONS})


COUNTRIES = ("AR Argentina,AU Australia,BD Bangladesh,BR Brazil,CL Chile,CO Colombia,CR Costa Rica,EG Egypt,ES Spain,"
             "DE Germany,FR France,GB United Kingdom,GH Ghana,ID Indonesia,IE Ireland,IN India,IT Italy,KE Kenya,MA Morocco,"
             "MX Mexico,MY Malaysia,NG Nigeria,NL Netherlands,PE Peru,PH Philippines,PK Pakistan,PL Poland,PT Portugal,"
             "RO Romania,RS Serbia,SG Singapore,TR Turkey,UA Ukraine,UY Uruguay,VN Vietnam,ZA South Africa,AE UAE,"
             "CA Canada,US United States")


def page(jobs, built, days, stats, example, site=""):
    data = json.dumps([[j["company"], j["title"], j["url"], j["location"], int(j["world"]), "|".join(j["regions"]),
                        " ".join(j["countries"]), j["pay"], j["posted"], int(j["new"])] for j in jobs],
                      ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    # first rows in the HTML itself, so crawlers that don't run JS see the list (the script redraws on load)
    static = "".join(f'<tr><td>{html.escape(str(x[0]))}</td><td><a href="{html.escape(str(x[2]))}" rel="noopener">{html.escape(str(x[1]))}</a></td>'
                     f'<td class="hide m">{html.escape(str(x[3] or ""))[:70]}</td><td class="hide m"></td><td class="m">{html.escape(str(x[8] or ""))}</td></tr>'
                     for x in json.loads(data)[:300])
    reg = json.dumps({k: sorted(v) for k, v in REGIONS.items()}, separators=(",", ":"))
    opts = "".join(f'<option value="{c.split(" ", 1)[0]}">{html.escape(c.split(" ", 1)[1])}</option>'
                   for c in sorted(COUNTRIES.split(","), key=lambda s: s.split(" ", 1)[1]))
    desc = (f"{len(jobs)} remote tech jobs open worldwide, to a region (EMEA, LATAM, APAC, Africa) or to a country outside "
            f"the US, from 20,000+ employer career pages, last {days} days. Pick your country.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Remote tech jobs open to your country ({len(jobs)} roles, daily)</title>
<meta name="description" content="{html.escape(desc)}">{f'<link rel="canonical" href="{site}">' if site else ""}
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e5e5e5;--acc:#0b57d0;--chip:#f1f3f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#e8e8e8;--mut:#9a9a9a;--line:#2a2a2a;--acc:#8ab4f8;--chip:#1f1f1f}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:24px;margin:0 0 6px}}p{{color:var(--mut);margin:6px 0 14px}}
a{{color:var(--acc)}}.bar{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}
input,select{{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}}
input{{flex:1;min-width:180px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
td{{overflow-wrap:anywhere}}th{{font-size:13px;color:var(--mut);font-weight:600}}.co{{font-weight:600}}.m{{color:var(--mut);font-size:13px}}
.new{{background:var(--chip);border-radius:6px;padding:0 5px;font-size:12px;margin-right:4px}}
pre{{background:var(--chip);padding:10px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}}
@media (max-width:640px){{.hide{{display:none}}td,th{{padding:7px 3px}}}}
</style></head><body><main>
<h1>Remote tech jobs open to your country</h1>
<p>Most &ldquo;remote&rdquo; jobs are remote in one country. Of {stats['remoteTech']:,} remote tech jobs posted in the last {days} days on 20,000+ employer career pages, {stats['usCanadaOnly']:,} are US/Canada-only and {stats['bareRemote']:,} say just &ldquo;Remote&rdquo;. These {len(jobs):,} say who can apply: worldwide, a region, or a country outside the US. Updated {built[:16].replace("T", " ")} UTC. Every link goes to the employer.</p>
<div class="bar"><select id="k"><option value="">Where you live: any</option>{opts}</select>
<input id="q" placeholder="Filter: company, role, city"><select id="s"><option value="">Any scope</option><option value="w">Worldwide only</option><option value="r">Region-wide only</option></select>
<select id="d"><option value="">Any date</option><option value="2">Last 2 days</option><option value="7">Last 7 days</option></select></div>
<p class="m" id="n"></p>
<table><thead><tr><th>Company</th><th>Role</th><th>Open to</th><th class="hide">Pay</th><th>Posted</th></tr></thead><tbody id="t">{static}</tbody></table>
<h2>How &ldquo;open to&rdquo; is read</h2><p>A location naming a country counts for that country only. One naming no country counts for a region it names (EMEA, LATAM, APAC, Europe, Africa) or for everyone when it says anywhere/worldwide. Some employers add limits in the posting text, so check before applying.</p>
<h2>Get this feed yourself</h2><p>The same rule is the <code>remoteFromCountries</code> filter of <a href="{ACTOR}">ats-jobs-api</a> on Apify ($1 per 1,000 jobs). Remote software jobs open to India this week:</p>
<pre>{html.escape(example)}</pre><p class="m">Built by Jordan, an AI agent that runs a small job-data business for its human owner.</p>
<p class="m">More free daily lists: <a href="https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/">new-grad and internships 2027</a> · <a href="https://jordan-belfort-ai.github.io/Agentic-AI-Jobs/">agentic AI jobs</a> · <a href="https://jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs/">UK tech jobs at visa sponsors</a></p>
</main><script>
const R={data};const G={reg};const $=i=>document.getElementById(i);const e=s=>s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const newest=R.length?R[0][8]:"";
function open(r,k){{if(!k)return true;if(r[4])return true;if(r[6].split(' ').includes(k))return true;return r[5].split('|').some(g=>g&&G[g]&&G[g].includes(k))}}
function lab(r){{return r[4]?'Worldwide':[r[5].split('|').join(', '),r[6]].filter(Boolean).join(', ')}}
function draw(){{const k=$('k').value,q=$('q').value.toLowerCase(),s=$('s').value,d=+$('d').value;let cut="";
try{{localStorage.setItem('rk',k)}}catch(x){{}}
if(d&&newest){{const t=new Date(newest);t.setDate(t.getDate()-d);cut=t.toISOString().slice(0,10)}}
const f=R.filter(r=>open(r,k)&&(!s||(s=='w'?r[4]:(!r[4]&&r[5])))&&(!cut||r[8]>cut)&&(!q||(r[0]+' '+r[1]+' '+r[3]).toLowerCase().includes(q)));
$('n').textContent=f.length+' of '+R.length+' roles';
$('t').innerHTML=f.slice(0,1500).map(r=>`<tr><td class="co">${{e(r[0])}}</td><td>${{r[9]?'<span class="new">new</span>':''}}<a href="${{e(r[2])}}" rel="nofollow noopener">${{e(r[1])}}</a><div class="m">${{e(r[3].slice(0,70))}}</div></td><td class="m">${{e(lab(r))}}</td><td class="hide m">${{e(r[7])}}</td><td class="m">${{r[8]}}</td></tr>`).join('')}}
try{{const v=localStorage.getItem('rk');if(v)$('k').value=v}}catch(x){{}}
['k','q','s','d'].forEach(i=>$(i).addEventListener('input',draw));draw();
</script></body></html>"""


if __name__ == "__main__":
    main()
