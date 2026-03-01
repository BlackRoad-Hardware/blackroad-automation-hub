# BlackRoad Automation Hub

[![PyPI version](https://img.shields.io/pypi/v/blackroad-automation-hub.svg)](https://pypi.org/project/blackroad-automation-hub/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](test_automation_hub.py)

> **Production-grade IoT automation rules engine** — part of the [BlackRoad Hardware](https://github.com/BlackRoad-Hardware) platform. Define triggers, evaluate conditions, and execute actions across any connected device fleet.

---

## Table of Contents

1. [Overview](#1-overview)
2. [BlackRoad Ecosystem](#2-blackroad-ecosystem)
3. [Features](#3-features)
4. [Quick Start](#4-quick-start)
5. [Installation](#5-installation)
   - [Python / PyPI](#python--pypi)
   - [JavaScript / npm](#javascript--npm)
6. [Configuration](#6-configuration)
7. [Core Concepts](#7-core-concepts)
   - [Rules](#rules)
   - [Trigger Types](#trigger-types)
   - [Condition Operators](#condition-operators)
   - [Action Types](#action-types)
8. [API Reference](#8-api-reference)
   - [AutomationHub](#automationhub)
   - [Rule Management](#rule-management)
   - [Rule Engine](#rule-engine)
   - [Execution History](#execution-history)
9. [JSON Rule Schema](#9-json-rule-schema)
10. [Stripe Integration](#10-stripe-integration)
    - [Billing Webhooks as Triggers](#billing-webhooks-as-triggers)
    - [Subscription-Gated Rules](#subscription-gated-rules)
    - [Example Stripe Webhook Rule](#example-stripe-webhook-rule)
11. [Database Schema](#11-database-schema)
12. [E2E Testing](#12-e2e-testing)
    - [Unit Tests](#unit-tests)
    - [End-to-End Test Scenarios](#end-to-end-test-scenarios)
    - [Running the Full Suite](#running-the-full-suite)
13. [Deployment](#13-deployment)
14. [Contributing](#14-contributing)
15. [License](#15-license)

---

## 1. Overview

**BlackRoad Automation Hub** is the rules engine at the center of the BlackRoad IoT platform. It processes events, sensor readings, and external webhooks (including Stripe billing events), evaluates user-defined conditions, and executes configurable actions — all persisted to SQLite with WAL-mode durability.

Key design goals:

- **Zero-dependency core** — pure Python 3.10+, SQLite storage, no external message broker required.
- **Declarative rules** — define rules as JSON; load, enable, disable, or delete them at runtime.
- **Thread-safe** — all write operations protected by a per-engine lock; safe for multi-threaded WSGI/ASGI deployments.
- **Stripe-ready** — first-class WEBHOOK trigger type maps directly onto Stripe event webhooks.
- **Observable** — every rule execution is logged with duration, context, and result status.

---

## 2. BlackRoad Ecosystem

| Repository | Description |
|---|---|
| [blackroad-smart-home](https://github.com/BlackRoad-Hardware/blackroad-smart-home) | Smart home controller — scenes, scheduling, device groups |
| [blackroad-sensor-network](https://github.com/BlackRoad-Hardware/blackroad-sensor-network) | IoT sensor aggregator with Z-score anomaly detection |
| **blackroad-automation-hub** | **Rules engine — triggers, conditions, actions** ← *you are here* |
| [blackroad-energy-optimizer](https://github.com/BlackRoad-Hardware/blackroad-energy-optimizer) | Energy tracking, peak analysis, CO₂ equivalent |
| [blackroad-fleet-tracker](https://github.com/BlackRoad-Hardware/blackroad-fleet-tracker) | Fleet GPS tracking, geofencing, idle detection |

---

## 3. Features

- **Five trigger types** — `time`, `sensor`, `event`, `state`, `webhook`
- **Eight condition operators** — `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `contains`
- **Six action types** — `set_state`, `call_service`, `send_notify`, `log_message`, `run_scene`, `delay`
- **Priority ordering** — higher-priority rules execute first within a trigger cycle
- **Condition negation** — any condition can be inverted with `"negate": true`
- **Execution logging** — full history table with duration, context snapshot, and error capture
- **JSON rule definitions** — load rules at runtime from any source (file, API, Stripe webhook payload)
- **Service handler registry** — plug in custom handlers for `call_service` actions
- **Stripe billing integration** — map Stripe webhook events to automation triggers

---

## 4. Quick Start

```python
from automation_hub import AutomationHub, Rule, Trigger, Condition, Action
from automation_hub import TriggerType, ActionType

hub = AutomationHub()                          # initialises SQLite DB automatically

rule = Rule(
    name="high_temp_alert",
    trigger=Trigger(type=TriggerType.SENSOR, config={"sensor_id": "t1"}),
    conditions=[Condition(field="sensor.t1.value", op=">", value=30.0)],
    actions=[Action(type=ActionType.SEND_NOTIFY,
                    params={"channel": "sms", "message": "Temperature too high!"})],
    priority=10,
)
hub.add_rule(rule)

# Fire a sensor update — rule triggers automatically
results = hub.process_sensor_update("t1", 35.0, "°C")
print(results)
# [{'rule': 'high_temp_alert', 'status': 'ok', 'actions': [...], 'duration_ms': 0.82}]
```

---

## 5. Installation

### Python / PyPI

```bash
pip install blackroad-automation-hub
```

Or install from source:

```bash
git clone https://github.com/BlackRoad-Hardware/blackroad-automation-hub.git
cd blackroad-automation-hub
pip install -r requirements.txt
```

Run the built-in demo:

```bash
python automation_hub.py
```

### JavaScript / npm

A lightweight JavaScript client is available for Node.js applications that need to push sensor events or fire webhooks into a running Automation Hub instance:

```bash
npm install @blackroad/automation-hub-client
```

```js
import { AutomationHubClient } from '@blackroad/automation-hub-client';

const hub = new AutomationHubClient({ baseUrl: 'https://your-hub.example.com' });

// Fire a sensor update
await hub.sensorUpdate({ sensorId: 't1', value: 35.0, unit: '°C' });

// Fire a named event
await hub.fireEvent('motion_detected', { room: 'hallway' });

// Register a Stripe webhook relay
await hub.webhook('/webhooks/stripe', stripePayload);
```

> **Note:** The Python engine exposes an HTTP API when deployed behind a WSGI server such as Gunicorn or uWSGI. The npm client connects to that API.

---

## 6. Configuration

| Environment variable | Default | Description |
|---|---|---|
| `AUTOMATION_HUB_DB` | `automation_hub.db` | Path to the SQLite database file |
| `STRIPE_WEBHOOK_SECRET` | — | Stripe webhook signing secret for payload verification |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

```python
import os
os.environ["AUTOMATION_HUB_DB"] = "/data/production.db"

from automation_hub import AutomationHub
hub = AutomationHub(db_path=os.environ["AUTOMATION_HUB_DB"])
```

---

## 7. Core Concepts

### Rules

A **Rule** is the central unit. It binds a **Trigger** (what fires it) to a list of **Conditions** (guards) and **Actions** (effects).

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Unique rule identifier |
| `trigger` | `Trigger` | What activates this rule |
| `conditions` | `list[Condition]` | All must pass for actions to execute |
| `actions` | `list[Action]` | Executed in order when all conditions pass |
| `enabled` | `bool` | Toggle without deleting |
| `priority` | `int` | Execution order within a trigger cycle (higher = first) |
| `description` | `str` | Human-readable description |

### Trigger Types

| Type | Config keys | Description |
|---|---|---|
| `time` | `cron`, `interval_seconds` | Scheduled execution |
| `sensor` | `sensor_id`, `op`, `value` | Sensor value threshold crossing |
| `event` | `event_name` | Named system event |
| `state` | `entity_id`, `new_state` | Device or entity state change |
| `webhook` | `endpoint` | Inbound HTTP call — including Stripe webhooks |

### Condition Operators

| Operator | Description | Example |
|---|---|---|
| `==` | Equal | `"sensor.t1.value" == 30` |
| `!=` | Not equal | `"event.name" != "ignored"` |
| `>` | Greater than | `"sensor.t1.value" > 30` |
| `>=` | Greater than or equal | `"sensor.t1.value" >= 30` |
| `<` | Less than | `"sensor.t1.value" < 10` |
| `<=` | Less than or equal | `"sensor.t1.value" <= 10` |
| `in` | Value is in list | `"event.name" in ["a","b"]` |
| `contains` | Collection contains value | `"sensor.tags" contains "critical"` |

Set `"negate": true` on any condition to invert the result.

### Action Types

| Type | Key fields | Description |
|---|---|---|
| `log_message` | `params.message` | Write to internal log table |
| `send_notify` | `params.channel`, `params.message` | Dispatch notification (SMS, email, push) |
| `set_state` | `target` (entity_id), `params.state` | Update a device/entity state |
| `call_service` | `target` (service name), `params` | Call a registered service handler |
| `run_scene` | `params.scene_name` | Activate a named scene |
| `delay` | `params.seconds` | Pause execution pipeline |

---

## 8. API Reference

### AutomationHub

```python
AutomationHub(db_path: str = "automation_hub.db")
```

Creates (or opens) an automation hub backed by the given SQLite file. The database schema is created automatically on first use.

### Rule Management

| Method | Signature | Description |
|---|---|---|
| `add_rule` | `(rule: Rule) -> Rule` | Persist a rule (upsert) |
| `add_rule_from_json` | `(rule_json: str) -> Rule` | Parse JSON string and persist |
| `get_rule` | `(name: str) -> Rule \| None` | Fetch a rule by name |
| `list_rules` | `() -> list[dict]` | Summary list of all rules |
| `get_active_rules` | `() -> list[Rule]` | Enabled rules, ordered by priority |
| `enable_rule` | `(name: str) -> None` | Enable a disabled rule |
| `disable_rule` | `(name: str) -> None` | Disable without deleting |
| `delete_rule` | `(name: str) -> None` | Permanently remove a rule |

### Rule Engine

| Method | Signature | Description |
|---|---|---|
| `run_rule_engine` | `(context, trigger_type?) -> list[dict]` | Evaluate all active rules against context |
| `fire_event` | `(event_name, event_data?) -> list[dict]` | Convenience: fires all `event` rules |
| `process_sensor_update` | `(sensor_id, value, unit?) -> list[dict]` | Convenience: fires all `sensor` rules |
| `evaluate_rule` | `(rule, context) -> (bool, list[str])` | Returns `(should_run, failed_conditions)` |
| `execute_action` | `(action, context) -> Any` | Executes a single action |
| `register_service` | `(name, handler) -> None` | Register a `call_service` handler |

### Execution History

| Method | Signature | Description |
|---|---|---|
| `get_execution_history` | `(rule_name?, hours?) -> list[dict]` | Retrieve past executions (default: last 24 h) |

---

## 9. JSON Rule Schema

Rules can be defined as JSON and loaded at runtime — from files, REST APIs, or Stripe webhook payloads:

```json
{
  "name": "high_temp_alert",
  "description": "Send SMS when temperature exceeds 30 °C",
  "priority": 10,
  "enabled": true,
  "trigger": {
    "type": "sensor",
    "config": { "sensor_id": "t1" }
  },
  "conditions": [
    {
      "field": "sensor.t1.value",
      "op": ">",
      "value": 30,
      "negate": false
    }
  ],
  "actions": [
    {
      "type": "send_notify",
      "params": { "channel": "sms", "message": "High temp detected!" }
    },
    {
      "type": "log_message",
      "params": { "message": "Temperature threshold exceeded" }
    }
  ]
}
```

Load from a file:

```python
import json
with open("rules/high_temp_alert.json") as f:
    hub.add_rule_from_json(f.read())
```

---

## 10. Stripe Integration

BlackRoad Automation Hub has first-class support for [Stripe](https://stripe.com) via the `webhook` trigger type. Stripe sends signed HTTP POST payloads to your endpoint; the hub verifies the signature and fires matching rules.

### Billing Webhooks as Triggers

```python
import stripe
import os

STRIPE_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

def handle_stripe_webhook(raw_body: bytes, sig_header: str) -> list:
    """Verify Stripe signature, then fire the hub."""
    event = stripe.Webhook.construct_event(raw_body, sig_header, STRIPE_SECRET)
    return hub.fire_event(
        event_name=f"stripe.{event['type']}",
        event_data=event["data"]["object"],
    )
```

### Subscription-Gated Rules

Use conditions to only execute actions for active subscriptions:

```json
{
  "name": "premium_scene_on_arrival",
  "trigger": { "type": "event", "config": { "event_name": "user.arrived" } },
  "conditions": [
    { "field": "event.data.subscription_status", "op": "==", "value": "active" }
  ],
  "actions": [
    { "type": "run_scene", "params": { "scene_name": "welcome_home_premium" } }
  ]
}
```

### Example Stripe Webhook Rule

Handle `invoice.payment_succeeded` to unlock a premium automation scene:

```json
{
  "name": "stripe_payment_unlock_premium",
  "description": "Unlock premium scenes when Stripe invoice is paid",
  "trigger": {
    "type": "webhook",
    "config": { "endpoint": "/webhooks/stripe" }
  },
  "conditions": [
    {
      "field": "event.data.object.status",
      "op": "==",
      "value": "paid"
    }
  ],
  "actions": [
    {
      "type": "call_service",
      "target": "subscription_manager",
      "params": { "action": "activate_premium" }
    },
    {
      "type": "send_notify",
      "params": {
        "channel": "email",
        "message": "Your BlackRoad Premium subscription is now active."
      }
    }
  ],
  "priority": 100
}
```

> **Security note:** Always verify the `Stripe-Signature` header using `stripe.Webhook.construct_event` before passing a payload to the hub. Never process unsigned webhook payloads in production.

---

## 11. Database Schema

The hub auto-creates three tables in SQLite on first run:

### `rules`

| Column | Type | Description |
|---|---|---|
| `name` | TEXT PK | Unique rule name |
| `definition` | TEXT | Full rule JSON |
| `enabled` | INTEGER | 1 = active, 0 = disabled |
| `priority` | INTEGER | Execution order (higher first) |
| `created_at` | TEXT | ISO-8601 creation timestamp |
| `last_triggered` | TEXT | ISO-8601 last execution timestamp |
| `trigger_count` | INTEGER | Total successful executions |

### `executions`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `rule_name` | TEXT FK | References `rules.name` |
| `triggered_by` | TEXT | Trigger type that fired the rule |
| `context` | TEXT | JSON context snapshot (credentials stripped) |
| `result` | TEXT | `ok` or `error` |
| `error` | TEXT | Error message if `result = error` |
| `ts` | TEXT | ISO-8601 execution timestamp |
| `duration_ms` | REAL | Wall-clock execution time |

Index: `idx_exec_rule` on `(rule_name, ts)` for fast history queries.

### `logs`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `level` | TEXT | `INFO`, `WARNING`, `ERROR` |
| `message` | TEXT | Log message |
| `context` | TEXT | JSON context |
| `ts` | TEXT | ISO-8601 timestamp |

---

## 12. E2E Testing

### Unit Tests

All core engine logic is covered by the test suite in [`test_automation_hub.py`](test_automation_hub.py):

| Test | Description |
|---|---|
| `test_add_and_get_rule` | Rule persisted and retrieved correctly |
| `test_get_active_rules` | Only enabled rules returned |
| `test_enable_disable_rule` | Toggle without data loss |
| `test_condition_passes` | Condition evaluates `True` with matching context |
| `test_condition_fails` | Condition evaluates `False` with non-matching context |
| `test_process_sensor_update_triggers` | Sensor update fires and executes a matching rule |
| `test_process_sensor_below_threshold` | Rule skipped when condition not met |
| `test_fire_event` | Named event fires an event-triggered rule |
| `test_add_rule_from_json` | JSON string parsed and persisted correctly |
| `test_trigger_count_increments` | Execution counter increments on each fire |
| `test_execution_history` | Execution record written and retrievable |

### End-to-End Test Scenarios

These scenarios validate the complete request → rule evaluation → action execution path:

**Scenario 1 — Sensor threshold alert**
```
Input:  process_sensor_update("t1", 35.0, "°C")
Expect: rule "high_temp_alert" fires, SEND_NOTIFY action executes, execution recorded
```

**Scenario 2 — Event-driven state change**
```
Input:  fire_event("motion_detected", {"room": "hallway"})
Expect: rule "motion_lights" fires, SET_STATE action sets light.hallway → "on"
```

**Scenario 3 — Stripe webhook → premium unlock**
```
Input:  fire_event("stripe.invoice.payment_succeeded", {"status": "paid"})
Expect: rule "stripe_payment_unlock_premium" fires, call_service "subscription_manager" called
```

**Scenario 4 — Rule priority ordering**
```
Input:  two rules with priority 10 and 5 both matching
Expect: priority-10 rule executes before priority-5 rule
```

**Scenario 5 — Disabled rule is skipped**
```
Input:  disable_rule("high_temp_alert"), then process_sensor_update("t1", 35.0)
Expect: no rules executed, execution history unchanged
```

### Running the Full Suite

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests with verbose output
pytest test_automation_hub.py -v

# Run with coverage report
pip install pytest-cov
pytest test_automation_hub.py -v --cov=automation_hub --cov-report=term-missing

# Run a specific test
pytest test_automation_hub.py::test_process_sensor_update_triggers -v
```

Expected output:

```
test_automation_hub.py::test_add_and_get_rule              PASSED
test_automation_hub.py::test_get_active_rules              PASSED
test_automation_hub.py::test_enable_disable_rule           PASSED
test_automation_hub.py::test_condition_passes              PASSED
test_automation_hub.py::test_condition_fails               PASSED
test_automation_hub.py::test_process_sensor_update_triggers PASSED
test_automation_hub.py::test_process_sensor_below_threshold PASSED
test_automation_hub.py::test_fire_event                    PASSED
test_automation_hub.py::test_add_rule_from_json            PASSED
test_automation_hub.py::test_trigger_count_increments      PASSED
test_automation_hub.py::test_execution_history             PASSED

=========== 11 passed in 0.15s ===========
```

---

## 13. Deployment

### Standalone (demo / development)

```bash
python automation_hub.py
```

### Production (Gunicorn + WSGI wrapper)

Wrap `AutomationHub` in a WSGI/ASGI app (e.g. Flask, FastAPI) and deploy:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 your_app:app
```

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV AUTOMATION_HUB_DB=/data/automation_hub.db
VOLUME ["/data"]
CMD ["python", "automation_hub.py"]
```

```bash
docker build -t blackroad-automation-hub .
docker run -v hub_data:/data -p 8000:8000 blackroad-automation-hub
```

### Environment variables checklist

- [ ] `AUTOMATION_HUB_DB` — path to a persistent volume
- [ ] `STRIPE_WEBHOOK_SECRET` — from Stripe Dashboard → Webhooks → Signing secret
- [ ] `LOG_LEVEL=WARNING` — reduce log verbosity in production

---

## 14. Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Add tests for your changes
4. Run the full test suite: `pytest test_automation_hub.py -v`
5. Open a pull request against `main`

Please follow the existing code style: dataclasses, type hints, and SQLite persistence. No new runtime dependencies without prior discussion.

---

## 15. License

© BlackRoad OS, Inc. All rights reserved.

This software is proprietary. Unauthorised copying, distribution, or modification is prohibited. See [LICENSE](LICENSE) for full terms.
