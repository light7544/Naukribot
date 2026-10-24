"""Shared project configuration, strict GenAI title filters, and Smart Chatbot Auto-Answer Engine."""

from __future__ import annotations

import os
import re
from pathlib import Path


def project_dir(script_file: str | Path) -> Path:
    return Path(script_file).resolve().parent


def load_project_env(script_file: str | Path) -> Path:
    env_path = project_dir(script_file) / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        if not env_path.is_file():
            return env_path
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            else:
                value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
            os.environ.setdefault(key, value)
    else:
        load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def is_keep_browser_open() -> bool:
    val = os.getenv("KEEP_BROWSER_OPEN", "").strip().lower()
    return val in ("true", "1", "yes")


# Strict AI / GenAI / LLM / ML Whitelist (No standalone 'architect' or 'foundry' to avoid Azure Cloud Architect / Palantir)
TITLE_WHITELIST = [
    "artificial intelligence",
    "artificial-intelligence",
    "artificial intelligence engineer",
    "artificial intelligence developer",
    "artificial intelligence architect",
    "artificial intelligence specialist",
    "artificial intelligence consultant",
    "artificial intelligence scientist",
    "artificial intelligence researcher",
    "artificial intelligence lead",
    "ai",
    "ai engineer",
    "ai developer",
    "ai architect",
    "ai solution architect",
    "ai solutions architect",
    "ai specialist",
    "ai consultant",
    "ai scientist",
    "ai researcher",
    "ai lead",
    "genai",
    "gen ai",
    "gen-ai",
    "generative ai",
    "generative artificial intelligence",
    "generative",
    "genai engineer",
    "genai developer",
    "genai architect",
    "agentic",
    "agentic ai",
    "ai agent",
    "ai agents",
    "multi-agent",
    "multi agent",
    "multiagent",
    "autonomous agent",
    "autonomous agents",
    "langgraph",
    "crewai",
    "autogen",
    "llm",
    "llms",
    "large language model",
    "large language models",
    "rag",
    "retrieval augmented generation",
    "retrieval-augmented generation",
    "prompt engineer",
    "prompt engineering",
    "llmops",
    "mlops",
    "langchain",
    "llamaindex",
    "llama index",
    "openai",
    "conversational ai",
    "chatbot developer",
    "ml",
    "machine learning",
    "machine learning engineer",
    "deep learning",
    "deep learning engineer",
    "nlp",
    "nlp engineer",
    "natural language processing",
    "data scientist",
    "applied scientist",
    "azure ai",
    "azure ai foundry",
    "ai foundry",
    "aws bedrock",
    "bedrock",
    "vertex",
    "vertex ai",
    "gemini",
    "copilot",
]

TITLE_BLACKLIST = [
    "devops",
    "aws devops",
    "azure devops",
    "cloud architect",
    "azure cloud architect",
    "aws cloud architect",
    "sre",
    "site reliability",
    "cloud infrastructure engineer",
    "cloud admin",
    "release engineer",
    "system admin",
    "palantir",
]

PRIORITY_GENAI_TERMS = [
    "genai", "gen ai", "gen-ai", "generative ai", "llm", "llms", "rag",
    "agentic", "langchain", "llamaindex", "bedrock", "vertex ai", "azure ai foundry"
]


def compile_term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.casefold().strip())
    pattern = re.sub(r"(\\\s+|\\\-|\\/|\\_)+", lambda _: r"[\s\-_/]+", escaped)
    return re.compile(rf"(?<![a-zA-Z0-9]){pattern}(?![a-zA-Z0-9])", re.IGNORECASE)


COMPILED_WHITELIST = {
    term: compile_term_pattern(term)
    for term in sorted(TITLE_WHITELIST, key=len, reverse=True)
}
COMPILED_BLACKLIST = {
    term: compile_term_pattern(term)
    for term in sorted(TITLE_BLACKLIST, key=len, reverse=True)
}
COMPILED_PRIORITY_GENAI = {
    term: compile_term_pattern(term)
    for term in sorted(PRIORITY_GENAI_TERMS, key=len, reverse=True)
}


def is_job_title_allowed(title_text: str) -> tuple[bool, str]:
    if not title_text or not title_text.strip():
        return False, "Empty job title"

    # 1. Blacklist check first for non-GenAI roles (like Palantir or pure Cloud Architect)
    for b_kw, pat in COMPILED_BLACKLIST.items():
        if pat.search(title_text):
            # Only allow if it explicitly has a priority GenAI term (and isn't Palantir)
            if "palantir" not in b_kw:
                for p_kw, p_pat in COMPILED_PRIORITY_GENAI.items():
                    if p_pat.search(title_text):
                        return True, f"Matched Priority GenAI keyword '{p_kw}'"
            return False, f"Matched blacklist keyword '{b_kw}'"

    # 2. Whitelist Check
    for w_kw, pat in COMPILED_WHITELIST.items():
        if pat.search(title_text):
            return True, f"Matched GenAI/AI whitelist keyword '{w_kw}'"

    return False, "Does not match any GenAI/AI whitelist keyword"


