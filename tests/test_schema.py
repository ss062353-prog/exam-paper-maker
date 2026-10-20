# -*- coding: utf-8 -*-
"""Validate the example spec against schemas/paper.schema.json (optional dep)."""
import json
import os
import unittest

from helpers import EXAMPLE, ROOT

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

SCHEMA = os.path.join(ROOT, "schemas", "paper.schema.json")


class SchemaTests(unittest.TestCase):
    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_example_matches_schema(self):
        with open(EXAMPLE, encoding="utf-8") as fh:
            spec = json.load(fh)
        with open(SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        jsonschema.validate(spec, schema)


if __name__ == "__main__":
    unittest.main()
