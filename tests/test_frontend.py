"""Frontend data-shape tests that do not require a running Streamlit server."""

import sys
import types


if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = types.ModuleType("streamlit")

from frontend.app import _normalise_flow_steps, _normalize_assertions


def test_flow_step_normalization_keeps_order_and_edits_multiple_assertions():
    """Each flow step gets editable list configs without losing request data."""
    testcase = {
        "id": "flow-1",
        "steps": [
            {
                "step_order": 2,
                "endpoint": {"method": "GET", "url": "/profile"},
                "assertions": {
                    "status": {"enabled": True, "expected_status": 200},
                    "jsonpath": [
                        {"enabled": True, "path": "$.id", "expected_value": "7"},
                        {"enabled": True, "path": "$.name", "expected_value": "Ada"},
                    ],
                },
                "variable_mappings": [{"from": "$.token", "to": "headers.Authorization"}],
            },
            {
                "step_order": 1,
                "endpoint": {"method": "POST", "url": "/login"},
                "assertions": {"status": [{"enabled": True, "expected_status": 200}]},
            },
        ],
    }

    steps = _normalise_flow_steps(testcase)

    assert [step["step_order"] for step in steps] == [1, 2]
    assert steps[1]["assertions"]["jsonpath"] == [
        {"enabled": True, "path": "$.id", "expected_value": "7"},
        {"enabled": True, "path": "$.name", "expected_value": "Ada"},
    ]
    assert steps[1]["variable_mappings"][0]["from"] == "$.token"
    assert steps[1]["endpoint"]["url"] == "/profile"


def test_single_case_assertions_normalize_legacy_dicts():
    """Existing single-dictionary assertion payloads become editable lists."""
    testcase = {
        "assertions": {
            "status": {"enabled": True, "expected_status": 201},
        }
    }

    assertions = _normalize_assertions(testcase)

    assert assertions["status"] == [{"enabled": True, "expected_status": 201}]
    assert assertions["body_contains"][0]["enabled"] is False
