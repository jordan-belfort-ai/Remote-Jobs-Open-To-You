"""Country codes for job rows: the ATS's own country field (ISO code or name) where it has one, else read from the
location text (US states, Canadian provinces, country names, big cities). Greenhouse, Workday and Personio rows
carry no country, and the others spell it 'us', 'US', 'USA' or 'United States'."""
import re

_NAMES = {
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US", "us": "US",
    "america": "US", "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB", "scotland": "GB",
    "wales": "GB", "northern ireland": "GB", "canada": "CA", "germany": "DE", "deutschland": "DE", "france": "FR",
    "spain": "ES", "españa": "ES", "italy": "IT", "italia": "IT", "netherlands": "NL", "the netherlands": "NL",
    "nederland": "NL", "belgium": "BE", "switzerland": "CH", "schweiz": "CH", "austria": "AT", "österreich": "AT",
    "ireland": "IE", "portugal": "PT", "poland": "PL", "polska": "PL", "sweden": "SE", "sverige": "SE", "norway": "NO",
    "norge": "NO", "denmark": "DK", "danmark": "DK", "finland": "FI", "suomi": "FI", "czech republic": "CZ",
    "czechia": "CZ", "romania": "RO", "hungary": "HU", "greece": "GR", "turkey": "TR", "türkiye": "TR",
    "israel": "IL", "united arab emirates": "AE", "uae": "AE", "saudi arabia": "SA", "qatar": "QA", "egypt": "EG",
    "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "india": "IN", "china": "CN", "japan": "JP",
    "south korea": "KR", "korea": "KR", "singapore": "SG", "hong kong": "HK", "taiwan": "TW", "australia": "AU",
    "new zealand": "NZ", "philippines": "PH", "indonesia": "ID", "malaysia": "MY", "thailand": "TH", "vietnam": "VN",
    "viet nam": "VN", "pakistan": "PK", "bangladesh": "BD", "brazil": "BR", "brasil": "BR", "mexico": "MX",
    "méxico": "MX", "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE", "perú": "PE",
    "costa rica": "CR", "uruguay": "UY", "ukraine": "UA", "lithuania": "LT", "latvia": "LV", "estonia": "EE",
    "serbia": "RS", "croatia": "HR", "bulgaria": "BG", "slovakia": "SK", "slovenia": "SI", "luxembourg": "LU",
    "cyprus": "CY", "tanzania": "TZ", "ghana": "GH", "rwanda": "RW", "uganda": "UG", "ethiopia": "ET", "sri lanka": "LK", "nepal": "NP", "malta": "MT", "iceland": "IS", "morocco": "MA", "puerto rico": "PR",
}
US_STATES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
    "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana", "ME": "maine",
    "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi", "MO": "missouri",
    "MT": "montana", "NE": "nebraska", "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico",
    "NY": "new york", "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee",
    "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia",
}
CA_PROVINCES = {"ON": "ontario", "QC": "quebec", "BC": "british columbia", "AB": "alberta", "MB": "manitoba",
                "SK": "saskatchewan", "NS": "nova scotia", "NB": "new brunswick", "NL": "newfoundland", "PE": "prince edward island"}
