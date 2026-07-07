"""Dump the skene server's OpenAPI spec, downgraded to 3.0.x for oapi-codegen.

FastAPI emits OpenAPI 3.1 (JSON Schema 2020-12), which oapi-codegen does not
support yet (oapi-codegen/oapi-codegen#373). This script converts the 3.1
constructs pydantic actually produces into their 3.0 equivalents:

  - ``anyOf: [X, {type: null}]``        -> ``X`` + ``nullable: true``
  - ``const: v``                        -> ``enum: [v]``
  - ``examples: [...]``                 -> ``example: ...``
  - numeric ``exclusiveMinimum/Maximum``-> bool form + ``minimum/maximum``

It also marks single-value-enum properties (the discriminator literals:
``type``, ``role``, ``status``) as required — pydantic leaves defaulted
fields out of ``required``, which makes oapi-codegen generate them as
pointers and its union helpers fail to compile. The server always
serializes them, so requiring them is faithful to the wire.

Run from tui/: ``uv run --project .. python scripts/dump_openapi.py > internal/api/openapi.json``
(the Makefile's ``generate`` target does this for you).
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _downgrade(node: Any) -> Any:
    if isinstance(node, list):
        return [_downgrade(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = {key: _downgrade(value) for key, value in node.items()}

    if "const" in node:
        node["enum"] = [node.pop("const")]

    if "examples" in node and isinstance(node["examples"], list) and node["examples"]:
        node.setdefault("example", node["examples"][0])
        del node["examples"]

    for bound, limit in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if isinstance(node.get(bound), (int, float)) and not isinstance(node.get(bound), bool):
            node[limit] = node.pop(bound)
            node[bound] = True

    properties = node.get("properties")
    if isinstance(properties, dict):
        required = set(node.get("required", []))
        for name, prop in properties.items():
            if isinstance(prop, dict) and isinstance(prop.get("enum"), list) and len(prop["enum"]) == 1:
                required.add(name)
        if required:
            node["required"] = sorted(required)

    any_of = node.get("anyOf")
    if isinstance(any_of, list) and {"type": "null"} in any_of:
        rest = [sub for sub in any_of if sub != {"type": "null"}]
        del node["anyOf"]
        if len(rest) == 1 and "$ref" not in rest[0]:
            node.update(rest[0])
        elif rest:
            # $ref siblings are ignored in 3.0, so wrap instead of merging.
            node["anyOf"] = rest
        node["nullable"] = True

    return node


def main() -> None:
    from skene.server import create_app

    spec = create_app().openapi()
    spec["openapi"] = "3.0.3"
    json.dump(_downgrade(spec), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
