"""Tests for blackroad-automation-hub."""
import json, pytest
from automation_hub import (
    AutomationHub, Rule, Trigger, Condition, Action,
    TriggerType, ActionType
)


@pytest.fixture
def hub(tmp_path):
    h = AutomationHub(db_path=str(tmp_path / "test.db"))
    rule = Rule(
        name="temp_alert",
        trigger=Trigger(type=TriggerType.SENSOR, config={"sensor_id": "t1"}),
        conditions=[Condition(field="sensor.t1.value", op=">", value=30.0)],
        actions=[Action(type=ActionType.LOG_MESSAGE, params={"message": "hot!"})],
        priority=5
    )
    h.add_rule(rule)
    return h


def test_add_and_get_rule(hub):
    r = hub.get_rule("temp_alert")
    assert r is not None
    assert r.name == "temp_alert"


def test_get_active_rules(hub):
    rules = hub.get_active_rules()
    assert any(r.name == "temp_alert" for r in rules)


def test_enable_disable_rule(hub):
    hub.disable_rule("temp_alert")
    assert len(hub.get_active_rules()) == 0
    hub.enable_rule("temp_alert")
    assert len(hub.get_active_rules()) == 1


def test_condition_passes(hub):
    rule = hub.get_rule("temp_alert")
    ctx = {"sensor": {"t1": {"value": 35.0}}}
    ok, failed = hub.evaluate_rule(rule, ctx)
    assert ok is True and failed == []


def test_condition_fails(hub):
    rule = hub.get_rule("temp_alert")
    ctx = {"sensor": {"t1": {"value": 20.0}}}
    ok, failed = hub.evaluate_rule(rule, ctx)
    assert ok is False and len(failed) > 0


def test_process_sensor_update_triggers(hub):
    results = hub.process_sensor_update("t1", 40.0, "°C")
    executed = [r for r in results if r["status"] == "ok"]
    assert len(executed) == 1


def test_process_sensor_below_threshold(hub):
    results = hub.process_sensor_update("t1", 20.0, "°C")
    skipped = [r for r in results if r["status"] == "skipped"]
    assert len(skipped) == 1


def test_fire_event(hub):
    event_rule = Rule(
        name="motion_on",
        trigger=Trigger(type=TriggerType.EVENT, config={"event_name": "motion"}),
        actions=[Action(type=ActionType.LOG_MESSAGE, params={"message": "motion!"})],
    )
    hub.add_rule(event_rule)
    results = hub.fire_event("motion", {"room": "hall"})
    assert any(r["rule"] == "motion_on" for r in results)


def test_add_rule_from_json(hub):
    rule_j = json.dumps({
        "name": "json_rule",
        "trigger": {"type": "event", "config": {}},
        "conditions": [],
        "actions": [{"type": "log_message", "params": {"message": "ok"}}]
    })
    r = hub.add_rule_from_json(rule_j)
    assert r.name == "json_rule"


def test_trigger_count_increments(hub):
    hub.process_sensor_update("t1", 50.0, "°C")
    hub.process_sensor_update("t1", 60.0, "°C")
    r = hub.get_rule("temp_alert")
    assert r.trigger_count >= 2


def test_execution_history(hub):
    hub.process_sensor_update("t1", 50.0, "°C")
    hist = hub.get_execution_history("temp_alert")
    assert len(hist) >= 1
