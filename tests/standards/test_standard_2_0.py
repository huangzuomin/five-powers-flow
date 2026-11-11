import hashlib
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = REPO_ROOT / "tools" / "standards" / "verify_standard.py"
OUTPUT_PATH = REPO_ROOT / "tools" / "standards" / "verify-output.json"
DIGEST_PATH = REPO_ROOT / "tools" / "standards" / "verify-output.sha256"

_SPEC = importlib.util.spec_from_file_location("verify_standard", VERIFY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("无法载入标准校验器")
VERIFY_STANDARD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VERIFY_STANDARD)


def test_standard_verification_passes():
    payload, _ = VERIFY_STANDARD.verify_repo(REPO_ROOT)
    assert payload["summary"]["failed"] == 0, json.dumps(
        payload, ensure_ascii=False, sort_keys=True
    )


def test_verification_output_is_byte_deterministic():
    _, output = VERIFY_STANDARD.verify_repo(REPO_ROOT)
    assert output == OUTPUT_PATH.read_bytes()


def test_verification_output_digest_matches_record():
    output_digest = hashlib.sha256(OUTPUT_PATH.read_bytes()).hexdigest()
    recorded = DIGEST_PATH.read_text(encoding="utf-8").strip().split()[0]
    assert output_digest == recorded
