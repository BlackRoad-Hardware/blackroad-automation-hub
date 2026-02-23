"""
blackroad-automation-hub — Automation Rules Engine
Production: Rule dataclass, trigger types, condition evaluation, action execution,
JSON rule definitions, execution logging.
"""

from __future__ import annotations
import sqlite3
import json
import re
import threading
import operator
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

DB_PATH = "automation_hub.db"
_LOCK = threading.Lock()


# ─────────────────────────── Enums & Types ──────────────────────────

class TriggerType(str, Enum):
    TIME       = "time"      # cron or interval
    SENSOR     = "sensor"    # sensor value crosses threshold
    EVENT      = "event"     # named system event
    STATE      = "state"     # device/entity state change
    WEBHOOK    = "webhook"   # incoming HTTP call


class ActionType(str, Enum):
    SET_STATE    = "set_state"
    CALL_SERVICE = "call_service"
    SEND_NOTIFY  = "send_notify"
    LOG_MESSAGE  = "log_message"
    RUN_SCENE    = "run_scene"
    DELAY        = "delay"


class ConditionOp(str, Enum):
    EQ   = "=="
    NEQ  = "!="
    GT   = ">"
    GTE  = ">="
    LT   = "<"
    LTE  = "<="
    IN   = "in"
    CONTAINS = "contains"


_OP_MAP: Dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "!=": operator.ne,
    ">":  operator.gt,
    ">=": operator.ge,
    "<":  operator.lt,
    "<=": operator.le,
    "in": lambda a, b: a in b,
    "contains": lambda a, b: b in a,
}


# ─────────────────────────── Dataclasses ────────────────────────────

@dataclass
class Trigger:
    type: str                          # TriggerType value
    config: Dict[str, Any] = field(default_factory=dict)
    # TIME:   {"cron": "*/5 * * * *"} or {"interval_seconds": 300}
    # SENSOR: {"sensor_id": "s1", "op": ">", "value": 30}
    # EVENT:  {"event_name": "motion_detected"}
    # STATE:  {"entity_id": "light.l1", "new_state": "on"}
    # WEBHOOK:{"endpoint": "/webhooks/my_hook"}


@dataclass
class Condition:
    field: str                # dot-path in context, e.g. "sensor.s1.value"
    op: str                   # ConditionOp value
    value: Any
    negate: bool = False

    def evaluate(self, context: Dict[str, Any]) -> bool:
        actual = _resolve_path(self.field, context)
        if actual is None:
            return self.negate   # missing field → condition fails (or passes if negated)
        fn = _OP_MAP.get(self.op)
        if fn is None:
            raise ValueError(f"Unknown condition operator: {self.op!r}")
        result = fn(actual, self.value)
        return (not result) if self.negate else result


@dataclass
class Action:
    type: str                  # ActionType value
    target: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    name: str
    trigger: Trigger
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_triggered: Optional[str] = None
    trigger_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        trigger = Trigger(**d["trigger"])
        conditions = [Condition(**c) for c in d.get("conditions", [])]
        actions = [Action(**a) for a in d.get("actions", [])]
        return cls(
            name=d["name"], trigger=trigger,
            conditions=conditions, actions=actions,
            enabled=d.get("enabled", True),
            priority=d.get("priority", 0),
            description=d.get("description", ""),
            created_at=d.get("created_at", datetime.utcnow().isoformat()),
            last_triggered=d.get("last_triggered"),
            trigger_count=d.get("trigger_count", 0)
        )


# ─────────────────────────── Helpers ────────────────────────────────

def _resolve_path(path: str, context: Dict[str, Any]) -> Any:
    """Resolve dot-separated path in nested dict. e.g. 'sensor.s1.value'"""
    parts = path.split(".")
    val: Any = context
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


# ─────────────────────────── Database ───────────────────────────────