# ==============================================================================
# SMART CHATBOT AUTO-RESPONDER ENGINE (100% Hands-Free Profile Rules)
# ==============================================================================
USER_PROFILE_DEFAULTS = {
    "total_exp_years": os.getenv("TOTAL_EXP_YEARS", "3"),
    "genai_exp_years": os.getenv("GENAI_EXP_YEARS", "3"),
    "tenth_percent": os.getenv("TENTH_PERCENT", "92"),
    "twelfth_percent": os.getenv("TWELFTH_PERCENT", "80"),
    "grad_cgpa": os.getenv("GRAD_CGPA", "8"),
    "notice_period_days": os.getenv("NOTICE_PERIOD_DAYS", "30"),
    "education_gap_years": os.getenv("EDUCATION_GAP_YEARS", "1"),
    "current_ctc_lpa": os.getenv("CURRENT_CTC_LPA", "4.13"),
    "current_ctc_inr": os.getenv("CURRENT_CTC_INR", "413120"),
    "expected_ctc_lpa": os.getenv("EXPECTED_CTC_LPA", "12"),
    "expected_ctc_inr": os.getenv("EXPECTED_CTC_INR", "1200000"),
    "current_location": os.getenv("CURRENT_LOCATION", "Pune"),
    "preferred_location": os.getenv("PREFERRED_LOCATION", "Bangalore"),
    "current_company": os.getenv("CURRENT_COMPANY", "Tata Consultancy Services"),
}


def smart_infer_text_answer(question_text: str) -> str:
    """
    Automatically determines the exact answer for ANY Naukri chatbot free-text question.
    NEVER answers 'no' to a 'How many years of experience...' question (Naukri expects a number!).
    """
    q = (question_text or "").strip().lower()
    p = USER_PROFILE_DEFAULTS

    # 0. Employment Type (Permanent / Contractual / Third party payroll)
    if any(k in q for k in ("permanent", "contractual", "third party", "payroll", "employment type")):
        return "Permanent"

    # 1. Experience questions ("How many years...", "What is your experience...") -> ALWAYS return a number!
    if any(k in q for k in (
        "how many years", "years of experience", "experience do you have",
        "experience you have", "relevant experience", "relevant years", "total experience", "work experience"
    )):
        # Core AI / GenAI / ML / Cloud / DevOps / Python skills -> 3 years
        core_skills = (
            "ai", "artificial intelligence", "genai", "gen ai", "generative", "agentic",
            "llm", "rag", "langchain", "llamaindex", "machine learning", "ml", "deep learning",
            "nlp", "natural language", "python", "aws", "azure", "gcp", "vertex", "bedrock",
            "foundry", "fastapi", "docker", "kubernetes", "devops", "cloud", "prompt",
            "vector", "milvus", "openai", "gemini", "work", "total", "it", "relevant"
        )
        if any(skill in q for skill in core_skills):
            return p["total_exp_years"]  # "3"
        # Secondary adjacent tech (Databricks, Computer Vision, Data Engineering, SQL, etc.) -> "2" (never "no"!)
        secondary_skills = ("data", "databricks", "data bricks", "computer vision", "spark", "sql", "java", "react")
        if any(skill in q for skill in secondary_skills):
            return "2"
        # Niche / unrelated tools -> "1" (numeric, so recruiter filter doesn't auto-reject)
        return "1"

    # 2. 10th / SSLC / Matriculation Percentage
    if any(k in q for k in ("10th", "sslc", "matric", "class 10", "class x", "ssc")):
        return p["tenth_percent"]

    # 3. 12th / HSC / Diploma Percentage
    if any(k in q for k in ("12th", "hsc", "diploma", "intermediate", "class 12", "class xii", "puc")):
        return p["twelfth_percent"]

    # 4. Graduation / B.Tech / B.E / Highest Qualification CGPA
    if any(k in q for k in ("graduation", "b.tech", "b.e", "degree", "highest educational", "cgpa", "percentage", "qualification")):
        return p["grad_cgpa"]

    # 5. Education Gap / Career Gap
    if "gap" in q:
        return p["education_gap_years"]

    # 6. Notice Period / LWD / Joining Time
    if any(k in q for k in ("notice period", "notice", "lwd", "last working day", "how soon can you join", "joining time", "days to join")):
        return p["notice_period_days"]

    # 7. Holding any Offer / Offered CTC
    if "holding any offer" in q or "other offer" in q or "offered ctc" in q or "offer in hand" in q:
        return "No"

    # 8. Expected CTC / Expected Salary
    if any(k in q for k in ("expected ctc", "expected salary", "ectc", "expected annual", "salary expectation")):
        return p["expected_ctc_lpa"]

    # 9. Current CTC / Current Salary / Fixed Salary
    if any(k in q for k in ("current ctc", "current salary", "cctc", "present ctc", "present salary", "fixed salary", "annual salary")):
        return p["current_ctc_lpa"]

    # 10. Relocation / Residing / Hybrid / Shift
    if any(k in q for k in ("relocate", "residing", "willing to work", "comfortable working", "shift", "hybrid", "work from office", "wfo")):
        return "Yes"

    # 11. Current / Preferred Location
    if any(k in q for k in ("current location", "current city", "where are you currently located", "hometown")):
        return p["current_location"]
    if "preferred location" in q or "preferred city" in q:
        return p["preferred_location"]

    # 12. Current Company
    if any(k in q for k in ("current company", "current employer", "current organization", "working with")):
        return p["current_company"]

    # 13. Generic Yes/No question
    if q.startswith(("are you", "do you", "have you", "can you", "will you")):
        if any(neg in q for neg in ("offer", "visa sponsorship", "criminal", "bond", "backlogs")):
            return "No"
        return "Yes"

    return p["total_exp_years"]


