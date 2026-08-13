"""Domain vocabulary used to turn free text into structured intent.

This file is deliberately data, not logic. Everything the parser can recognise
lives here in one place, so adding a new skill or domain is a one-line change
and the matcher's vocabulary is auditable at a glance.

Each entry maps a canonical label to the surface forms a human might type.
"""

# --------------------------------------------------------------------------- #
# Skills
# --------------------------------------------------------------------------- #
# canonical name -> alternative spellings people actually type
SKILL_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "py", "python3"],
    "FastAPI": ["fastapi", "fast api"],
    "Django": ["django", "drf", "django rest framework"],
    "Flask": ["flask"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "React": ["react", "reactjs", "react.js"],
    "Next.js": ["next.js", "nextjs", "next js"],
    "Node.js": ["node.js", "nodejs", "node", "node js"],
    "Angular": ["angular", "angularjs"],
    "Vue": ["vue", "vuejs", "vue.js"],
    "Java": ["java", "core java"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "Go": ["golang", "go lang"],
    "C#": ["c#", "csharp", "c sharp"],
    ".NET": [".net", "dotnet", "dot net"],
    "PHP": ["php", "laravel"],
    "Ruby": ["ruby", "rails", "ruby on rails"],
    "SQL": ["sql", "t-sql", "pl/sql"],
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql", "mariadb"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "elastic search", "opensearch"],
    "REST APIs": ["rest", "rest api", "rest apis", "restful", "restful api"],
    "GraphQL": ["graphql", "graph ql"],
    "gRPC": ["grpc"],
    "Microservices": ["microservices", "micro services", "microservice"],
    "Docker": ["docker", "containers", "containerisation", "containerization"],
    "Kubernetes": ["kubernetes", "k8s", "eks", "aks", "gke"],
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "CI/CD": ["ci/cd", "cicd", "ci cd", "continuous integration", "jenkins", "github actions"],
    "Terraform": ["terraform", "iac", "infrastructure as code"],
    "Linux": ["linux", "unix", "bash", "shell scripting"],
    "Git": ["git", "github", "gitlab", "version control"],
    "Machine Learning": ["machine learning", "ml", "deep learning", "neural networks"],
    "NLP": ["nlp", "natural language processing", "text mining"],
    "Computer Vision": ["computer vision", "cv", "image processing", "opencv"],
    "LLMs": ["llm", "llms", "large language model", "large language models", "genai", "generative ai", "prompt engineering", "rag"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "keras"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "Pandas": ["pandas", "numpy", "dataframe"],
    "Data Engineering": ["data engineering", "etl", "elt", "data pipeline", "data pipelines", "airflow", "spark", "pyspark"],
    "Data Analysis": ["data analysis", "data analytics", "analytics", "bi", "business intelligence"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["excel", "advanced excel", "spreadsheets"],
    "Testing": ["testing", "unit testing", "pytest", "jest", "qa", "test automation", "selenium"],
    "Security": ["security", "cybersecurity", "appsec", "infosec", "penetration testing"],
    "Android": ["android", "kotlin"],
    "iOS": ["ios", "swift", "swiftui"],
    "React Native": ["react native", "react-native"],
    "Flutter": ["flutter", "dart"],
    "UI/UX": ["ui/ux", "ui ux", "figma", "user experience", "user interface", "product design"],
    "HTML/CSS": ["html", "css", "sass", "scss", "tailwind", "bootstrap"],
    "Agile": ["agile", "scrum", "kanban", "sprint planning"],
    "Product Management": ["product management", "product owner", "roadmap"],
    "Communication": ["communication", "stakeholder management", "presentation"],
    "Leadership": ["leadership", "mentoring", "team lead", "people management"],
}

# --------------------------------------------------------------------------- #
# Business domains
# --------------------------------------------------------------------------- #
DOMAIN_ALIASES: dict[str, list[str]] = {
    "Healthcare": ["healthcare", "health care", "health-tech", "healthtech", "health tech", "medical", "medtech", "clinical", "hospital", "patient", "pharma", "pharmaceutical", "life sciences", "ehr", "emr", "hipaa", "telemedicine", "diagnostics"],
    "Fintech": ["fintech", "fin-tech", "finance", "financial", "banking", "bank", "payments", "payment", "lending", "insurance", "insurtech", "trading", "wealth management", "capital markets"],
    "E-commerce": ["e-commerce", "ecommerce", "e commerce", "retail", "marketplace", "d2c", "online shopping", "storefront"],
    "EdTech": ["edtech", "ed-tech", "education", "e-learning", "elearning", "learning platform", "lms"],
    "Logistics": ["logistics", "supply chain", "shipping", "freight", "warehousing", "fleet", "last mile"],
    "SaaS": ["saas", "b2b saas", "software as a service", "enterprise software", "platform"],
    "Gaming": ["gaming", "games", "game development", "game dev"],
    "Media": ["media", "streaming", "entertainment", "publishing", "content platform", "ott"],
    "Travel": ["travel", "hospitality", "tourism", "booking", "airline", "hotel"],
    "Real Estate": ["real estate", "proptech", "property"],
    "Cybersecurity": ["cybersecurity", "cyber security", "security product", "threat intelligence"],
    "Telecom": ["telecom", "telecommunications", "5g", "networking hardware"],
    "Manufacturing": ["manufacturing", "industrial", "iot", "automotive", "factory"],
    "Energy": ["energy", "cleantech", "clean tech", "renewables", "solar", "sustainability", "climate"],
    "Government": ["government", "public sector", "govtech", "civic"],
    "HR Tech": ["hr tech", "hrtech", "recruiting", "recruitment", "talent", "hiring platform", "ats"],
    "AI Research": ["ai research", "research lab", "foundation model", "frontier ai"],
}

# --------------------------------------------------------------------------- #
# Role types
# --------------------------------------------------------------------------- #
ROLE_TYPE_ALIASES: dict[str, list[str]] = {
    "Backend": ["backend", "back-end", "back end", "server side", "server-side", "api developer"],
    "Frontend": ["frontend", "front-end", "front end", "ui developer", "web developer"],
    "Full Stack": ["full stack", "fullstack", "full-stack"],
    "Data Science": ["data science", "data scientist", "ml engineer", "machine learning engineer", "ai engineer", "research engineer"],
    "Data Engineering": ["data engineer", "data engineering", "analytics engineer"],
    "Data Analysis": ["data analyst", "business analyst", "bi analyst", "reporting analyst"],
    "DevOps": ["devops", "sre", "site reliability", "platform engineer", "infrastructure engineer", "cloud engineer"],
    "Mobile": ["mobile", "mobile developer", "app developer", "android developer", "ios developer"],
    "QA": ["qa", "quality assurance", "test engineer", "sdet", "automation engineer"],
    "Security": ["security engineer", "security analyst", "soc analyst"],
    "Product": ["product manager", "product owner", "program manager"],
    "Design": ["designer", "ux designer", "ui designer", "product designer"],
    "Management": ["engineering manager", "tech lead", "team lead", "architect"],
}

# --------------------------------------------------------------------------- #
# Locations (Indian metros + common remote phrasing)
# --------------------------------------------------------------------------- #
LOCATION_ALIASES: dict[str, list[str]] = {
    "Hyderabad": ["hyderabad", "hyd", "secunderabad", "telangana"],
    "Bengaluru": ["bengaluru", "bangalore", "blr", "karnataka"],
    "Chennai": ["chennai", "madras", "tamil nadu"],
    "Pune": ["pune"],
    "Mumbai": ["mumbai", "bombay", "navi mumbai"],
    "Delhi NCR": ["delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida"],
    "Kolkata": ["kolkata", "calcutta"],
    "Ahmedabad": ["ahmedabad", "gujarat"],
    "Kochi": ["kochi", "cochin", "kerala"],
    "Remote": ["remote", "anywhere", "work from home", "wfh", "distributed"],
}

# --------------------------------------------------------------------------- #
# Work mode / company stage / experience level
# --------------------------------------------------------------------------- #
WORK_MODE_ALIASES: dict[str, list[str]] = {
    "remote": ["remote", "work from home", "wfh", "fully remote", "anywhere"],
    "hybrid": ["hybrid", "partly remote", "flexible office", "2 days in office", "3 days in office"],
    "onsite": ["onsite", "on-site", "on site", "in office", "in-office", "office based"],
}

COMPANY_STAGE_ALIASES: dict[str, list[str]] = {
    "startup": ["startup", "start-up", "start up", "early stage", "early-stage", "seed stage", "series a", "small team", "founding team", "scrappy"],
    "midsize": ["mid-size", "midsize", "mid size", "scale-up", "scaleup", "growth stage", "series c", "mid-sized"],
    "enterprise": ["enterprise", "large company", "mnc", "multinational", "fortune 500", "big company", "corporate"],
}

EXPERIENCE_LEVEL_ALIASES: dict[str, list[str]] = {
    "entry": ["entry level", "entry-level", "fresher", "freshers", "graduate", "junior", "no experience", "beginner", "trainee", "intern"],
    "mid": ["mid level", "mid-level", "intermediate", "mid senior", "2-4 years", "3 years", "few years"],
    "senior": ["senior", "sr.", "sr ", "experienced", "5+ years", "5 years", "6 years", "7 years"],
    "lead": ["lead", "principal", "staff engineer", "architect", "head of", "manager", "director", "8+ years", "10+ years"],
}

# Typical years-of-experience band for each level. Used to score how well a
# candidate's actual experience lines up with what a job asks for.
EXPERIENCE_BANDS: dict[str, tuple[float, float]] = {
    "entry": (0.0, 2.0),
    "mid": (2.0, 5.0),
    "senior": (5.0, 9.0),
    "lead": (8.0, 30.0),
}

# Ordering used to measure "how far apart" two levels are.
EXPERIENCE_ORDER: list[str] = ["entry", "mid", "senior", "lead"]


def build_lookup(aliases: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Flatten an alias map into (surface_form, canonical) pairs.

    Sorted longest-first so that multi-word forms win over their own substrings
    - e.g. "react native" is matched before "react".
    """
    pairs: list[tuple[str, str]] = []
    for canonical, forms in aliases.items():
        pairs.append((canonical.lower(), canonical))
        for form in forms:
            pairs.append((form.lower(), canonical))
    pairs.sort(key=lambda pair: len(pair[0]), reverse=True)
    return pairs


SKILL_LOOKUP = build_lookup(SKILL_ALIASES)
DOMAIN_LOOKUP = build_lookup(DOMAIN_ALIASES)
ROLE_TYPE_LOOKUP = build_lookup(ROLE_TYPE_ALIASES)
LOCATION_LOOKUP = build_lookup(LOCATION_ALIASES)
WORK_MODE_LOOKUP = build_lookup(WORK_MODE_ALIASES)
COMPANY_STAGE_LOOKUP = build_lookup(COMPANY_STAGE_ALIASES)
EXPERIENCE_LEVEL_LOOKUP = build_lookup(EXPERIENCE_LEVEL_ALIASES)
