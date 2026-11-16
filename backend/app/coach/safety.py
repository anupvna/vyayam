"""Safety screens around the AI coach. Pure functions, unit-tested.

screen(message): some topics must never depend on a language model. Medical red
flags, crisis, disordered eating, drugs, and requests for a diagnosis get a fixed,
careful answer, and the message is not sent to any AI provider.

check_reply(text): a last check on what a model wrote, for things it must never say
(drug dosing, starvation-level calories, fasting for days).
"""

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["red_flag", "crisis", "eating", "drugs", "medical", "health"]


@dataclass(frozen=True)
class SafetyReply:
    category: Category
    text: str


def _any(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


# Ordered by urgency: the first match wins.
_CRISIS = _any(
    r"\b(kill|hurt|harm)\s+myself\b",
    r"\bsuicid",
    r"\bend\s+(my|it)\s+(life|all)\b",
    r"\bwant\s+to\s+die\b",
    r"\bself[-\s]?harm",
    r"\bno\s+reason\s+to\s+live\b",
)
_RED_FLAG = _any(
    r"\bchest\s+(pain|pressure|tight)",
    r"\b(pain|pressure|tightness)\s+in\s+my\s+chest\b",
    r"\bfaint(ed|ing)?\b",
    r"\bpass(ed)?\s+out\b",
    r"\bblack(ed)?\s+out\b",
    r"\b(can'?t|cannot|couldn'?t|hard\s+to|struggling\s+to)\s+(breathe|catch\s+my\s+breath)\b",
    r"\bshort(ness)?\s+of\s+breath\b",
    r"\bheart\s+(is\s+)?(racing|pounding|skipping)\b",
    r"\b(numb|numbness|tingling)\b",
    r"\bdizz(y|iness)\b",
    r"\b(heard|felt)\s+a\s+(pop|snap)\b",
    r"\bsharp\s+pain\b",
    r"\bsevere\s+pain\b",
    r"\bswollen\b",
)
_EATING = _any(
    r"\bpurg(e|ing)\b",
    r"\bthrow(ing)?\s+up\s+after\s+(eating|meals?)\b",
    r"\bmake\s+myself\s+(throw\s+up|sick|vomit)\b",
    r"\blaxatives?\b",
    r"\bstarv(e|ing)\s+myself\b",
    r"\bnot\s+eat(ing)?\s+for\s+\d+\s+days\b",
    r"\b([1-9]\d{0,2})\s*(k?cal|calories)\s+(a|per)\s+day\b",
    r"\beat\s+(only\s+)?([1-9]\d{0,2})\s*(k?cal|calories)\b",
    r"\bbinge\b",
    r"\bhate\s+my\s+body\b",
)
_DRUGS = _any(
    r"\bsteroids?\b",
    r"\banabolic",
    r"\bsarms?\b",
    r"\btestosterone\b",
    r"\btrt\b",
    r"\btren(bolone)?\b",
    r"\bclen(buterol)?\b",
    r"\b(hgh|growth\s+hormone)\b",
    r"\bdianabol\b",
    r"\bozempic|semaglutide|tirzepatide|mounjaro\b",
    r"\bcycle\b.*\b(dose|dosage|mg|weeks?)\b",
    r"\bpeds?\b",
)
_MEDICAL = _any(
    r"\b(is|could)\s+(it|this|my\s+\w+(\s+\w+)?)\s+(be\s+)?(torn|broken|fractured|herniated|a\s+tear|a\s+fracture|a\s+hernia)\b",
    r"\bdiagnos",
    r"\b(torn|tore)\s+(my\s+)?(acl|mcl|meniscus|rotator|ligament|tendon|muscle)\b",
    r"\bherniat",
    r"\bfracture",
    r"\bconcussion\b",
)
_HEALTH = _any(
    r"\bpregnan",
    r"\b(diabet|heart\s+condition|blood\s+pressure|hypertension|asthma|epilep)\w*\b",
    r"\b(medication|meds|prescri\w+|painkillers?|ibuprofen|insulin)\b",
    r"\bsurgery\b",
)

RED_FLAG_TEXT = (
    "Please stop training now. Chest pain or pressure, fainting, trouble breathing, a "
    "racing heart, dizziness, numbness, or a sudden sharp pain can be signs of something "
    "serious. If any of these are happening now or are severe, call emergency services "
    "(911 in the US). Otherwise, see a doctor before your next workout. When you're "
    "cleared, tell me and I'll ease you back in."
)
CRISIS_TEXT = (
    "I'm really sorry you're going through this, and I'm glad you said something. "
    "You don't have to handle it alone. In the US, you can call or text 988 (Suicide & "
    "Crisis Lifeline) any time. Elsewhere, findahelpline.com lists free local lines. "
    "If you're in danger right now, call emergency services. Talking to someone you "
    "trust today can help too. Training can wait."
)
EATING_TEXT = (
    "Thank you for telling me. What you describe can harm your health, and you deserve "
    "real support with it. I won't give calorie or weight-loss targets here. Please "
    "talk to a doctor, or in the US contact the National Alliance for Eating Disorders "
    "helpline at 866-662-1235. I'm happy to keep your training gentle and focused on "
    "feeling strong in the meantime."
)
DRUGS_TEXT = (
    "I can't help with steroids, SARMs, hormones or weight-loss drugs: they carry real "
    "health risks and need a doctor's care. What I can do is help you get the most from "
    "training, sleep and food, which is where most progress comes from. Want me to "
    "look at your plan?"
)
MEDICAL_TEXT = (
    "I can't diagnose injuries or give medical advice. A doctor or physiotherapist can "
    "examine it properly. Until then, avoid movements that hurt. In today's check-in, "
    "mark the area under pain and I'll keep exercises that load it out of your plan."
)

HEALTH_TEXT = (
    "With a health condition, medication, pregnancy or recent surgery, please check with "
    "your doctor before changing your training. Once you're cleared, tell me any limits "
    "they gave you and I'll work within them."
)

_SCREENS: tuple[tuple[re.Pattern[str], Category, str], ...] = (
    (_CRISIS, "crisis", CRISIS_TEXT),
    (_RED_FLAG, "red_flag", RED_FLAG_TEXT),
    (_EATING, "eating", EATING_TEXT),
    (_DRUGS, "drugs", DRUGS_TEXT),
    (_MEDICAL, "medical", MEDICAL_TEXT),
    (_HEALTH, "health", HEALTH_TEXT),
)

# "No chest pain", "never fainted": a negated mention isn't a symptom report.
_NEGATED = re.compile(r"\b(no|not|never|without|don'?t\s+have|didn'?t)\s+(\w+\s+){0,2}$", re.I)


def _negated(message: str, match: re.Match[str]) -> bool:
    return bool(_NEGATED.search(message[: match.start()][-40:]))


def screen(message: str) -> SafetyReply | None:
    for pattern, category, text in _SCREENS:
        for m in pattern.finditer(message):
            if category in ("red_flag", "medical", "health") and _negated(message, m):
                continue
            return SafetyReply(category, text)
    return None


# ---------------------------------------------------------------- model output

_BAD_REPLY = _any(
    r"\b\d+\s*(mg|mcg|iu|ml)\b.*\b(steroid|testosterone|tren|sarm|clen|hgh|dianabol|anavar)",
    r"\b(steroid|testosterone|tren|sarm|clen|hgh|dianabol|anavar)\w*\b.*\b\d+\s*(mg|mcg|iu|ml)\b",
    r"\b([1-9]\d{0,2}|1[01]\d\d)\s*(k?cal|calories)\s*(a|per)\s*day\b",
    r"\bfast(ing)?\s+for\s+([2-9]|\d{2,})\s+days\b",
    r"\bno\s+pain,?\s+no\s+gain\b",
    r"\b(push|train|work)\s+through\s+(the\s+)?(sharp\s+)?pain\b",
)


def check_reply(text: str) -> str | None:
    """None if fine; otherwise the reason the reply must not be shown."""
    m = _BAD_REPLY.search(text)
    return f"unsafe content: {m.group(0)!r}" if m else None
