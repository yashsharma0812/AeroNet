# AeroNet — Resilient Airport Network Simulator

AeroNet is a local educational web application for **21CSC302J Computer Networks**. It visualizes a small airport network and makes routing and configuration changes observable without claiming to emulate production network equipment.

## Five-unit mapping

| Unit | Topic | AeroNet feature |
|---|---|---|
| 1 | Hybrid network topology | Interactive SVG with 3 routers, 3 switches, 4 PCs, and 1 server |
| 2 | VLSM addressing | Python-generated subnet table and LAN allocation comparison |
| 3 | Single-area OSPF | Area 0 labeling and Dijkstra-based, OSPF-inspired route selection |
| 4 | PPP | Per-endpoint PPP/HDLC configuration and mismatch demonstration |
| 5 | HTTP | Real Flask flight portal plus simulated topology delivery |

## Setup and run

Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
flask --app app run --debug
```

Open `http://127.0.0.1:5000`. The real local flight portal is at `http://127.0.0.1:5000/flights`.

## Architecture

```text
app.py                    Flask pages and JSON API
simulator/
  addressing.py           ipaddress-based VLSM calculations
  routing.py              deterministic Dijkstra algorithm
  state.py                authoritative in-memory state and event log
  topology.py             devices, links, interfaces, and addresses
templates/                dashboard and flight portal
static/css/styles.css     responsive visual system
static/js/app.js          API client, rendering, and packet playback
tests/test_simulator.py   backend and endpoint verification
```

The backend is authoritative for topology state, link operation, route selection, and request results. JavaScript renders backend results and animates the returned device path; it does not calculate routes.

## Addressing plan

| Zone/link | Required usable | Subnet | Interface assignment |
|---|---:|---|---|
| Check-in LAN | 50 | `172.16.0.0/26` | gateway `.1`, PCs `.2` and `.3` |
| Cargo LAN | 25 | `172.16.0.64/27` | gateway `.65`, PCs `.66` and `.67` |
| Airport Services LAN | 10 | `172.16.0.96/28` | gateway `.97`, HTTP server `.98` |
| Check-in ↔ Services | 2 | `172.16.0.112/30` | Check-in `.113`, Services `.114` |
| Services ↔ Cargo | 2 | `172.16.0.116/30` | Services `.117`, Cargo `.118` |
| Cargo ↔ Check-in | 2 | `172.16.0.120/30` | Cargo `.121`, Check-in `.122` |

For the three LANs only, VLSM allocates `64 + 32 + 16 = 112` total addresses. An FLSM `/26` baseline allocates `3 × 64 = 192`, a **41.7% reduction**. These are allocated address counts, including network and broadcast addresses; usable-host capacity is shown separately in the application.

## Presentation / demo script

1. Inspect the hybrid topology and its exactly 11 devices.
2. Open Addressing and explain the VLSM plan and 41.7% LAN address saving.
3. Send a request through the direct Check-in → Services route (cost 10).
4. Select that serial link and disable it; show the alternative through Cargo (cost 20).
5. Send another successful simulated request over the alternative route.
6. In PPP, create an endpoint encapsulation mismatch and then repair it.
7. Disable both links leaving Check-in and demonstrate an unreachable request.
8. Reset the demo and confirm the initial route and settings return.

## What is real and what is simulated

Flask serves a real HTTP page at `/flights` with fictional sample flight data. `172.16.0.98` is the server's **simulated** network address; opening the local Flask URL does not make the browser traverse the simulated routers. The **Send HTTP Request** button separately asks the backend to model delivery through the topology. A simulated link failure does not stop the actual Flask process.

Routing is **OSPF-inspired shortest-path selection**, not real OSPF. PPP/HDLC settings model endpoint compatibility, not negotiation or frame transmission. Link costs are configurable educational values—not measured latency or bandwidth.

## State and limitations

- State is in memory, shared by all browser tabs using the same Flask process, and reset when the process restarts.
- The event log is bounded to 100 entries.
- There are no OSPF neighbor exchanges, LSAs, timers, convergence measurements, ECMP, authentication, databases, external APIs, or packet-level PPP internals.
- Matching HDLC is allowed only to demonstrate that endpoint encapsulation must agree; HDLC is not implemented as an additional module.

## Tests

```bash
pytest -q
```

The suite covers direct, alternate, unreachable, mismatch, restoration, cost-change and reset behavior; addressing validity; API validation; animation-path output; and the real `/flights` endpoint.
