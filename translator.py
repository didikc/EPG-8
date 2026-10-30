#!/usr/bin/env python3
"""
translator.py - Translate EPG XML content to English,
while preserving Indonesian and English text.

Usage:
    python3 translator.py input.xml output.xml
"""

import sys
import gzip
import html
import time
from pathlib import Path

from lxml import etree
from deep_translator import GoogleTranslator
from langdetect import detect

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

TAGS_TO_TRANSLATE = ["title", "desc", "sub-title"]

TARGET_CHANNELS = {
    "HBOAsia.sg@SD",
    "HBOSignatureAsia.sg@SD",
    "HBOFamilyAsia.sg@SD",
    "HBOHitsAsia.sg@SD",
    "CinemaxAsia.sg@SD",
    "AXNAsia.sg@Singapore",
}

MAX_RETRIES = 5
REQUEST_DELAY = 0.25

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def safe_detect(text: str) -> str:
    try:
        return detect(text)
    except Exception:
        return "unknown"


def fix_full_caps(text: str) -> str:
    if not text:
        return text

    if text.strip().isupper():
        return text.lower().title()

    return text


def translate_with_retry(
    text: str,
    translator: GoogleTranslator
) -> str:
    """
    Translate text with automatic retry and backoff.
    """

    for attempt in range(MAX_RETRIES):
        try:
            translated = translator.translate(text)

            translated = (
                html.unescape(translated)
                .replace('"-"', '" - "')
            )

            time.sleep(REQUEST_DELAY)
            return translated

        except Exception as e:
            error = str(e).lower()

            if (
                "too many requests" in error
                or "429" in error
                or "rate limit" in error
            ):
                wait_time = min(60, (attempt + 1) * 5)

                print(
                    f"⏳ Rate limit hit "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}), "
                    f"waiting {wait_time}s..."
                )

                time.sleep(wait_time)
                continue

            print(f"⚠️ Translation failed: {e}")
            break

    return text


def selective_translate(
    text: str,
    translator: GoogleTranslator,
    channel: str = None,
    cache: dict = None
) -> str:

    if not text or not text.strip():
        return text

    text = html.unescape(text).strip()

    if len(text) < 4:
        return text

    if channel in TARGET_CHANNELS:
        text = fix_full_caps(text)

    key = text.casefold()

    # cache hit
    if cache is not None and key in cache:
        return cache[key]

    lang = safe_detect(text)

    # keep English and Indonesian
    if lang in ("en", "id"):
        if cache is not None:
            cache[key] = text
        return text

    translated = translate_with_retry(text, translator)

    if cache is not None:
        cache[key] = translated

    if translated != text:
        print(
            f"🌐 {lang} → EN | "
            f"{text[:60]} -> "
            f"{translated[:60]}"
        )

    return translated


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    if len(sys.argv) < 3:
        print("Usage:")
        print("python3 translator.py input.xml output.xml")
        sys.exit(1)

    input_xml = Path(sys.argv[1])
    output_xml = Path(sys.argv[2])

    output_gz = output_xml.with_suffix(".xml.gz")

    print(f"🔍 Parsing {input_xml}...")

    tree = etree.parse(str(input_xml))
    root = tree.getroot()

    translator = GoogleTranslator(
        source="auto",
        target="en"
    )

    cache = {}

    print("🌍 Translating...\n")

    count = 0

    for elem in root.iter():

        tag = (
            elem.tag.lower()
            if hasattr(elem.tag, "lower")
            else ""
        )

        if tag not in TAGS_TO_TRANSLATE:
            continue

        if not elem.text:
            continue

        parent = elem.getparent()

        channel = (
            parent.get("channel")
            if parent is not None
            else None
        )

        elem.text = selective_translate(
            elem.text,
            translator,
            channel,
            cache
        )

        count += 1

        if count % 500 == 0:
            print(
                f"✅ Processed {count:,} items "
                f"| Cache size: {len(cache):,}"
            )

    print("\n💾 Saving XML...")

    tree.write(
        str(output_xml),
        encoding="utf-8",
        pretty_print=True,
        xml_declaration=True
    )

    print("📦 Compressing GZ...")

    with gzip.open(output_gz, "wb") as f:
        f.write(
            etree.tostring(
                root,
                encoding="utf-8",
                pretty_print=True
            )
        )

    print("\n✅ DONE")
    print(f"Processed entries : {count:,}")
    print(f"Cached texts      : {len(cache):,}")
    print(f"XML Output        : {output_xml}")
    print(f"GZ Output         : {output_gz}")


if __name__ == "__main__":
    main()
