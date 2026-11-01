# ruff: noqa: E501 - translated wording reads better on one line
"""Language handling for the assistant: English, Telugu and Hindi.

detect() reads the script of the text. understand() maps a Telugu or Hindi question to one of a small set
of English questions the existing router already handles, so routing, tools and permissions stay in one
place. This is keyword matching, not translation: anything it doesn't recognize goes to guided help
instead of a guess, and free text from the question never reaches the pipeline. Claim numbers and file
names are carried over unchanged."""

from __future__ import annotations

import re

SUPPORTED = ("en", "te", "hi")
GENERAL_HELP = "help"
_CLAIM = re.compile(r"\bSYN-CLM-\d{4}-\d{6}\b", re.I)
_FILE = re.compile(r"[\w.-]+\.(?:pdf|png|jpe?g)\b", re.I)


def detect(text: str) -> str | None:
    """"te" or "hi" when that script is used; None for Latin text, which could be any language."""
    telugu = sum("ఀ" <= ch <= "౿" for ch in text)
    hindi = sum("ऀ" <= ch <= "ॿ" for ch in text)
    if not telugu and not hindi:
        return None
    return "te" if telugu >= hindi else "hi"


def resolve(selected: str | None, text: str) -> str:
    """A question typed in Telugu or Hindi is answered in that language; otherwise the selection applies."""
    return detect(text) or selected or "en"


_MRI = r"(ఎంఆర్ఐ|ఎమ్ఆర్ఐ|एमआरआई|mri)"
_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.I), question)
    for pattern, question in (
        (r"మందు|మాత్ర|డోస్|दवा|दवाई|गोली|खुराक", "What medicine should I take?"),
        (r"ప్రతినిధి|మనిషి|వ్యక్తితో|ఏజెంట్|సిబ్బంది|प्रतिनिधि|इंसान|एजेंट|किसी व्यक्ति|सपोर्ट टीम", "I want to talk to a person"),
        (r"సపోర్ట్ రిక్వెస్ట్|ఫిర్యాదు|టికెట్|सपोर्ट रिक्वेस्ट|शिकायत|टिकट", "Please create a support case"),
        (r"అర్థం కాలేదు|అర్థం కావడం లేదు|అర్ధం కాలేదు|సులభంగా|सरल|समझ नहीं|समझा नहीं", "I don't understand"),
        (r"(అప్‌లోడ్|అప్లోడ్|अपलोड).*(సిద్ధ|ఏమి లేదు|रेडी|तैयार|कमी)", "Is my uploaded document ready for prior authorization?"),
        (r"అప్‌లోడ్|అప్లోడ్|अपलोड", "Summarize my latest uploaded document"),
        (r"క్లెయిమ్|క్లైమ్|దావా|क्लेम|दावा|दावे", "Show my claims"),
        (rf"{_MRI}.*(డాక్యుమెంట్|పత్రా|दस्तावेज|दस्तावेज़|कागज)|(డాక్యుమెంట్|పత్రా|दस्तावेज|दस्तावेज़|कागज).*{_MRI}",
         "What documents are required for a lumbar MRI prior authorization?"),
        (r"గుండె|हृदय|दिल|हार्ट|హార్ట్", "What documents are required for heart bypass prior authorization?"),
        (r"ఫిజియోథెరపీ|ఫిజికల్ థెరపీ|फिजियोथेरेपी|फिजिकल थेरेपी", "How many physical therapy visits does my plan cover?"),
        (r"ఆథరైజేషన్|ముందస్తు అనుమతి|అనుమతి|ऑथराइजेशन|प्राधिकरण|पूर्व अनुमति|अनुमति", "How does prior authorization work?"),
        (r"డాక్యుమెంట్|పత్రాలు|దస్తావేజు|दस्तावेज|दस्तावेज़|कागज", "Which documents do I need?"),
        (r"ప్రయోజన|కవరేజ్|కవర్|ప్లాన్|బీమా|ఇన్సూరెన్స్|ఎంత చెల్లించ|लाभ|कवरेज|कवर|प्लान|योजना|बीमा|इंश्योरेंस|कितना देना",
         "Show my plan benefits"),
    )
)


def understand(text: str, language: str) -> str:
    """The English question to route. English text passes through unchanged."""
    if language == "en" or detect(text) is None:
        return text
    if (claim := _CLAIM.search(text)) is not None:
        return f"What is the status of my claim {claim.group(0).upper()}?"
    for pattern, question in _RULES:
        if pattern.search(text):
            if question.startswith("Summarize") and (file := _FILE.search(text)):
                return f"Summarize {file.group(0)}"
            return question
    return GENERAL_HELP
