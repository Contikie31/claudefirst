"""Turn a raw headline/summary into a structured deal record.

All logic is keyword/regex based so it runs without external services.
Results are best-effort; every record keeps the original headline and link.
"""

import re

# ---------------------------------------------------------------- relevance

MA_PATTERN = re.compile(
    r"\b(acquir\w*|acquisition|merg\w*|takeover|take[- ]private|take .{1,40} private|go[- ]private|going[- ]private|"
    r"buyout|buys|to buy|bought|purchas\w*|snaps? up|tender offer|bid for|offer for|"
    r"sells? .{0,40}\bto\b|sold to|divest\w*|carve[- ]out|stake in|combination)\b",
    re.I,
)

# Phrases that use M&A words in a non-deal sense.
NOISE_PATTERN = re.compile(
    r"\b(customer|user|talent|data|land|client|patient|subscriber|lead|player)[- ]acquisition\b|"
    r"\bacquisition (cost|strategy for (customers|users))\b|"
    r"\b(buy|sell|hold) rating\b|\bbuys? (shares|stock|bitcoin|gold)\b|\bshares? (bought|purchased)\b|"
    r"\b(stock|share) buyback\b|\bmerge (lanes|traffic)\b|\bhow to\b|\bbest .* to buy\b|"
    r"\bpurchas\w* (power|manager|price index|order)\b",
    re.I,
)


def is_relevant(title: str, summary: str = "") -> bool:
    if NOISE_PATTERN.search(title):
        return False
    return bool(MA_PATTERN.search(title) or MA_PATTERN.search(summary[:300]))


# ---------------------------------------------------------------- parties

_ACQ_VERBS = (
    r"agrees? to acquire|agreed to acquire|signs? (?:a )?(?:definitive )?agreement to acquire|"
    r"enters? into (?:a )?(?:definitive )?agreement to acquire|"
    r"(?:completes?|completed|closes?|closed|finali[sz]es?|announces?|unveils?) (?:its |the |a )?"
    r"(?:(?:US|C|A|AU)?[$€£₹][\d.,]+\s?(?:bn|billion|b|m|mn|million)?|[\w-]+)?\s?(?:acquisition|purchase|takeover) of|"
    r"agrees? to take|to take|announces? (?:plans|agreement) to acquire|"
    r"finalizes? (?:the )?acquisition of|expands? .{0,40}? with (?:the )?acquisition of|"
    r"has acquired|will acquire|to acquire|acquires|acquired|"
    r"agrees? to buy|to buy|buys|bought|snaps? up|scoops? up|"
    r"to purchase|purchases|purchased|takes? over|to take over|"
    r"makes? (?:a )?(?:takeover )?(?:bid|offer) for|bids? for|launches? (?:a )?(?:takeover )?bid for|"
    r"takes? (?:a )?(?:majority|controlling|minority) stake in|invests? in"
)
_PASSIVE_VERBS = (
    r"(?:agrees? )?to be acquired by|acquired by|(?:agrees? )?to be (?:bought|purchased) by|"
    r"bought by|purchased by|sold to|to be sold to|(?:agrees? )?to (?:be )?sell(?: itself)? to|"
    r"to be taken private by|taken private by|enters? into (?:a )?(?:definitive )?agreement to be acquired by"
)
_END = r"(?=\s+(?:private|for|in|from|at|amid|as|after|to (?:create|form|expand|bolster|strengthen|boost)|with|valued|worth|deal|that|which|-|–|—)\b|[,;:|(]|\s+-\s+|$)"

ACTIVE_RE = re.compile(rf"^(?P<acq>.{{2,80}}?)\s+(?:{_ACQ_VERBS})\s+(?P<tgt>.{{2,80}}?){_END}", re.I)
PASSIVE_RE = re.compile(rf"^(?P<tgt>.{{2,80}}?)\s+(?:{_PASSIVE_VERBS})\s+(?P<acq>.{{2,80}}?){_END}", re.I)
MERGER_RE = re.compile(
    r"^(?P<a>.{2,60}?)\s+(?:and|&)\s+(?P<b>.{2,60}?)\s+(?:to merge|agree to merge|announce (?:a )?merger|"
    r"in (?:all-stock |all-cash )?merger|complete merger|to combine)",
    re.I,
)

