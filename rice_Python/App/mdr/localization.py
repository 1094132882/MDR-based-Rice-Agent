"""English display values for metadata responses; graph values stay unchanged."""

import json
from pathlib import Path


TRANSLATIONS = json.loads(
    (Path(__file__).resolve().parents[3] / "scripts/localization/translations.en.json")
    .read_text(encoding="utf-8")
)
DISPLAY_FIELDS = {
    "name", "status", "evolution", "indefinite", "segmentation",
    "describe", "description",
}


def english_metadata(value):
    """Prefer stored English attributes, including in nested metadata objects.

    Identifiers, property keys, raw sample data, and unknown strings are preserved.
    The dictionary covers display values copied into relationship summaries that
    do not include the source node's English attributes.
    """
    if isinstance(value, list):
        return [english_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, original in value.items():
        if key.endswith("_en") and key[:-3] in DISPLAY_FIELDS:
            continue
        if key == "sample_data":
            result[key] = original
        elif key in DISPLAY_FIELDS and isinstance(original, str):
            translated = value.get(key + "_en")
            result[key] = translated if isinstance(translated, str) and translated else TRANSLATIONS.get(original, original)
        else:
            result[key] = english_metadata(original)
    return result


def localize_metadata_response(response):
    """Apply English display values only to successful MDR/MFI JSON responses."""
    from flask import current_app, request

    if (request.path.startswith(("/mdr/", "/mfi/"))
            and 200 <= response.status_code < 300 and response.is_json):
        response.set_data(current_app.json.dumps(english_metadata(response.get_json())))
    return response
