"""Map free-text ``sectors`` from ``companies.yaml`` to ≤20 coarse industries.

Used at index generation time only; granular ``sectors`` stay in YAML unchanged.
"""

from __future__ import annotations

# Canonical filter labels (dropdown order). "Other" is last for UX.
INDUSTRIES_ORDERED: tuple[str, ...] = (
    "AI & Machine Learning",
    "Cybersecurity",
    "Data & Analytics",
    "Cloud & Infrastructure",
    "Software & SaaS",
    "IT Services & Consulting",
    "Fintech & Insurance",
    "Health & Life Sciences",
    "E-commerce & Retail",
    "Marketing & AdTech",
    "Gaming & Entertainment",
    "Travel, Mobility & Logistics",
    "Industrial & Manufacturing",
    "Energy & Resources",
    "HR & Education Tech",
    "Gov, Defense & Aerospace",
    "Hardware, IoT & Embedded",
    "Consumer & Hospitality",
    "Professional & Business Services",
    "Other",
)

_INDUSTRY_SET = frozenset(INDUSTRIES_ORDERED)
_INDUSTRY_RANK = {name: i for i, name in enumerate(INDUSTRIES_ORDERED)}

# Exact sector string (after normalize_sector: strip + collapse spaces), lowercased.
_EXACT: dict[str, str] = {
    "ai": "AI & Machine Learning",
    "iot": "Hardware, IoT & Embedded",
    "data": "Data & Analytics",
    "erp": "Software & SaaS",
    "5g": "Cloud & Infrastructure",
    "saas": "Software & SaaS",
    "cms": "Software & SaaS",
    "seo": "Marketing & AdTech",
    "communications": "Cloud & Infrastructure",
    "consulting": "Professional & Business Services",
    "advisory": "Professional & Business Services",
    "strategy": "Professional & Business Services",
    "operations": "Professional & Business Services",
    "innovation": "Professional & Business Services",
    "technology": "IT Services & Consulting",
    "analytics": "Data & Analytics",
    "automation": "Industrial & Manufacturing",
    "security": "Cybersecurity",
    "cloud": "Cloud & Infrastructure",
    "infrastructure": "Cloud & Infrastructure",
    "internet": "IT Services & Consulting",
    "information": "IT Services & Consulting",
    "computers": "Hardware, IoT & Embedded",
    "electronics manufacturing": "Hardware, IoT & Embedded",
    "manufacturing": "Industrial & Manufacturing",
    "energy": "Energy & Resources",
    "gas": "Energy & Resources",
    "oil": "Energy & Resources",
    "insurance": "Fintech & Insurance",
    "banking": "Fintech & Insurance",
    "health": "Health & Life Sciences",
    "healthcare": "Health & Life Sciences",
    "marketing": "Marketing & AdTech",
    "advertising": "Marketing & AdTech",
    "entertainment": "Gaming & Entertainment",
    "hospitality": "Consumer & Hospitality",
    "logistics": "Travel, Mobility & Logistics",
    "transportation": "Travel, Mobility & Logistics",
    "leasing": "Professional & Business Services",
    "investment": "Fintech & Insurance",
    "deep tech": "Software & SaaS",
    "startups": "Professional & Business Services",
    "industrials": "Industrial & Manufacturing",
    "book": "Marketing & AdTech",
    "agency": "Marketing & AdTech",
    "media": "Marketing & AdTech",
    "search": "Marketing & AdTech",
    "tech": "IT Services & Consulting",
    "software": "Software & SaaS",
    "software engineering": "Software & SaaS",
    "recruitment": "HR & Education Tech",
    "staffing": "HR & Education Tech",
    "utilities": "Energy & Resources",
    "networks": "Cloud & Infrastructure",
    "messaging": "Cloud & Infrastructure",
}