_LEADING_NOISE = re.compile(
    r"^(?:breaking|exclusive|update\d*|report|reports?|sources?|watch|video|m&a|deal news|"
    r"press release|news)\s*[:\-–—]\s*",
    re.I,
)
_TRAILING_JUNK = re.compile(r"\s*(?:'s|’s)$")
_DESCRIPTOR = re.compile(
    r"^(?:(?:the|a|an)\s+)?(?:(?:[\w-]+\s+){0,4}?(?:firm|company|startup|start-up|maker|giant|group|"
    r"provider|platform|developer|operator|specialist|leader|brand|business|retailer|bank|insurer|lender)\s+)",
    re.I,
)


_RUMOR_SUFFIX = re.compile(
    r"\s+(?:is |are )?(?:in (?:advanced |early |exclusive )?talks|nears? (?:a )?deal|said|set|plans?|"
    r"planning|looks?|looking|moves?|seeks?|seeking|reportedly|considers?|considering|weighs?|weighing|"
    r"explores?|exploring|eyes|offers?|drops?|abandons?|scraps?|ends?|wins?|secures?|gets?|receives?|"
    r"announces?|confirms?|agrees?|agreed|signs?|launches?|makes?|completes?|"
    r"(?:to|has|will|would|could|may))\b.*$",
    re.I,
)


def _clean_party(s: str) -> str:
    s = s.strip(" \"'“”‘’.")
    s = _RUMOR_SUFFIX.sub("", s)
    s = _TRAILING_JUNK.sub("", s)
    s = re.sub(r"\s+", " ", s)
    # "AI startup Foo" -> keep "Foo" only if descriptor is followed by a capitalised name
    m = _DESCRIPTOR.match(s)
    if m and s[m.end():m.end() + 1].isupper():
        s = s[m.end():]
    # Strip leading articles/qualifiers.
    s = re.sub(r"^(?:the|rival|peer|fellow|us|uk|u\.s\.|u\.k\.)\s+", "", s, flags=re.I)
    return s.strip()[:80]


def strip_publisher(title: str) -> tuple[str, str]:
    """Google News titles end with ' - Publisher'. Returns (title, publisher)."""
    m = re.match(r"^(.*\S)\s+[-–—|]\s+([^-–—|]{2,60})$", title)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return title.strip(), ""


def extract_parties(title: str) -> tuple[str, str]:
    t = _LEADING_NOISE.sub("", title).strip()
    m = MERGER_RE.search(t)
    if m:
        return _clean_party(m.group("a")), _clean_party(m.group("b"))
    m = PASSIVE_RE.search(t)
    if m:
        return _clean_party(m.group("acq")), _clean_party(m.group("tgt"))
    m = ACTIVE_RE.search(t)
    if m:
        acq, tgt = _clean_party(m.group("acq")), _clean_party(m.group("tgt"))
        if len(acq.split()) <= 10 and len(tgt.split()) <= 10:
            return acq, tgt
    return "", ""


# ---------------------------------------------------------------- value

_FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "AUD": 0.66, "INR": 0.012,
              "JPY": 0.0067, "CHF": 1.13, "SEK": 0.095, "NOK": 0.094, "DKK": 0.145, "CNY": 0.14,
              "HKD": 0.128, "SGD": 0.74, "NZD": 0.6, "ZAR": 0.055, "BRL": 0.18}
_CUR_SYMBOL = {"$": "USD", "US$": "USD", "€": "EUR", "£": "GBP", "C$": "CAD", "CA$": "CAD",
               "A$": "AUD", "AU$": "AUD", "₹": "INR", "¥": "JPY", "S$": "SGD", "NZ$": "NZD",
               "HK$": "HKD", "R$": "BRL"}
_UNIT = {"trillion": 1e6, "tn": 1e6, "billion": 1e3, "bn": 1e3, "b": 1e3, "bln": 1e3,
         "million": 1.0, "mn": 1.0, "m": 1.0, "mln": 1.0, "mm": 1.0, "crore": 1.0 / 0.1 / 100,
         "lakh crore": 1e5 / 10}

