"""Verify generated bootstrap manifests against public JSON Schemas."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
import jsonschema
import yaml
from packages.fpf_bootstrap.artifacts import bundle


class TestBootstrapContracts(unittest.TestCase):
    def test_generated_config_conforms_to_schemas(self):
        root = Path(__file__).resolve().parents[1]
        discovery = {
            "sha": "a" * 40, "base_ref": "main", "tracked_files": 2,
            "modules": ["src"], "documents": [
                {"path": "README.md", "headings": ["Overview"], "note": "unverified_document"}
            ],
        }
        for mode in ("api", "manual"):
            files = bundle("MYAPP01", "Demo", discovery, mode)
            for rel, schema_file in [
                (".fpf/project.yaml", "schemas/bootstrap-manifest.schema.json"),
                (".fpf/agents.yaml", "schemas/agent-registry.schema.json"),
            ]:
                obj = yaml.safe_load(files[rel])
                schema = json.loads((root / schema_file).read_text(encoding="utf-8"))
                jsonschema.validate(obj, schema)
            self.assertNotIn("QA_PASS", files[".fpf/agents.yaml"])


if __name__ == "__main__":
    unittest.main()