_CITIES = {
    "US": "san francisco|new york|nyc|seattle|los angeles|chicago|boston|austin|denver|atlanta|washington, d\\.?c|"
          "san jose|san diego|palo alto|mountain view|menlo park|sunnyvale|redwood city|santa clara|cambridge, ma|"
          "miami|dallas|houston|phoenix|philadelphia|pittsburgh|portland|salt lake city|minneapolis|detroit|nashville|"
          "raleigh|charlotte|baltimore|arlington|brooklyn|silicon valley|bay area|oakland|irvine|boulder|columbus",
    "GB": "london|manchester|edinburgh|bristol|birmingham|glasgow|leeds|belfast|oxford|reading",
    "DE": "bochum|wiesbaden|mainz|münster|aachen|freiburg|heidelberg|potsdam|berlin|munich|münchen|muenchen|hamburg|frankfurt|köln|cologne|stuttgart|düsseldorf|dusseldorf|leipzig|"
          "dresden|hannover|nürnberg|nuremberg|karlsruhe|bonn|essen|dortmund|bremen|mannheim",
    "FR": "paris|lyon|marseille|toulouse|lille|bordeaux|nantes|nice",
    "NL": "amsterdam|rotterdam|utrecht|eindhoven|the hague|den haag",
    "ES": "madrid|barcelona|valencia|seville|sevilla|málaga|malaga",
    "IT": "milan|milano|rome|roma|turin|torino",
    "IE": "dublin|cork",
    "CH": "zurich|zürich|geneva|genève|basel|lausanne|zug",
    "AT": "vienna|wien|graz|linz|salzburg",
    "SE": "stockholm|gothenburg|göteborg|malmö",
    "DK": "copenhagen|københavn|aarhus",
    "NO": "oslo|bergen",
    "FI": "helsinki|espoo",
    "PL": "warsaw|warszawa|kraków|krakow|wrocław|wroclaw|gdańsk|gdansk|poznań",
    "PT": "lisbon|lisboa|porto",
    "BE": "brussels|bruxelles|antwerp|ghent",
    "CZ": "prague|praha|brno",
    "CA": "toronto|vancouver|montreal|montréal|ottawa|calgary|waterloo|edmonton",
    "IN": "bangalore|bengaluru|mumbai|hyderabad|pune|chennai|gurgaon|gurugram|noida|new delhi|delhi|kolkata|ahmedabad|jaipur|kochi|coimbatore|indore|chandigarh|trivandrum",
    "SG": "singapore", "TH": "bangkok", "ID": "jakarta", "UA": "kyiv|kiev|lviv", "RO": "bucharest|cluj", "HU": "budapest", "GR": "athens", "VN": "ho chi minh|hanoi", "MY": "kuala lumpur", "NG": "lagos", "KE": "nairobi", "ZA": "cape town|johannesburg", "HK": "hong kong", "JP": "tokyo|osaka", "KR": "seoul", "CN": "shanghai|beijing|shenzhen",
    "AU": "sydney|melbourne|brisbane|perth|adelaide|canberra", "NZ": "auckland|wellington",
    "AE": "dubai|abu dhabi", "IL": "tel aviv|jerusalem|haifa", "BR": "são paulo|sao paulo|rio de janeiro",
    "MX": "mexico city|ciudad de méxico|guadalajara|monterrey", "AR": "buenos aires", "CO": "bogotá|bogota|medellín",
    "PH": "manila|makati|taguig|cebu", "TR": "istanbul|ankara", "GE": "tbilisi", "AM": "yerevan", "RS": "belgrade", "BG": "sofia", "EG": "cairo", "MA": "casablanca", "PK": "karachi|lahore|islamabad",
}
_CITY_RE = [(cc, re.compile(r"(?<!\w)(?:" + pat + r")(?!\w)")) for cc, pat in _CITIES.items()]

# More capitals and big cities (4 Nov). Checked after the US state/province rules, so 'Lima, OH' stays American.
for _cc, _pat in {
    "DO": "santo domingo", "EC": "quito|guayaquil", "PE": "lima", "UY": "montevideo", "GT": "guatemala city",
    "NG": "abuja", "GH": "accra", "ET": "addis ababa", "MA": "rabat", "TN": "tunis", "DZ": "algiers", "SN": "dakar",
    "UG": "kampala", "RW": "kigali", "TZ": "dar es salaam", "ZA": "durban|pretoria", "BD": "dhaka", "LK": "colombo",
    "NP": "kathmandu", "KH": "phnom penh", "MM": "yangon", "KZ": "almaty|astana", "UZ": "tashkent", "AZ": "baku",
    "BY": "minsk", "MD": "chisinau|chișinău", "BA": "sarajevo", "AL": "tirana", "MK": "skopje", "HR": "zagreb",
    "SI": "ljubljana", "SK": "bratislava", "LT": "vilnius|kaunas", "LV": "riga", "EE": "tallinn", "IS": "reykjavik",
    "CY": "nicosia|limassol", "GR": "thessaloniki", "SA": "riyadh|jeddah", "QA": "doha", "BH": "manama",
    "OM": "muscat", "JO": "amman", "LB": "beirut", "TW": "taipei|hsinchu|taichung", "JP": "yokohama|kyoto|fukuoka",
    "KR": "busan", "CN": "guangzhou|hangzhou|chengdu|suzhou", "VN": "da nang", "ID": "bandung|surabaya",
    "MY": "penang", "TH": "chiang mai", "BR": "belo horizonte|curitiba|porto alegre|florianópolis|florianopolis|recife",
    "MX": "puebla|querétaro|queretaro|tijuana"
}.items():
    _CITY_RE.append((_cc, re.compile(r"(?<!\w)(?:" + _pat + r")(?!\w)")))
