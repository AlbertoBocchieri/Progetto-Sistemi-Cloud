import json
from pathlib import Path


SCENARIOS = Path("data/synthetic/demo_scenarios.json")
REQUIRED_FIELDS = {
    "id",
    "label",
    "affected_zones",
    "traffic_pressure",
    "parking_lot_availability",
    "event_pressure",
    "expected_status",
}
VALID_STATUSES = {
    "very_difficult",
    "difficult",
    "uncertain",
    "good",
    "favorable",
}


def assert_probability(scenario: dict, field: str) -> None:
    value = scenario[field]
    assert isinstance(value, int | float), f"{scenario['id']} {field} is not numeric"
    assert 0 <= value <= 1, f"{scenario['id']} {field} must be between 0 and 1"


def main() -> None:
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    assert scenarios, "demo_scenarios.json is empty"

    ids = set()
    for scenario in scenarios:
        missing = REQUIRED_FIELDS - set(scenario)
        assert not missing, f"{scenario.get('id', '<missing id>')} missing {missing}"
        assert scenario["id"] not in ids, f"duplicate scenario id {scenario['id']}"
        ids.add(scenario["id"])
        assert scenario["affected_zones"], f"{scenario['id']} has no affected zones"
        assert scenario["expected_status"] in VALID_STATUSES

        for field in (
            "traffic_pressure",
            "parking_lot_availability",
            "event_pressure",
        ):
            assert_probability(scenario, field)


if __name__ == "__main__":
    main()
    print("Scenario checks OK")