# (industry, substrings) — first matching rule wins. Sectors compared lowercased.
_SUBSTRING_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Gaming & Entertainment",
        (
            "gaming",
            "betting",
            "igaming",
            "lottery",
            "computer games",
            "gametech",
            "sports betting",
            "game development",
            "online gaming",
        ),
    ),
    (
        "Gov, Defense & Aerospace",
        (
            "defense",
            "defence",
            "military",
            "aerospace",
            "space manufacturing",
            "civil protection",
            "public safety",
            "critical infrastructure protection",
            "night vision",
            "thermal imaging",
            "geospatial intelligence",
            "government",
            "govtech",
            "drones",
            "smart cities",
        ),
    ),
    (
        "Health & Life Sciences",
        (
            "health",
            "healthcare",
            "pharma",
            "biopharm",
            "biotech",
            "clinical",
            "medical",
            "patient",
            "cancer care",
            "life sciences",
            "nutrition",
            "digital health",
            "foodtech",
        ),
    ),
    (
        "Fintech & Insurance",
        (
            "fintech",
            "banktech",
            "insurtech",
            "blockchain",
            "web3",
            "bitcoin",
            "cryptocurrency",
            "crypto",
            "payment",
            "trading platform",
            "asset management",
            "investment services",
            "venture capital",
            "broker",
            "credit management",
            "debt management",
            "ethical debt",
            "financial services",
            "financial software",
            "banking software",
            "price intelligence",
            "global trade intelligence",
            "personal finance",
        ),
    ),
    (
        "Cybersecurity",
        (
            "cyber",
            "cybersecurity",
            "penetration testing",
            "fraud detection",
            "fraud prevention",
            "threat",
            "security labs",
            "security training",
            "data security",
            "cyber protection",
            "digital identity",
            "privacy tech",
        ),
    ),
    (
        "AI & Machine Learning",
        (
            "machine learning",
            "generative ai",
            "conversational ai",
            "chatbot",
            "document intelligence",
            " & ai",
            " ai ",
            "artificial intelligence",
            "location intelligence",
            "voice technology",
        ),
    ),
    (
        "Data & Analytics",
        (
            "data analytics",
            "big data",
            "business intelligence",
            "data streaming",
            "data annotation",
            "data infrastructure",
            "forecasting",
            "real-time data",
            "customer intelligence",
            "intelligence insights",
            "retail analytics",
            "market research",
            "real-world data",
        ),
    ),
    (
        "Marketing & AdTech",
        (
            "adtech",
            "advertising",
            "digital marketing",
            "mobile marketing",
            "marketing automation",
            "marketing tech",
            "customer data platform",
            "digital signage",
            "media intelligence",
            "periodical publishing",
            "outbound sales",
            "gtm strategy",
            "search engine",
            "music tech",
            "video technology",
            "rights management",
            "media",
        ),
    ),
    (
        "HR & Education Tech",
        (
            "human resources",
            "hr tech",
            "talent management",
            "recruitment software",
            "employment solutions",
            "e-learning",
            "elearning",
            "learning",
            "church management software",
        ),
    ),
    (
        "Cloud & Infrastructure",
        (
            "cloud",
            "devops",
            "hosting",
            "edge computing",
            "networking",
            "network infrastructure",
            "5g",
            "telecom",
            "wireless",
        ),
    ),
    (
        "E-commerce & Retail",
        (
            "e-commerce",
            "ecommerce",
            "retail",
            "retailtech",
            "retail tech",
            "marketplace",
            "price comparison",
            "booking platform",
            "online travel agency",
        ),
    ),
    (
        "Travel, Mobility & Logistics",
        (
            "travel",
            "aviation",
            "airline",
            "airline software",
            "mobility",
            "ride hailing",
            "logistics",
            "supply chain",
            "shipping",
            "maritime",
            "transportation",
            "delivery",
            "travel tech",
            "traveltech",
            "travel arrangements",
            "tourism",
            "vesselbot",
            "automotive",
            "automotive technology",
            "ev charging",
            "car as a service",
            "used car",
        ),
    ),
    (
        "Industrial & Manufacturing",
        (
            "industrial automation",
            "industrial machinery",
            "industry 4.0",
            "construction tech",
            "metal ore mining",
            "manufacturing",
            "engineering services",
            "digital business automation",
            "robotics",
        ),
    ),
    (
        "Energy & Resources",
        (
            "renewable",
            "cleantech",
            "solar",
            "wind power",
            "oil",
            "gas",
            "mining",
        ),
    ),
    (
        "Hardware, IoT & Embedded",
        (
            "hardware",
            "embedded",
            "firmware",
            "semiconductor",
            "electronics",
            "iot",
            "advance optronics",
            "sensory",
            "smart systems",
        ),
    ),
    (
        "Software & SaaS",
        (
            "software development",
            "saas",
            "business software",
            "digital platform",
            "web development",
            "mobile apps",
            "digital experience",
            "digital libraries",
            "digital transformation",
            "erp",
            "cms",
            "accessibility tech",
            "inclusion tech",
        ),
    ),
    (
        "IT Services & Consulting",
        (
            "it consulting",
            "it services",
            "managed services",
            "systems integration",
            "ict ",
            "outsourcing",
            "freelance platforms",
            "technology, information and internet",
            "information and internet",
            "information services",
            "information technology",
            "internet platform",
            "internet services",
            "technology investments",
            "office administration",
            "certification",
        ),
    ),
    (
        "Consumer & Hospitality",
        (
            "beverages",
            "coffee industry",
            "fmcg",
            "tobacco",
            "home services",
            "leisure",
            "hospitality",
            "food",
        ),
    ),
    (
        "Professional & Business Services",
        (
            "business consulting",
            "legal tech",
            "accounting",
            "tax",
            "assurance",
            "leasing",
            "photography",
            "printing services",
            "proptech",
            "real estate",
        ),
    ),
)


def sector_to_industry(sector: str) -> str:
    """Return a single canonical industry for one sector string."""
    if not sector or not str(sector).strip():
        return "Other"
    s = " ".join(str(sector).split()).strip().lower()
    if s in _EXACT:
        return _EXACT[s]
    for industry, needles in _SUBSTRING_RULES:
        for needle in needles:
            if needle in s:
                return industry
    return "Other"


def industries_for_sectors(sectors: list[str]) -> list[str]:
    """Deduped sorted industries for a company’s sector list."""
    seen: set[str] = set()
    out: list[str] = []
    for sec in sectors:
        ind = sector_to_industry(sec)
        if ind not in seen:
            seen.add(ind)
            out.append(ind)
    out.sort(key=lambda x: (_INDUSTRY_RANK.get(x, 999), x.casefold()))
    return out


def sort_industries_for_filter(labels: set[str]) -> list[str]:
    """Stable order for dropdown: INDUSTRIES_ORDERED, omit empty; ``Other`` only if present."""
    ordered = [x for x in INDUSTRIES_ORDERED if x in labels]
    return ordered