_NAME_RE = re.compile(r"(?<!\w)(" + "|".join(sorted((re.escape(n) for n in _NAMES if len(n) > 3), key=len, reverse=True)) + r")(?!\w)")
_STATE_NAME_RE = re.compile(r"(?<!\w)(" + "|".join(sorted(US_STATES.values(), key=len, reverse=True)) + r")(?!\w)")
_PROV_NAME_RE = re.compile(r"(?<!\w)(" + "|".join(CA_PROVINCES.values()) + r")(?!\w)")
_ABBR_RE = re.compile(r"(?:^|,|\s-|\(|[a-z]\s)\s*([A-Z]{2})(?=\b(?!\.))")  # 'Austin, TX', 'ND, Fargo', 'Olathe KS', 'Boston (MA)'
_ISO2 = set(_NAMES.values())
_CITY_RE_IN = dict(_CITY_RE)["IN"]

# Checked only after the US/Canada checks fail, so 'Lebanon, NH' or 'Athens, GA' stay American.
_EXTRA = {
    "albania": "AL", "algeria": "DZ", "andorra": "AD", "angola": "AO", "armenia": "AM", "azerbaijan": "AZ",
    "bahrain": "BH", "bahamas": "BS", "barbados": "BB", "belarus": "BY", "belize": "BZ", "benin": "BJ",
    "bermuda": "BM", "bhutan": "BT", "bolivia": "BO", "bosnia": "BA", "bosnia and herzegovina": "BA",
    "botswana": "BW", "brunei": "BN", "burkina faso": "BF", "burundi": "BI", "cambodia": "KH", "cameroon": "CM",
    "cape verde": "CV", "cayman islands": "KY", "curaçao": "CW", "curacao": "CW", "côte d'ivoire": "CI",
    "ivory coast": "CI", "democratic republic of the congo": "CD", "dr congo": "CD", "djibouti": "DJ",
    "dominican republic": "DO", "ecuador": "EC", "el salvador": "SV", "eritrea": "ER", "eswatini": "SZ", "fiji": "FJ",
    "gabon": "GA", "gambia": "GM", "gibraltar": "GI", "greenland": "GL", "guatemala": "GT", "guyana": "GY",
    "haiti": "HT", "honduras": "HN", "iran": "IR", "iraq": "IQ", "jamaica": "JM", "kazakhstan": "KZ",
    "kosovo": "XK", "kuwait": "KW", "kyrgyzstan": "KG", "laos": "LA", "lesotho": "LS", "liberia": "LR",
    "libya": "LY", "liechtenstein": "LI", "macau": "MO", "macao": "MO", "madagascar": "MG", "malawi": "MW",
    "maldives": "MV", "mauritania": "MR", "mauritius": "MU", "moldova": "MD", "monaco": "MC", "mongolia": "MN",
    "montenegro": "ME", "mozambique": "MZ", "myanmar": "MM", "namibia": "NA", "nicaragua": "NI",
    "north macedonia": "MK", "macedonia": "MK", "oman": "OM", "papua new guinea": "PG", "paraguay": "PY",
    "russia": "RU", "russian federation": "RU", "san marino": "SM", "senegal": "SN", "seychelles": "SC",
    "sierra leone": "SL", "somalia": "SO", "sudan": "SD", "suriname": "SR", "syria": "SY", "tajikistan": "TJ",
    "togo": "TG", "trinidad and tobago": "TT", "tunisia": "TN", "turkmenistan": "TM", "uzbekistan": "UZ",
    "venezuela": "VE", "yemen": "YE", "zambia": "ZM", "zimbabwe": "ZW", "lebanon": "LB", "jordan": "JO",
    "cuba": "CU", "panama": "PA", "georgia": "GE", "mali": "ML", "niger": "NE", "chad": "TD", "guinea": "GN",
    "jersey": "JE", "guernsey": "GG", "isle of man": "IM", "aruba": "AW", "palestine": "PS",
}
_EXTRA_RE = re.compile(r"(?<!\w)(" + "|".join(sorted((re.escape(n) for n in _EXTRA), key=len, reverse=True)) + r")(?!\w)")