def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with _get_conn(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            name        TEXT PRIMARY KEY,
            definition  TEXT NOT NULL,
            enabled     INTEGER NOT NULL DEFAULT 1,
            priority    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            last_triggered TEXT,
            trigger_count  INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS executions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name   TEXT NOT NULL,
            triggered_by TEXT NOT NULL,
            context     TEXT NOT NULL DEFAULT '{}',
            result      TEXT NOT NULL DEFAULT 'ok',
            error       TEXT,
            ts          TEXT NOT NULL,
            duration_ms REAL,
            FOREIGN KEY(rule_name) REFERENCES rules(name)
        );
        CREATE INDEX IF NOT EXISTS idx_exec_rule ON executions(rule_name, ts);
        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            level       TEXT NOT NULL DEFAULT 'INFO',
            message     TEXT NOT NULL,
            context     TEXT NOT NULL DEFAULT '{}',
            ts          TEXT NOT NULL
        );
        """)
    logger.info("automation_hub DB initialised at %s", db_path)


# ─────────────────────────── Engine ─────────────────────────────────

class AutomationHub:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        init_db(db_path)
        self._service_handlers: Dict[str, Callable[[str, Dict], Any]] = {}
        self._running = False

    # ── Rule management ───────────────────────────────────────────────

    def add_rule(self, rule: Rule) -> Rule:
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?,?,?)",
                (rule.name, json.dumps(rule.to_dict()),
                 int(rule.enabled), rule.priority,
                 rule.created_at, rule.last_triggered,
                 rule.trigger_count)
            )
        self._log("INFO", f"Rule added: {rule.name}", {})
        return rule

    def add_rule_from_json(self, rule_json: str) -> Rule:
        d = json.loads(rule_json)
        rule = Rule.from_dict(d)
        return self.add_rule(rule)

    def get_rule(self, name: str) -> Optional[Rule]:
        with _get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM rules WHERE name=?", (name,)
            ).fetchone()
        if not row:
            return None
        r = Rule.from_dict(json.loads(row["definition"]))
        r.enabled = bool(row["enabled"])
        r.last_triggered = row["last_triggered"]
        r.trigger_count = row["trigger_count"]
        return r

    def enable_rule(self, name: str) -> None:
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "UPDATE rules SET enabled=1 WHERE name=?", (name,)
            )

    def disable_rule(self, name: str) -> None:
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "UPDATE rules SET enabled=0 WHERE name=?", (name,)
            )

    def delete_rule(self, name: str) -> None:
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute("DELETE FROM rules WHERE name=?", (name,))

    def get_active_rules(self) -> List[Rule]:
        with _get_conn(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM rules WHERE enabled=1 ORDER BY priority DESC"
            ).fetchall()
        result = []
        for row in rows:
            r = Rule.from_dict(json.loads(row["definition"]))
            r.enabled = True
            r.last_triggered = row["last_triggered"]
            r.trigger_count = row["trigger_count"]
            result.append(r)
        return result

    def list_rules(self) -> List[Dict[str, Any]]:
        with _get_conn(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name, enabled, priority, last_triggered, trigger_count "
                "FROM rules ORDER BY priority DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Condition & Action evaluation ─────────────────────────────────

    def evaluate_rule(self, rule: Rule, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Returns (should_run, [failed_condition_descriptions])"""
        failed = []
        for cond in rule.conditions:
            try:
                if not cond.evaluate(context):
                    desc = f"{cond.field} {cond.op} {cond.value}"
                    failed.append(desc)
            except Exception as e:
                failed.append(f"error: {e}")
        return (len(failed) == 0), failed

    def execute_action(self, action: Action, context: Dict[str, Any]) -> Any:
        atype = action.type
        if atype == ActionType.LOG_MESSAGE:
            msg = action.params.get("message", "")
            self._log("INFO", f"[rule_action] {msg}", context)
            return {"logged": msg}

        if atype == ActionType.SEND_NOTIFY:
            channel = action.params.get("channel", "default")
            message = action.params.get("message", "")
            # In production: plug in actual notification service
            logger.info("NOTIFY[%s]: %s", channel, message)
            return {"channel": channel, "message": message}

        if atype == ActionType.SET_STATE:
            entity_id = action.target
            new_state = action.params.get("state")
            # In production: call device/entity state manager
            logger.info("SET_STATE %s -> %s", entity_id, new_state)
            return {"entity_id": entity_id, "state": new_state}

        if atype == ActionType.CALL_SERVICE:
            service = action.target
            handler = self._service_handlers.get(service)
            if handler:
                return handler(service, action.params)
            logger.warning("No handler for service: %s", service)
            return {"service": service, "status": "no_handler"}

        if atype == ActionType.DELAY:
            import time
            secs = action.params.get("seconds", 1)
            time.sleep(secs)
            return {"delayed": secs}

        if atype == ActionType.RUN_SCENE:
            scene = action.params.get("scene_name")
            logger.info("RUN_SCENE: %s", scene)
            return {"scene": scene}

        raise ValueError(f"Unknown action type: {atype!r}")

    def register_service(self, name: str, handler: Callable) -> None:
        self._service_handlers[name] = handler

    # ── Rule engine ───────────────────────────────────────────────────

    def run_rule_engine(self, context: Dict[str, Any],
                        trigger_type: Optional[str] = None) -> List[Dict[str, Any]]:
        rules = self.get_active_rules()
        if trigger_type:
            rules = [r for r in rules if r.trigger.type == trigger_type]
        results = []
        for rule in rules:
            start = datetime.utcnow()
            ok, failed = self.evaluate_rule(rule, context)
            if not ok:
                results.append({"rule": rule.name, "status": "skipped",
                                 "failed_conditions": failed})
                continue
            action_results = []
            error_msg = None
            try:
                for action in rule.actions:
                    res = self.execute_action(action, context)
                    action_results.append(res)
                status = "ok"
            except Exception as e:
                status = "error"
                error_msg = str(e)
                logger.error("Rule %s action error: %s", rule.name, e)

            duration_ms = (datetime.utcnow() - start).total_seconds() * 1000
            self._record_execution(rule.name, trigger_type or "manual",
                                   context, status, error_msg, duration_ms)
            self._increment_trigger(rule.name)
            results.append({
                "rule": rule.name, "status": status,
                "actions": action_results, "duration_ms": round(duration_ms, 2)
            })
        return results

    def fire_event(self, event_name: str,
                   event_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        context = {"event": {"name": event_name, "data": event_data or {}},
                   "ts": datetime.utcnow().isoformat()}
        return self.run_rule_engine(context, trigger_type=TriggerType.EVENT)

    def process_sensor_update(self, sensor_id: str,
                              value: float, unit: str = "") -> List[Dict[str, Any]]:
        context = {
            "sensor": {sensor_id: {"value": value, "unit": unit}},
            "event": {"name": "sensor_update", "sensor_id": sensor_id, "value": value},
            "ts": datetime.utcnow().isoformat()
        }
        return self.run_rule_engine(context, trigger_type=TriggerType.SENSOR)

    # ── Execution history ─────────────────────────────────────────────

    def _record_execution(self, rule_name: str, triggered_by: str,
                          context: Dict[str, Any], result: str,
                          error: Optional[str], duration_ms: float) -> None:
        ts = datetime.utcnow().isoformat()
        safe_context = {k: v for k, v in context.items() if k != "credentials"}
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "INSERT INTO executions "
                "(rule_name, triggered_by, context, result, error, ts, duration_ms) "
                "VALUES (?,?,?,?,?,?,?)",
                (rule_name, triggered_by, json.dumps(safe_context),
                 result, error, ts, duration_ms)
            )

    def _increment_trigger(self, rule_name: str) -> None:
        now = datetime.utcnow().isoformat()
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "UPDATE rules SET trigger_count=trigger_count+1, last_triggered=? "
                "WHERE name=?",
                (now, rule_name)
            )

    def get_execution_history(self, rule_name: Optional[str] = None,
                              hours: int = 24) -> List[Dict[str, Any]]:
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        q = "SELECT * FROM executions WHERE ts>=?"
        params: list = [since]
        if rule_name:
            q += " AND rule_name=?"
            params.append(rule_name)
        q += " ORDER BY ts DESC"
        with _get_conn(self.db_path) as conn:
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ── Logging ───────────────────────────────────────────────────────

    def _log(self, level: str, message: str, context: Dict[str, Any]) -> None:
        ts = datetime.utcnow().isoformat()
        with _LOCK, _get_conn(self.db_path) as conn:
            conn.execute(
                "INSERT INTO logs (level, message, context, ts) VALUES (?,?,?,?)",
                (level, message, json.dumps(context), ts)
            )


