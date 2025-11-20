"""Language Detection - Detects website language from HTML using multiple methods"""

import re
from typing import Optional, Tuple, Dict, List
from collections import Counter
from bs4 import BeautifulSoup

try:
    from langdetect import detect, detect_langs, LangDetectException

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

try:
    from py3langid import classify as langid_classify

    LANGID_AVAILABLE = True
except ImportError:
    LANGID_AVAILABLE = False


LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "hi": "Hindi",
    "tr": "Turkish",
    "pl": "Polish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sl": "Slovenian",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mt": "Maltese",
    "el": "Greek",
    "he": "Hebrew",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    "sw": "Swahili",
    "af": "Afrikaans",
    "zu": "Zulu",
    "xh": "Xhosa",
    "st": "Sesotho",
    "tn": "Tswana",
    "ts": "Tsonga",
    "ss": "Swati",
    "ve": "Venda",
    "nr": "Ndebele",
}

LANGUAGE_KEYWORDS = {
    "es": [
        "privacidad",
        "protección de datos",
        "derecho al olvido",
        "supresión de datos",
        "contacto",
    ],
    "fr": [
        "confidentialité",
        "protection des données",
        "droit à l'effacement",
        "contact",
    ],
    "de": ["datenschutz", "datenschutzerklärung", "kontakt", "impressum"],
    "it": ["privacy", "protezione dei dati", "contatto"],
    "pt": ["privacidade", "proteção de dados", "contacto"],
    "nl": ["privacy", "gegevensbescherming", "contact"],
    "ar": ["خصوصية", "حماية البيانات", "اتصال"],
    "pl": ["prywatność", "ochrona danych", "kontakt"],
    "sv": ["sekretess", "dataskydd", "kontakt"],
    "da": ["privatliv", "databeskyttelse", "kontakt"],
    "no": ["personvern", "databeskyttelse", "kontakt"],
    "fi": ["tietosuoja", "yksityisyys", "yhteystiedot"],
    "cs": ["ochrana osobních údajů", "kontakt"],
    "sk": ["ochrana osobných údajov", "kontakt"],
    "hu": ["adatvédelem", "kapcsolat"],
    "ro": ["confidențialitate", "protecția datelor", "contact"],
    "bg": ["поверителност", "защита на данните", "контакт"],
    "hr": ["privatnost", "zaštita podataka", "kontakt"],
    "sl": ["zasebnost", "varstvo podatkov", "kontakt"],
}


def detect_html_language(
    html_content: str, url: Optional[str] = None
) -> Tuple[str, str, float]:
    detection_results = []

    lang_attr = extract_lang_attribute(html_content)
    if lang_attr:
        lang_code = normalize_lang_code(lang_attr)
        detection_results.append(
            {
                "lang": lang_code,
                "confidence": 0.95,
                "method": "html_lang",
                "weight": 5.0,
            }
        )

    meta_lang = extract_meta_language(html_content)
    if meta_lang:
        lang_code = normalize_lang_code(meta_lang)
        detection_results.append(
            {"lang": lang_code, "confidence": 0.90, "method": "meta_tag", "weight": 4.0}
        )

    if url:
        url_lang = detect_language_from_url(url)
        if url_lang:
            lang_code = normalize_lang_code(url_lang)
            detection_results.append(
                {
                    "lang": lang_code,
                    "confidence": 0.75,
                    "method": "url_pattern",
                    "weight": 2.0,
                }
            )

    # Extract text content for analysis
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:
        soup = BeautifulSoup(html_content, "html.parser")

    text_content = soup.get_text(separator=" ", strip=True)

    # Method 4: langdetect library (with probabilities)
    if LANGDETECT_AVAILABLE and len(text_content) > 100:
        try:
            # Get multiple language probabilities
            langs = detect_langs(text_content[:5000])
            for lang_prob in langs[:3]:
                lang_code = normalize_lang_code(lang_prob.lang)
                confidence = float(lang_prob.prob)
                if confidence > 0.1:
                    detection_results.append(
                        {
                            "lang": lang_code,
                            "confidence": min(confidence * 0.85, 0.85),
                            "method": "langdetect",
                            "weight": 3.0,
                        }
                    )
        except Exception:
            pass

    if LANGID_AVAILABLE and len(text_content) > 100:
        try:
            detected_lang, confidence = langid_classify(text_content[:5000])
            lang_code = normalize_lang_code(detected_lang)
            normalized_conf = max(0.1, min(1.0, 1.0 + (confidence / 10000)))
            detection_results.append(
                {
                    "lang": lang_code,
                    "confidence": normalized_conf * 0.70,
                    "method": "langid",
                    "weight": 3.0,
                }
            )
        except Exception:
            pass

    keyword_lang = detect_language_from_keywords(html_content)
    if keyword_lang:
        lang_code = normalize_lang_code(keyword_lang)
        detection_results.append(
            {"lang": lang_code, "confidence": 0.50, "method": "keywords", "weight": 1.0}
        )

    if detection_results:
        final_lang, final_confidence = aggregate_detections(detection_results)
        lang_name = LANGUAGE_NAMES.get(final_lang, final_lang.upper())
        return final_lang, lang_name, final_confidence

    return "en", "English", 0.05


def extract_lang_attribute(html_content: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html_content[:2000], "lxml")
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return html_tag["lang"].lower()
    except Exception:
        pass
    return None


def extract_meta_language(html_content: str) -> Optional[str]:
    try:
        soup = BeautifulSoup(html_content[:5000], "lxml")

        # Check various meta tags
        meta_tags = soup.find_all("meta")
        for meta in meta_tags:
            content = meta.get("content", "").lower()
            if "lang" in content or content in ["en", "es", "fr", "de", "it", "pt"]:
                return content

        # Check Open Graph locale
        og_locale = soup.find("meta", property="og:locale")
        if og_locale and og_locale.get("content"):
            locale = og_locale["content"].lower()
            if "_" in locale:
                return locale.split("_")[0]

    except Exception:
        pass
    return None