def from_field(value) -> str | None:
    """'us', 'US', 'USA', 'United States', 'Deutschland' -> ISO 3166 alpha-2."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if len(v) == 2 and v.isalpha():
        return "GB" if v.upper() == "UK" else v.upper()
    return _NAMES.get(v.lower())


def from_text(text: str | None) -> str | None:
    """Country of a free-text location, or None when it doesn't say ('Remote', '3 Locations')."""
    if not text:
        return None
    low = text.lower()
    m = _NAME_RE.search(low.replace("new mexico", "nm"))
    if m:
        return _NAMES[m.group(1)]
    if re.search(r"(?<![\w.])(us|usa|u\.s\.a?\.?)(?![\w])", low) or low.startswith("us >") or low.startswith("us-"):
        return "US"
    if re.search(r"(?<![\w.])uk(?![\w])", low):
        return "GB"
    for m in _ABBR_RE.finditer(text):
        ab = m.group(1)
        if ab == "IN" and _CITY_RE_IN.search(low):
            return "IN"  # 'Bengaluru, IN' is India, 'Carmel, IN' Indiana
        if ab in US_STATES:
            return "US"
        if ab in CA_PROVINCES:
            return "CA"
    if _PROV_NAME_RE.search(low):
        return "CA"
    m = _STATE_NAME_RE.search(low)
    if m and m.group(1) not in ("georgia", "washington"):  # 'Paris, Texas'; Georgia the country, Washington the city
        return "US"
    for cc, rx in _CITY_RE:
        if rx.search(low):
            return cc
    if m:
        return "US"
    m = _EXTRA_RE.search(low)  # 'Georgia' and 'New Jersey' already returned US above
    if m:
        return _EXTRA[m.group(1)]
    return None


def country_codes(row: dict) -> list[str]:
    """Every country a job is in: the ATS field first, then each location string. Empty when nothing says."""
    out: list[str] = []
    cc = from_field(row.get("country"))
    if cc:
        out.append(cc)
    for loc in [row.get("location"), *(row.get("allLocations") or [])]:
        if not isinstance(loc, str):
            continue
        # 'Remote (US/Canada)', 'UK or Ireland', 'Germany | Austria': every country it names, not only the first
        parts = [loc] + [p for p in _MULTI_SPLIT.split(loc) if p and p.strip()] if _MULTI_SPLIT.search(loc) else [loc]
        for part in parts:
            cc = from_text(part)
            if cc and cc not in out:
                out.append(cc)
    return out


_MULTI_SPLIT = re.compile(r"\s*(?:/|\||;|\bor\b|\band\b|&)\s*")


_STATE_BY_NAME = {v: k for k, v in US_STATES.items()} | {v: k for k, v in CA_PROVINCES.items()}
_STATE_CODES = set(US_STATES) | set(CA_PROVINCES)