# ──────────────────────────── Demo ──────────────────────────────────

def demo() -> None:
    import os; os.remove(DB_PATH) if os.path.exists(DB_PATH) else None
    hub = AutomationHub()

    # Rule from JSON
    rule_json = json.dumps({
        "name": "high_temp_alert",
        "trigger": {"type": "sensor", "config": {"sensor_id": "t1"}},
        "conditions": [
            {"field": "sensor.t1.value", "op": ">", "value": 30}
        ],
        "actions": [
            {"type": "send_notify", "params": {"channel": "sms", "message": "High temp!"}},
            {"type": "log_message", "params": {"message": "Temperature threshold exceeded"}}
        ],
        "priority": 10
    })
    hub.add_rule_from_json(rule_json)

    motion_rule = Rule(
        name="motion_lights",
        trigger=Trigger(type=TriggerType.EVENT, config={"event_name": "motion_detected"}),
        conditions=[],
        actions=[Action(type=ActionType.SET_STATE, target="light.hallway",
                        params={"state": "on"})],
        priority=5
    )
    hub.add_rule(motion_rule)

    print("Active rules:", [r.name for r in hub.get_active_rules()])

    results = hub.process_sensor_update("t1", 35.0, "°C")
    print("Sensor trigger results:", results)

    results2 = hub.fire_event("motion_detected", {"room": "hallway"})
    print("Event trigger results:", results2)

    hub.disable_rule("motion_lights")
    print("After disable:", [r.name for r in hub.get_active_rules()])

    print("Executions:", len(hub.get_execution_history()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