VALUE_RE = re.compile(
    r"(?P<sym>US\$|C\$|CA\$|A\$|AU\$|NZ\$|HK\$|S\$|R\$|\$|€|£|₹|¥)\s?(?P<num>\d{1,3}(?:[,.]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s?(?P<unit>trillion|tn|billion|bln|bn|b|million|mln|mn|mm|m|lakh crore|crore)?\b"
    r"|(?P<num2>\d+(?:\.\d+)?)\s?(?P<unit2>trillion|billion|bn|million|mn|crore)\s?(?P<code>USD|EUR|GBP|CAD|AUD|INR|JPY|CHF|SEK|NOK|DKK|CNY|SGD|dollars|euros|pounds)\b"
    r"|(?P<code2>USD|EUR|GBP|CAD|AUD|INR|JPY|CHF|SEK|NOK|DKK|CNY|SGD)\s?(?P<num3>\d+(?:\.\d+)?)\s?(?P<unit3>trillion|billion|bn|million|mn|m|crore)\b",
    re.I,
)
_CODE_WORDS = {"DOLLARS": "USD", "EUROS": "EUR", "POUNDS": "GBP"}


def extract_value(text: str) -> tuple[float | None, str, str]:
    """Return (value in USD millions, currency code, original text) for the largest amount found."""
    best = (None, "", "")
    for m in VALUE_RE.finditer(text):
        if m.group("num"):
            cur = _CUR_SYMBOL.get(m.group("sym").upper(), _CUR_SYMBOL.get(m.group("sym"), "USD"))
            num, unit = m.group("num"), (m.group("unit") or "").lower()
        elif m.group("num2"):
            code = m.group("code").upper()
            cur, num, unit = _CODE_WORDS.get(code, code), m.group("num2"), m.group("unit2").lower()
        else:
            cur, num, unit = m.group("code2").upper(), m.group("num3"), m.group("unit3").lower()
        if not unit:
            continue  # bare "$45" is usually a share price, not a deal size
        try:
            n = float(num.replace(",", ""))
        except ValueError:
            continue
        if unit == "crore":
            millions = n * 10  # 1 crore = 10 million
        elif unit == "lakh crore":
            millions = n * 1e6
        else:
            millions = n * _UNIT[unit]
        usd = millions * _FX_TO_USD.get(cur, 1.0)
        if best[0] is None or usd > best[0]:
            best = (round(usd, 2), cur, m.group(0).strip())
    return best


# ---------------------------------------------------------------- sector

PE_FIRMS = [
    "Blackstone", "KKR", "Carlyle", "Apollo Global", "Apollo Funds", "TPG", "Thoma Bravo", "Vista Equity",
    "Silver Lake", "EQT", "Advent International", "Bain Capital", "CVC", "Permira", "Warburg Pincus",
    "Hellman & Friedman", "Brookfield", "Clearlake", "Francisco Partners", "General Atlantic",
    "Insight Partners", "Leonard Green", "Apax", "Cinven", "BC Partners", "Ares Management",
    "Platinum Equity", "Stone Point", "Genstar", "Hg Capital", "HgCapital", "Partners Group", "Ardian",
    "3i Group", "L Catterton", "Roark Capital", "Sycamore Partners", "Searchlight", "Veritas Capital",
    "Siris Capital", "Cerberus", "Kohlberg", "Welsh, Carson", "Summit Partners", "TA Associates",
    "Accel-KKR", "Riverside Company", "HIG Capital", "H.I.G.", "Audax", "Arsenal Capital",
    "American Securities", "New Mountain", "GTCR", "Madison Dearborn", "Berkshire Partners",
    "Providence Equity", "Hellman", "Nordic Capital", "PAI Partners", "Triton", "Bridgepoint",
    "Inflexion", "Montagu", "IK Partners", "Investindustrial", "Astorg", "Eurazeo", "Wendel",
    "Tikehau", "Hillhouse", "PAG", "Baring Private Equity", "ChrysCapital", "Kedaara", "Temasek",
    "GIC", "Mubadala", "PIF", "CPP Investments", "Ontario Teachers", "OTPP", "Macquarie", "Onex",
    "Stonepeak", "Global Infrastructure Partners", "I Squared", "Vector Capital", "Marlin Equity",
    "Thomas H. Lee", "THL", "Elliott", "Starboard", "Golden Gate Capital", "Court Square",
    "Charlesbank", "Gryphon", "Alpine Investors", "Main Capital", "Battery Ventures", "JMI Equity",
    "Spectrum Equity", "Lightyear", "Turn/River", "Haveli", "Symphony Technology", "STG",
    "TDR Capital", "Bregal", "Sixth Street", "Blue Owl", "Oaktree", "Centerbridge", "Lone Star", "Sun Capital",
    "Wind Point", "Trivest", "Gauge Capital", "Kinderhook", "Shore Capital", "Levine Leichtman",
]
_PE_FIRM_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in PE_FIRMS) + r")\b")
_PE_WORDS_RE = re.compile(
    r"\b(private[- ]equity|buyout|take[- ]private|taken private|go[- ]private|going[- ]private|"
    r"portfolio company|PE[- ]backed|PE firm|sponsor[- ]backed|backed by|add[- ]on acquisition|"
    r"bolt[- ]on|platform investment|growth equity|(?:Capital|Equity|Investment) Partners|"
    r"management buy[- ]?out|MBO|LBO|leveraged buyout|recapitali[sz]ation|secondary buyout|"
    r"investment firm|asset manager .{0,20}acquir|fund (?:I|II|III|IV|V|VI|VII|VIII|IX|X)\b)",
    re.I,
)

