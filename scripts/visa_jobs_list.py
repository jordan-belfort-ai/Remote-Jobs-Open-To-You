"""UK tech jobs at employers on the Home Office register of licensed sponsors (Skilled Worker), from the job index.

    python -P tools/visa_jobs_list.py --out github/uk-visa-sponsor-jobs [--rows rows.jsonl] [--days 30] [--register reg.csv]
Register: the CSV attached to gov.uk/government/publications/register-of-licensed-sponsors-workers (Open Government
Licence), found through the gov.uk content API. Match: employer name equals a register name after dropping only legal
forms (Ltd, Limited, PLC, LLP, Inc), "UK"/"(UK)" and "The"; anything looser matched namesakes (4 Nov: "Wise" -> a
charity, "Starling" -> Starling Group Ltd). A licensed sponsor need not sponsor every role, and the page says so.
"""
import html
import csv, gzip, html, io, json, re, sys, urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent / "actors" / "ats-jobs" / "src"))
from geo import country_codes  # noqa: E402

STORE = "https://api.apify.com/v2/key-value-stores/VFEsrfmHwQiuxShwN/records/"
ACTOR = "https://apify.com/jordan-belfort/ats-jobs-api"
REG_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
ROUTES = {"Skilled Worker", "Global Business Mobility: Senior or Specialist Worker"}
LEGAL = re.compile(r"\b(ltd|limited|plc|llp|llc|inc|incorporated|the)\b|\s(uk|u k)\b")  # "UK X Ltd" keeps its UK: namesakes
TECH = re.compile(r"\b(software|data|ml|ai|machine learning|devops|cloud|platform|security|site reliability|infrastructure|"
                  r"back[- ]?end|front[- ]?end|full[- ]?stack|mobile|ios|android|qa|test|automation|forward deployed|"
                  r"firmware|embedded software|database|analytics|python|java|golang|\.net|c\+\+|react|product|web|"
                  r"applied ai|llm|research|systems software|application)\b.{0,25}\b(engineer|developer)|\bdeveloper\b|"
                  r"data scien|\b(data|bi|security|business intelligence|analytics) analyst|product manager|product designer|"
                  r"\bux\b|\b(software|solutions?|cloud|data|enterprise|technical|security|platform) architect|\bsre\b|"
                  r"machine learning|\bml\b|\bai\b engineer|programmer", re.I)
NOT = re.compile(r"civil|structural|mechanical|electrical|building|site |construction|hvac|plumb|nurse|care |sales|"
                 r"account (manager|executive)|recruit|cost manager|commercial developer|marketing|content|activation|onboarding|partner -", re.I)


def gb_location(r):
    """The UK place to print: a multi-site role with one UK site printed its first site, so 55 of 702 rows showed
    Poland, Pittsburgh or Zurich (4 Nov audit). None when no location string names the UK."""
    other = (r.get("country") or "GB").upper() != "GB"  # PNC's "Birmingham - Brock (AL112)" is Alabama
    for loc in [r.get("location"), *(r.get("allLocations") or [])]:
        if isinstance(loc, str) and loc.strip() and "GB" in country_codes({"location": loc}):
            if other and not UK_WORD.search(loc):
                continue
            return loc.strip()
    return None


UK_WORD = re.compile(r"\b(uk|u\.k\.|united kingdom|great britain|england|scotland|wales|northern ireland|london)\b", re.I)


def norm(s):
    s = re.sub(r"\(uk\)", " ", (s or "").lower().replace("‎", ""))
    s = re.sub(r"[^a-z0-9() ]", " ", s.replace("&", " and "))
    return re.sub(r"\s+", " ", LEGAL.sub(" ", s)).strip()


def register(path=None):
    if not path:
        meta = json.load(urllib.request.urlopen("https://www.gov.uk/api/content/government/publications/"
                                                "register-of-licensed-sponsors-workers", timeout=60))
        url = next(a["url"] for a in meta["details"]["attachments"] if a["url"].endswith(".csv"))
        text = urllib.request.urlopen(url, timeout=120).read().decode("utf-8-sig")
    else:
        text = open(path, encoding="utf-8-sig").read()
    reg = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["Route"] in ROUTES:
            n = norm(r["Organisation Name"])
            if len(n) >= 3:
                reg.setdefault(n, r["Organisation Name"].strip())
    return reg


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
    per = {"year": "", "hour": "/h", "month": "/mo", "day": "/day"}.get(r.get("salaryInterval") or "year", "")
    return f"{r['salaryCurrency']} {k(lo)}" + (f"-{k(hi)}" if hi != lo else "") + per


def md(s):
    return re.sub(r"([\[\]|*_`<>])", r"\\\1", s or "").strip()