def detect_language_from_url(url: str) -> Optional[str]:
    url_lower = url.lower()
    patterns = [
        (r"/es/", "es"),
        (r"/fr/", "fr"),
        (r"/de/", "de"),
        (r"/it/", "it"),
        (r"/pt/", "pt"),
        (r"/nl/", "nl"),
        (r"/ar/", "ar"),
        (r"/zh/", "zh"),
        (r"/ja/", "ja"),
        (r"/ko/", "ko"),
        (r"/ru/", "ru"),
        (r"/pl/", "pl"),
        (r"/es\.", "es"),
        (r"/fr\.", "fr"),
        (r"/de\.", "de"),
        (r"/it\.", "it"),
        (r"/pt\.", "pt"),
        (r"/nl\.", "nl"),
        (r"/ar\.", "ar"),
        (r"/zh\.", "zh"),
        (r"/ja\.", "ja"),
        (r"/ko\.", "ko"),
        (r"/ru\.", "ru"),
        (r"/pl\.", "pl"),
    ]

    for pattern, lang in patterns:
        if re.search(pattern, url_lower):
            return lang

    return None


def detect_language_from_keywords(html_content: str) -> Optional[str]:
    html_lower = html_content.lower()
    for lang_code, keywords in LANGUAGE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in html_lower:
                return lang_code

    return None


def normalize_lang_code(lang_code: str) -> str:
    """Normalize language codes to standard 2-letter format"""
    lang_code = lang_code.lower().strip()

    # Handle common variations
    mappings = {
        "english": "en",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "italian": "it",
        "portuguese": "pt",
        "dutch": "nl",
        "arabic": "ar",
        "chinese": "zh",
        "japanese": "ja",
        "korean": "ko",
        "russian": "ru",
        "hindi": "hi",
        "turkish": "tr",
        "polish": "pl",
        "swedish": "sv",
        "danish": "da",
        "norwegian": "no",
        "finnish": "fi",
        "czech": "cs",
        "slovak": "sk",
        "hungarian": "hu",
        "romanian": "ro",
        "bulgarian": "bg",
        "croatian": "hr",
        "slovenian": "sl",
        "estonian": "et",
        "latvian": "lv",
        "lithuanian": "lt",
        "maltese": "mt",
        "greek": "el",
        "hebrew": "he",
        "thai": "th",
        "vietnamese": "vi",
        "indonesian": "id",
        "malay": "ms",
        "tagalog": "tl",
    }

    # Direct mapping
    if lang_code in mappings:
        return mappings[lang_code]

    # Handle locale formats (e.g., 'en-US' -> 'en')
    if "-" in lang_code or "_" in lang_code:
        base_lang = lang_code.split("-")[0].split("_")[0]
        if base_lang in mappings:
            return mappings[base_lang]
        return base_lang

    # Return as-is if already 2-letter code
    if len(lang_code) == 2 and lang_code.isalpha():
        return lang_code

    return lang_code


def aggregate_detections(detection_results: List[Dict]) -> Tuple[str, float]:
    """
    Aggregate multiple language detection results using weighted voting

    Args:
        detection_results: List of detection dictionaries with 'lang', 'confidence', 'weight'

    Returns:
        Tuple of (language_code, final_confidence)
    """
    if not detection_results:
        return "en", 0.05

    # Count weighted votes for each language
    language_scores = {}
    total_weight = 0.0

    for result in detection_results:
        lang = result["lang"]
        confidence = result["confidence"]
        weight = result["weight"]

        # Score = confidence * weight
        score = confidence * weight

        if lang not in language_scores:
            language_scores[lang] = {
                "total_score": 0.0,
                "max_confidence": 0.0,
                "count": 0,
                "methods": [],
            }

        language_scores[lang]["total_score"] += score
        language_scores[lang]["max_confidence"] = max(
            language_scores[lang]["max_confidence"], confidence
        )
        language_scores[lang]["count"] += 1
        language_scores[lang]["methods"].append(result["method"])

        total_weight += weight

    # Find the language with highest total score
    if not language_scores:
        return "en", 0.05

    # Sort by total score
    sorted_langs = sorted(
        language_scores.items(),
        key=lambda x: (x[1]["total_score"], x[1]["count"], x[1]["max_confidence"]),
        reverse=True,
    )

    winner_lang, winner_data = sorted_langs[0]

    # Calculate final confidence
    # Use a combination of:
    # 1. Normalized total score
    # 2. Maximum confidence from any method
    # 3. Agreement bonus (if multiple methods agree)

    normalized_score = min(winner_data["total_score"] / (total_weight * 0.8), 1.0)
    max_conf = winner_data["max_confidence"]
    agreement_bonus = 0.05 * (winner_data["count"] - 1)  # Bonus for multiple detections

    final_confidence = min(
        (normalized_score * 0.5) + (max_conf * 0.4) + agreement_bonus,
        0.99,  # Cap at 0.99
    )

    return winner_lang, final_confidence


def get_language_keywords(lang_code: str) -> list:
    """Get language-specific keywords for a given language code"""
    return LANGUAGE_KEYWORDS.get(lang_code, [])


def is_supported_language(lang_code: str) -> bool:
    """Check if a language has specific keyword support"""
    return lang_code in LANGUAGE_KEYWORDS


def get_supported_languages() -> dict:
    """Get all supported languages with their keywords"""
    return LANGUAGE_KEYWORDS.copy()
