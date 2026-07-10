# Memory Lab

`memory-lab` is a deterministic, offline experiment bench for Agent Memory. It compares three policies while keeping the task, simulated tools, planner, and runtime budget fixed:

- `none`: no cross-session memory.
- `naive`: retrieves raw trajectories only by text similarity.
- `governed`: retrieves structured Memory Cards through scope, source, validity, risk, and relevance admission filters.

It implements the design document's deterministic demo project: integration tests require `APP_ENV=test`, then initialized fixtures. `force=True` is always rejected safely.

## Setup

The documented commands run directly from a source checkout. To install the package into an environment with Python 3.11+, use:

```powershell
python -m pip install -e .
```

## Demonstration

Run these commands from this repository's root. Every `run` creates a new session, so no chat history crosses the session boundary.

```powershell
python -m memory_lab reset

# Learn a reusable procedure from a failure trajectory.
python -m memory_lab run learn-1 --mode governed
python -m memory_lab memory list
python -m memory_lab memory show mem-001

# Compare the second task. Governed mode reuses the verified procedural card.
python -m memory_lab run learn-2 --mode none
python -m memory_lab run learn-2 --mode governed

# Add a semantically tempting but unsafe memory.
python -m memory_lab inject unsafe-memory
python -m memory_lab run injection --mode naive
python -m memory_lab run injection --mode governed
python -m memory_lab memory explain --scenario injection --mode governed

python -m memory_lab report
```

`NaiveMemory` deliberately records raw traces only when it itself runs a learning task. To see safe raw-trajectory reuse, use `run learn-1 --mode naive` before `run learn-2 --mode naive`.

## Safety and inspection

The `governed` reader evaluates every candidate before prompt assembly. A card with the wrong project scope, untrusted source, high risk, expired validity, or low confidence is rejected and its reason codes remain visible through `memory explain`. Rejected cards are not passed to the planner.

Persistent demonstration state defaults to `data/` and contains an append-only `events.jsonl`, `metrics.jsonl`, and a SQLite `memory.db`. Set `MEMORY_LAB_DATA` to isolate data for a test or separate demo.

## Tests

```powershell
python -m pytest
```