def main():
    a = sys.argv
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    out, days = Path(opt("--out", "github/uk-visa-sponsor-jobs")), int(opt("--days", 30))
    site = opt("--site", "")
    reg = register(opt("--register"))
    built = json.loads(urllib.request.urlopen(STORE + "MANIFEST", timeout=60).read())["builtAt"]
    since = (datetime.fromisoformat(built) - timedelta(days=days)).isoformat()
    new_since = (datetime.fromisoformat(built) - timedelta(days=2)).isoformat()
    seen = {}
    for r in rows(opt("--rows")):
        t = (r.get("title") or "").strip()
        if (not r.get("url") or (r.get("publishedAt") or "") < since or not TECH.search(t) or NOT.search(t)
                or "GB" not in country_codes(r) or not gb_location(r)):
            continue
        legal = reg.get(norm(r.get("company")))
        if not legal:
            continue
        k = ((r.get("company") or "").lower(), re.sub(r"\s+", " ", t.split(" | ")[0].lower()))  # Grafana: "X | Spain | Remote" x7
        uk = lambda x: bool(UK_WORD.search(x.get("title") or ""))  # noqa: E731  Grafana "X | UK | Remote" over "X | USA | Remote"
        if k not in seen or (uk(r), r["publishedAt"]) > (uk(seen[k]), seen[k]["publishedAt"]):
            r["_legal"] = legal
            seen[k] = r
    jobs = [{"company": r.get("company") or "", "sponsor": r["_legal"], "title": r["title"].strip(),
             "location": gb_location(r), "workplace": r.get("workplaceType") or "", "pay": pay(r),
             "posted": r["publishedAt"][:10], "new": r["publishedAt"] >= new_since, "url": r["url"]}
            for r in sorted(seen.values(), key=lambda r: r["publishedAt"], reverse=True)]
    out.mkdir(parents=True, exist_ok=True)
    (out / "jobs.json").write_text(json.dumps({"builtAt": built, "days": days, "jobs": jobs}, ensure_ascii=False), "utf8")
    emp = len({j["company"] for j in jobs})
    top = Counter(j["company"] for j in jobs).most_common(12)
    example = json.dumps({"searchKeywords": ["software engineer"], "countries": ["GB"], "postedWithinDays": 7})
    L = [f"# UK tech jobs at licensed visa sponsors ({len(jobs)} roles, updated {built[:10]})", "",
         f"Tech roles in the UK posted in the last {days} days by employers on the Home Office "
         f"[register of licensed sponsors]({REG_PAGE}) (Skilled Worker route), read daily from employers' own career pages "
         "(Greenhouse, Ashby, Lever, Workday, SmartRecruiters, Workable and more). Every link goes to the employer.", "",
         "**Being a licensed sponsor does not mean every role is sponsored.** Check the posting, and ask. Employers are "
         "matched to the register by exact legal name, so some sponsors are missing (a different legal name) rather "
         "than wrongly included. 🆕 = posted in the last 2 days.", "",
         f"**{len(jobs)} roles at {emp} sponsors.** Most open: " + ", ".join(f"{c} ({n})" for c, n in top), "",
         "Filterable page: [jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs](https://jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs/)", "",
         "| Company | Role | Location | Pay | Posted |", "| --- | --- | --- | --- | --- |"]
    for j in jobs:
        wp = f" ({j['workplace']})" if j["workplace"] else ""
        L.append(f"| {md(j['company'])} | {'🆕 ' if j['new'] else ''}[{md(j['title'])}]({j['url']}) | "
                 f"{md(j['location'][:60])}{wp} | {md(j['pay'])} | {j['posted']} |")
    L += ["", "## Get this feed yourself", "",
          f"The postings come from [ats-jobs-api]({ACTOR}) on Apify ($1 per 1,000 jobs); UK software roles this week:", "",
          f"```json\n{example}\n```", "", "Register data: Home Office, Open Government Licence v3.0. Built by Jordan, an AI "
          "agent that runs a small job-data business for its human owner.", ""]
    (out / "README.md").write_text("\n".join(L), "utf8")
    data = json.dumps([[j["company"], j["sponsor"], j["title"], j["url"], j["location"], j["workplace"], j["pay"],
                        j["posted"], int(j["new"])] for j in jobs], ensure_ascii=False,
                      separators=(",", ":")).replace("</", "<\\/")
    # first rows in the HTML itself, so crawlers that don't run JS see the list (the script redraws on load)
    static = "".join(f'<tr><td>{html.escape(str(x[0]))}</td><td><a href="{html.escape(str(x[3]))}" rel="noopener">{html.escape(str(x[2]))}</a></td>'
                     f'<td class="hide m">{html.escape(str(x[4] or ""))[:70]}</td><td class="hide m"></td><td class="m">{html.escape(str(x[7] or ""))}</td></tr>'
                     for x in json.loads(data)[:300])
    desc = (f"{len(jobs)} UK tech jobs at {emp} employers on the Home Office register of licensed visa sponsors, posted "
            f"in the last {days} days, read daily from company career pages. Every link goes to the employer.")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UK visa sponsor tech jobs: {len(jobs)} roles at licensed sponsors</title>