SECTORS = {
    "Technology": r"\b(software|SaaS|AI\b|A\.I\.|artificial intelligence|machine learning|generative|LLM|cloud|"
                  r"cyber\w*|security software|semiconductor|chip\w*|data center|datacenter|analytics|"
                  r"developer|DevOps|API|tech\w*|IT services|managed services|startup|start-up|robotic\w*|"
                  r"quantum|blockchain|crypto\w*|fintech|insurtech|healthtech|edtech|proptech|martech|"
                  r"computing|server|network(?:ing)? (?:equipment|security)|identity|observability|"
                  r"database|automation|digital transformation|ERP|CRM|HR software|payroll software|"
                  r"Microsoft|Google|Alphabet|Apple|Amazon|AWS|Meta|Salesforce|Oracle|IBM|Cisco|Nvidia|"
                  r"AMD|Intel|Adobe|ServiceNow|SAP|Workday|Palo Alto Networks|CrowdStrike|Snowflake|"
                  r"Databricks|OpenAI|Anthropic|Qualcomm|Broadcom|Dell|HPE|Hewlett|Atlassian|Shopify|"
                  r"Stripe|Okta|Zscaler|Fortinet|Datadog|Cloudflare|Twilio|HubSpot|Intuit|Autodesk|"
                  r"Synopsys|Cadence|Accenture|Capgemini|Infosys|Wipro|TCS|Cognizant|Samsung|Siemens|"
                  r"Thoma Bravo|Vista Equity|Silver Lake|Francisco Partners)\b",
    "Digital & Media": r"\b(digital|e-?commerce|online|internet|marketplace|app\b|apps\b|mobile|social media|"
                       r"advertising|adtech|ad tech|marketing|agency|agencies|media|publisher|publishing|"
                       r"streaming|content|creator|influencer|gaming|video ?game|game studio|esports|"
                       r"entertainment|music|film|studio|broadcast\w*|television|TV\b|news(?:paper)?|"
                       r"podcast|web\w*|SEO|search engine|website|platform|subscription|D2C|DTC)\b",
    "Healthcare & Life Sciences": r"\b(health\w*|pharma\w*|biotech\w*|bio\w*pharm\w*|therapeutic\w*|drug\w*|"
                                  r"medical|medtech|med-tech|clinic\w*|hospital\w*|diagnostic\w*|vaccine|"
                                  r"oncology|genomic\w*|life sciences|dental|veterinar\w*|animal health|"
                                  r"care home|senior care|physician|CRO|CDMO|Pfizer|Merck|AbbVie|Novartis|"
                                  r"Roche|AstraZeneca|Sanofi|GSK|Johnson & Johnson|J&J|Eli Lilly|Lilly|"
                                  r"Bristol Myers|Amgen|Gilead|Novo Nordisk|Biogen|Regeneron|Vertex)\b",
    "Financial Services": r"\b(bank\w*|insur\w*|reinsur\w*|asset manag\w*|wealth|wealth manag\w*|"
                          r"brokerage|broker-dealer|lender|lending|mortgage|credit union|payments?|"
                          r"fintech|exchange operator|stock exchange|financial|capital markets|"
                          r"RIA|fund administrator|asset servicing|credit card)\b",
    "Energy & Resources": r"\b(oil|gas|LNG|energy|solar|wind farm|wind power|renewable\w*|power plant|"
                          r"utility|utilities|pipeline|midstream|upstream|refin\w*|mining|miner|"
                          r"gold|copper|lithium|uranium|nuclear|hydrogen|battery storage|coal|"
                          r"Exxon|Chevron|Shell|BP|TotalEnergies|ConocoPhillips)\b",
    "Industrials": r"\b(industrial\w*|manufactur\w*|aerospace|defen[cs]e|logistics|freight|trucking|"
                   r"shipping|rail\w*|airline|airport|engineering|construction|building products|"
                   r"chemical\w*|materials|steel|aluminium|aluminum|packaging|automotive|auto parts|"
                   r"vehicle|EV maker|machinery|equipment|HVAC|electrical|components|infrastructure|"
                   r"waste management|environmental services|staffing)\b",
    "Consumer & Retail": r"\b(retail\w*|restaurant\w*|food|foods|beverage\w*|drinks|brewer\w*|"
                         r"distiller\w*|wine|spirits|snack\w*|grocery|grocer|supermarket|consumer|"
                         r"brand|apparel|fashion|footwear|beauty|cosmetic\w*|skincare|fragrance|"
                         r"luxury|hotel\w*|hospitality|travel|leisure|fitness|gym|pet|toy\w*|"
                         r"furniture|home goods|franchise\w*|cafe|coffee|QSR)\b",
    "Real Estate": r"\b(real estate|REIT|propert(?:y|ies)|landlord|office building|office portfolio|"
                   r"apartment\w*|multifamily|housing|homebuilder|warehouse portfolio|"
                   r"shopping (?:centre|center|mall)|data centre portfolio|self-storage)\b",
    "Telecom": r"\b(telecom\w*|telco|wireless|broadband|fib(?:er|re)|5G|spectrum|mobile operator|"
               r"carrier|cable operator|satellite|tower\w*|Verizon|AT&T|T-Mobile|Vodafone|"
               r"Orange|Telefonica|Deutsche Telekom|BT Group|Comcast|Charter)\b",
}
_SECTOR_RES = {k: re.compile(v, re.I if k != "Technology" else 0) for k, v in SECTORS.items()}
# Technology pattern mixes case-sensitive tickers/names with lowercase keywords: add an
# insensitive pass for the lowercase keywords only.
_TECH_LOWER = re.compile(
    r"\b(software|saas|artificial intelligence|machine learning|generative ai|cloud|cyber\w*|"
    r"semiconductor|chip\w*|data cent(?:er|re)|analytics|developer|devops|tech\w*|it services|"
    r"managed services|startup|start-up|robotic\w*|quantum|blockchain|crypto\w*|fintech|insurtech|"
    r"healthtech|edtech|proptech|martech|computing|observability|database|automation)\b",
    re.I,
)


