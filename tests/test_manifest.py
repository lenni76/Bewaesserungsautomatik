import json
from pathlib import Path
def test_manifest_metadata():
    data=json.loads(Path("custom_components/bewaesserungsautomatik/manifest.json").read_text())
    assert data["domain"]=="bewaesserungsautomatik"
    assert "@lenni76" in data["codeowners"]
    assert data["version"]=="1.0.2"
def test_translations_are_valid_json():
    for path in Path("custom_components/bewaesserungsautomatik/translations").glob("*.json"):
        json.loads(path.read_text())