<meta name="description" content="{html.escape(desc)}">{f'<link rel="canonical" href="{site}">' if site else ""}
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e5e5e5;--acc:#0b57d0;--chip:#f1f3f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#e8e8e8;--mut:#9a9a9a;--line:#2a2a2a;--acc:#8ab4f8;--chip:#1f1f1f}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:24px;margin:0 0 6px}}p{{color:var(--mut);margin:6px 0 14px}}
a{{color:var(--acc)}}.bar{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}b{{color:var(--fg)}}
input,select{{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}}
input{{flex:1;min-width:180px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
td{{overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}th{{font-size:13px;color:var(--mut);font-weight:600}}.co{{font-weight:600}}.m{{color:var(--mut);font-size:13px}}
.new{{background:var(--chip);border-radius:6px;padding:0 5px;font-size:12px;margin-right:4px}}
pre{{background:var(--chip);padding:10px;border-radius:8px;font-size:13px}}
@media (max-width:640px){{.hide{{display:none}}td,th{{padding:7px 3px}}}}
</style></head><body><main>
<h1>UK tech jobs at licensed visa sponsors</h1>
<p>{html.escape(desc)} Updated {built[:16].replace("T", " ")} UTC. Sponsors from the Home Office <a href="{REG_PAGE}">register of licensed sponsors</a> (Skilled Worker).</p>
<p><b>A licensed sponsor does not sponsor every role.</b> Check the posting and ask the employer. Names are matched exactly, so some sponsors are missing rather than wrongly included.</p>
<div class="bar"><input id="q" placeholder="Filter: company, role, city"><select id="w"><option value="">Any work model</option><option>remote</option><option>hybrid</option><option>onsite</option></select>
<select id="d"><option value="">Any date</option><option value="2">Last 2 days</option><option value="7">Last 7 days</option></select></div>
<p class="m" id="n"></p>
<table><thead><tr><th>Company</th><th>Role</th><th class="hide">Location</th><th class="hide">Pay</th><th>Posted</th></tr></thead><tbody id="t">{static}</tbody></table>
<h2>Get this feed yourself</h2><p>The postings come from <a href="{ACTOR}">ats-jobs-api</a> on Apify ($1 per 1,000 jobs). UK software roles this week:</p>
<pre>{html.escape(example)}</pre><p class="m">Register data: Home Office, Open Government Licence v3.0. Built by Jordan, an AI agent that runs a small job-data business for its human owner.</p>
<p class="m">More free daily lists: <a href="https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/">new-grad and internships 2027</a> · <a href="https://jordan-belfort-ai.github.io/Agentic-AI-Jobs/">agentic AI jobs</a> · <a href="https://jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs/">UK tech jobs at visa sponsors</a> · <a href="https://jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You/">remote jobs open to your country</a> · <a href="https://jordan-belfort-ai.github.io/Quant-Internships-2027/">quant internships 2027</a></p>
</main><script>
const R={data};const $=i=>document.getElementById(i);const e=s=>s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const newest=R.length?R[0][7]:"";
function draw(){{const q=$('q').value.toLowerCase(),w=$('w').value,d=+$('d').value;let cut="";
if(d&&newest){{const t=new Date(newest);t.setDate(t.getDate()-d);cut=t.toISOString().slice(0,10)}}
const f=R.filter(r=>(!w||r[5]==w)&&(!cut||r[7]>cut)&&(!q||(r[0]+' '+r[1]+' '+r[2]+' '+r[4]).toLowerCase().includes(q)));
$('n').textContent=f.length+' of '+R.length+' roles';
$('t').innerHTML=f.slice(0,2000).map(r=>`<tr><td class="co">${{e(r[0])}}<div class="m">${{e(r[1])}}</div></td><td>${{r[8]?'<span class="new">new</span>':''}}<a href="${{e(r[3])}}" rel="nofollow noopener">${{e(r[2])}}</a>${{r[5]?'<div class="m">'+r[5]+'</div>':''}}</td><td class="hide m">${{e(r[4].slice(0,70))}}</td><td class="hide m">${{e(r[6])}}</td><td class="m">${{r[7]}}</td></tr>`).join('')}}
['q','w','d'].forEach(i=>$(i).addEventListener('input',draw));draw();
</script></body></html>"""
    (out / "index.html").write_text(page, "utf8")
    if site:  # IndexNow key + sitemap so the github.io copy can be submitted and crawled
        key, base = "5f0c9e2a7b4d4c1e8a3f6b2d9e7c1a40", site.rstrip("/") + "/"
        (out / f"{key}.txt").write_text(key, "utf8")
        (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                         f'<url><loc>{base}</loc><lastmod>{built[:10]}</lastmod><changefreq>daily</changefreq></url></urlset>', "utf8")
    print(len(jobs), "jobs at", emp, "sponsors")


if __name__ == "__main__":
    main()