def classify_sectors(text: str) -> list[str]:
    out = []
    for name, rx in _SECTOR_RES.items():
        if name == "Technology":
            if rx.search(text) or _TECH_LOWER.search(text):
                out.append(name)
        elif rx.search(text):
            out.append(name)
    return out or ["Other"]


_PE_NAME_RE = re.compile(r"\b(?:Capital|Equity|Partners|Investments|Investors)(?: Partners| Group| Management| LLC| LP)?$")


def is_private_equity(text: str, acquirer: str = "") -> tuple[bool, str]:
    if acquirer and _PE_NAME_RE.search(acquirer) and not re.search(r"Capital One|Capitec", acquirer):
        return True, acquirer
    m = _PE_FIRM_RE.search(text)
    if m:
        return True, m.group(1)
    if _PE_WORDS_RE.search(text):
        return True, ""
    return False, ""


# ---------------------------------------------------------------- type / status

def deal_type(text: str, pe: bool) -> str:
    t = text.lower()
    if re.search(r"take[- ]private|take .{1,40} private|taken private|go(?:ing)?[- ]private", t):
        return "Take-private"
    if re.search(r"\bmerg(?:e|er|ing)\b|to combine|combination", t) and not re.search(r"acquir|buy", t):
        return "Merger"
    if re.search(r"tender offer|hostile|takeover bid|takeover offer|unsolicited", t):
        return "Tender offer / Takeover bid"
    if re.search(r"(?:majority|minority|controlling|significant|\d+(?:\.\d+)?%) stake|invests? in", t):
        return "Stake / Investment"
    if re.search(r"divest|carve[- ]out|spin[- ]?off|sells? (?:its|unit|division|business)|sold (?:its|unit)", t):
        return "Divestiture"
    if pe and re.search(r"buyout|lbo|private equity|capital|partners", t):
        return "PE buyout"
    return "Acquisition"