def _option_matches_target_years(opt_text: str, target_yr: float = 3.0) -> tuple[bool, float]:
    """
    Evaluates a radio button label (e.g. '2-4', '2 - 4 years', '1 to 3', '3+', 'Less than 1')
    and returns (is_good_match, score) for a candidate with ~3 years of experience.
    """
    o = opt_text.strip().lower()
    # Explicitly reject 'less than 1', '< 1', '<1', 'fresher', '0 year', 'none', 'no'
    if any(bad in o for bad in ("less than 1", "less than one", "< 1", "<1", "fresher", "no exp", "none")):
        return False, -100.0

    # Check explicit range like "2-4", "2 - 4", "2 to 4", "1-3", "3-5"
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\-|to|–)\s*(\d+(?:\.\d+)?)", o)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        if low <= target_yr <= high:
            # Prefer ranges where 3 is well inside or lower bound is >= 2 (e.g. '2-4' or '3-5' over '1-3')
            return True, 100.0 - abs(((low + high) / 2.0) - target_yr)
        # If target_yr is close (e.g. 1-2 or 4-6)
        dist = min(abs(target_yr - low), abs(target_yr - high))
        if dist <= 1.5:
            return True, 50.0 - dist * 10

    # Check '3+', '2+', 'more than 2', 'above 2'
    plus_match = re.search(r"(?:more than|above|>|>=)?\s*(\d+(?:\.\d+)?)\s*\+?", o)
    if plus_match and ("+" in o or "more" in o or "above" in o):
        val = float(plus_match.group(1))
        if val <= target_yr:
            return True, 80.0 - (target_yr - val)

    # Check exact single number like "3", "3 years", "2 years"
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", o)]
    if len(nums) == 1:
        val = nums[0]
        if val >= 1.0:
            return True, 90.0 - abs(target_yr - val) * 15

    return False, 0.0


def smart_infer_radio_option(question_text: str, options: list[str]) -> int:
    """
    Selects the best radio option index for ANY Naukri question.
    Never selects 'Less than 1' for experience questions!
    """
    if not options:
        return 0
    q = (question_text or "").strip().lower()
    norm_opts = [o.strip().lower() for o in options]

    # 1. Experience / Years questions -> score every option against 3.0 years and NEVER pick 'Less than 1'
    if any(k in q for k in ("experience", "years", "exp", "how long", "genai", "ai tech")):
        best_idx = None
        best_score = -999.0
        for i, o in enumerate(norm_opts):
            matched, score = _option_matches_target_years(o, target_yr=3.0)
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is not None and best_score > 0:
            return best_idx
        # Fallback for experience: pick any option that doesn't say 'less than 1', 'no', or 'skip'
        for i, o in enumerate(norm_opts):
            if not any(b in o for b in ("less than", "<", "no", "skip", "none", "fresher")):
                return i

    # 2. Employment Type (Permanent / Contractual / Third party payroll)
    if any(k in q for k in ("permanent", "contractual", "third party", "payroll", "employment")):
        for i, o in enumerate(norm_opts):
            if "permanent" in o or "full time" in o or "regular" in o:
                return i

    # 3. Holding an offer / backlogs / visa sponsorship -> prefer "No"
    if any(k in q for k in ("holding any offer", "offer in hand", "backlogs", "visa sponsorship")):
        for i, o in enumerate(norm_opts):
            if o in ("no", "n", "none", "0"):
                return i

    # 3. Notice period / Joining time -> prefer 30 days / 1 month / 15-30 days / Immediate
    if any(k in q for k in ("notice", "join", "lwd", "serving")):
        for pref in ("30", "1 month", "15", "immediate", "yes", "less than 30"):
            for i, o in enumerate(norm_opts):
                if pref in o:
                    return i

    # 4. Relocation / Residing / Shifts / Willingness / General Yes-No -> prefer "Yes"
    for i, o in enumerate(norm_opts):
        if o in ("yes", "y", "true", "immediate", "pune", "bangalore", "bengaluru", "mumbai"):
            return i

    # 5. Education -> prefer B.Tech / B.E / Graduate
    if any(k in q for k in ("education", "qualification", "degree", "graduate")):
        for pref in ("b.tech", "b.e", "bachelor", "graduate", "engineering", "yes"):
            for i, o in enumerate(norm_opts):
                if pref in o:
                    return i

    # 6. Safe Fallback: pick first option that is NOT 'Less than 1', 'No', or 'Skip'
    for i, o in enumerate(norm_opts):
        if not o.startswith("no") and "skip" not in o and "less than" not in o:
            return i

    return 0
