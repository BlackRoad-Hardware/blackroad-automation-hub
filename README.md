<!-- BlackRoad SEO Enhanced -->

# ulackroad automation hub

> Part of **[BlackRoad OS](https://blackroad.io)** — Sovereign Computing for Everyone

[![BlackRoad OS](https://img.shields.io/badge/BlackRoad-OS-ff1d6c?style=for-the-badge)](https://blackroad.io)
[![BlackRoad-Hardware](https://img.shields.io/badge/Org-BlackRoad-Hardware-2979ff?style=for-the-badge)](https://github.com/BlackRoad-Hardware)

**ulackroad automation hub** is part of the **BlackRoad OS** ecosystem — a sovereign, distributed operating system built on edge computing, local AI, and mesh networking by **BlackRoad OS, Inc.**

### BlackRoad Ecosystem
| Org | Focus |
|---|---|
| [BlackRoad OS](https://github.com/BlackRoad-OS) | Core platform |
| [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc) | Corporate |
| [BlackRoad AI](https://github.com/BlackRoad-AI) | AI/ML |
| [BlackRoad Hardware](https://github.com/BlackRoad-Hardware) | Edge hardware |
| [BlackRoad Security](https://github.com/BlackRoad-Security) | Cybersecurity |
| [BlackRoad Quantum](https://github.com/BlackRoad-Quantum) | Quantum computing |
| [BlackRoad Agents](https://github.com/BlackRoad-Agents) | AI agents |
| [BlackRoad Network](https://github.com/BlackRoad-Network) | Mesh networking |

**Website**: [blackroad.io](https://blackroad.io) | **Chat**: [chat.blackroad.io](https://chat.blackroad.io) | **Search**: [search.blackroad.io](https://search.blackroad.io)

---


> Automation rules engine - triggers, conditions, actions

Part of the [BlackRoad OS](https://blackroad.io) ecosystem — [BlackRoad-Hardware](https://github.com/BlackRoad-Hardware)

---

# blackroad-automation-hub

Part of [BlackRoad-Hardware](https://github.com/BlackRoad-Hardware) — IoT & hardware intelligence platform.

## Overview

| Repo | Description |
|------|-------------|
| blackroad-smart-home | Smart home controller: scenes, scheduling, device groups |
| blackroad-sensor-network | IoT sensor aggregator with Z-score anomaly detection |
| blackroad-automation-hub | Rules engine: triggers, conditions, actions |
| blackroad-energy-optimizer | Energy tracking, peak analysis, CO2 equivalent |
| blackroad-fleet-tracker | Fleet GPS tracking, geofencing, idle detection |

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
python automation-hub.py   # runs demo
```

## Tests

```bash
pytest test_automation-hub.py -v
```

## Architecture

- Pure Python with SQLite persistence (WAL mode)
- Thread-safe with per-operation locks
- Self-initializing database on first run
- Dataclass-based domain model

## License

© BlackRoad OS, Inc. All rights reserved.