def state_code(value) -> str | None:
    """'TX', 'texas', 'Ontario' -> the two-letter US state or Canadian province code."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if len(v) == 2 and v.upper() in _STATE_CODES:
        return v.upper()
    return _STATE_BY_NAME.get(v.lower())


def state_codes(row: dict) -> list[str]:
    """US states and Canadian provinces a job is in, read from its location strings. Empty when none says."""
    out: list[str] = []
    for loc in [row.get("location"), *(row.get("allLocations") or [])]:
        if not isinstance(loc, str):
            continue
        low = loc.lower()
        for m in _ABBR_RE.finditer(loc):
            if m.group(1) in _STATE_CODES and m.group(1) not in out:
                out.append(m.group(1))
        for name, code in _STATE_BY_NAME.items():
            if code not in out and re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", low):
                out.append(code)
    return out


# Regions remote postings name instead of a country ('Remote - EMEA', 'Europe (remote)', 'LATAM'), as ISO codes.
_EU = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
_EUROPE = _EU | set("GB NO CH IS UA RS BA ME MK AL MD XK BY LI MC SM AD GI JE GG IM".split())
_MIDEAST = set("AE SA QA BH KW OM IL JO LB IQ IR TR SY YE PS EG".split())
_AFRICA = set("DZ AO BJ BW BF BI CM CV TD CD CI DJ EG ER SZ ET GA GM GH GN KE LS LR LY MG MW ML MR MU MA MZ NA NE NG "
              "RW SN SC SL SO ZA SD TZ TG TN UG ZM ZW".split())
_ASIA = set("JP KR CN HK TW SG MY TH ID PH VN IN PK BD LK NP KH MM LA MN MO BN BT MV KZ UZ KG TJ TM".split())
_APAC = _ASIA | set("AU NZ FJ PG".split())
_LATAM = set("MX GT BZ SV HN NI CR PA CU DO HT JM PR CO VE EC PE BO BR PY UY AR CL GY SR TT BS BB AW CW KY".split())
_REGIONS = [
    (r"emea", _EUROPE | _MIDEAST | _AFRICA), (r"europe|european union|eu|eea", _EUROPE), (r"dach", {"DE", "AT", "CH"}),
    (r"nordics?", {"SE", "NO", "DK", "FI", "IS"}), (r"benelux", {"BE", "NL", "LU"}),
    (r"apac|asia[- ]pacific|asia|south ?east asia", _APAC), (r"anz|oceania", {"AU", "NZ"}),
    (r"latam|latin america|south america|central america|caribbean", _LATAM),
    (r"amer|americas", _LATAM | {"US", "CA"}), (r"north america", {"US", "CA", "MX"}),
    (r"mena|middle east", _MIDEAST | {"MA", "DZ", "TN", "LY"}), (r"africa", _AFRICA),
]
_REGION_RE = [(re.compile(r"(?<![\w])(?:" + p + r")(?![\w])"), codes) for p, codes in _REGIONS]
_WORLD_RE = re.compile(r"(?<![\w])(anywhere|worldwide|global|globally|international|any location|work from anywhere)(?![\w])")


def remote_open_to(row: dict, wanted: set[str]) -> bool:
    """A remote job someone in one of `wanted` (ISO codes) can take. Each location string is read on its own: one that
    names a country counts only for that country ('Anywhere, USA' is US, 'South Africa' is ZA, not Africa); one that
    names no country counts when it says anywhere / worldwide or names a region holding a wanted country
    ('Remote - EMEA' for DE). Jobs that say only 'Remote' are not kept."""
    if wanted & set(row.get("countryCodes") or country_codes(row)):
        return True
    if from_field(row.get("country")):
        return False  # the ATS pins the job to another country
    for loc in [row.get("location"), *(row.get("allLocations") or [])]:
        if not isinstance(loc, str) or not loc.strip() or from_text(loc):
            continue
        low = loc.lower()
        if _WORLD_RE.search(low) or any(rx.search(low) and wanted & codes for rx, codes in _REGION_RE):
            return True
    return False