def deal_status(text: str) -> str:
    t = text.lower()
    if re.search(r"terminat|called off|calls off|abandon|scrap|walks away|drops? (?:bid|offer|deal)|"
                 r"blocked|blocks|rejects?|collapse", t):
        return "Terminated / Blocked"
    if re.search(r"complet|closes|closed|finali[sz]|has acquired|\bacquired\b(?! by)|concludes|"
                 r"successfully acquired", t):
        return "Completed"
    if re.search(r"in talks|talks to|considering|consider|explor|weigh|eyes|eyeing|nears?|"
                 r"reportedly|sources say|people familiar|could|may |might|mulls|rumou?r|"
                 r"approach|considers|potential|possible|interest in|bid for|offer for", t):
        return "Rumored / In talks"
    return "Announced"


# ---------------------------------------------------------------- region

_REGION_WORDS = {
    "North America": r"\b(US|U\.S\.|USA|United States|American|Canada|Canadian|Toronto|New York|"
                     r"California|Texas|NYSE|Nasdaq|TSX|Mexico|Mexican)\b",
    "UK & Ireland": r"\b(UK|U\.K\.|Britain|British|England|London|Scotland|Scottish|Wales|Ireland|Irish|"
                    r"Dublin|FTSE|AIM-listed|LSE)\b",
    "Europe": r"\b(Europe|European|EU|Germany|German|France|French|Paris|Italy|Italian|Spain|Spanish|"
              r"Netherlands|Dutch|Sweden|Swedish|Norway|Norwegian|Denmark|Danish|Finland|Finnish|"
              r"Switzerland|Swiss|Austria|Belgium|Belgian|Poland|Polish|Portugal|Nordic|DAX|Euronext)\b",
    "Asia-Pacific": r"\b(Asia|Asian|China|Chinese|Hong Kong|Japan|Japanese|Tokyo|Korea|Korean|India|"
                    r"Indian|Mumbai|Bengaluru|Bangalore|Singapore|Australia|Australian|ASX|"
                    r"New Zealand|Indonesia|Malaysia|Vietnam|Philippines|Thailand|Taiwan)\b",
    "Middle East & Africa": r"\b(Middle East|UAE|Dubai|Abu Dhabi|Saudi|Qatar|Israel|Israeli|Egypt|"
                            r"Africa|African|Nigeria|Kenya|Turkey|Turkish)\b",
    "Latin America": r"\b(Latin America|LatAm|Brazil|Brazilian|Argentina|Chile|Colombia|Peru)\b",
}
_REGION_RES = {k: re.compile(v) for k, v in _REGION_WORDS.items()}
_FEED_REGION = {"US": "North America", "GB": "UK & Ireland", "IE": "Europe", "IN": "Asia-Pacific",
                "AU": "Asia-Pacific"}


def classify_regions(text: str, feed_region: str = "") -> list[str]:
    out = [k for k, rx in _REGION_RES.items() if rx.search(text)]
    if not out and feed_region in _FEED_REGION:
        out = [_FEED_REGION[feed_region]]
    return out or ["Unknown"]


# ---------------------------------------------------------------- entry point

def classify(title: str, summary: str = "", feed_region: str = "") -> dict:
    text = f"{title}. {summary}"
    acquirer, target = extract_parties(title)
    pe, pe_firm = is_private_equity(text, acquirer)
    value_usd_m, currency, value_text = extract_value(text)
    sectors = classify_sectors(text)
    if pe and "Private Equity" not in sectors:
        sectors = sectors + ["Private Equity"]
    if sectors[0] == "Other" and len(sectors) > 1:
        sectors = sectors[1:]
    return {
        "acquirer": acquirer,
        "target": target,
        "sectors": sectors,
        "private_equity": pe,
        "pe_firm": pe_firm,
        "deal_type": deal_type(text, pe),
        "status": deal_status(title),
        "value_usd_m": value_usd_m,
        "value_currency": currency,
        "value_text": value_text,
        "regions": classify_regions(text, feed_region),
    }
