# MQTT contract (draft, to lock with Squads A and C)

| Topic | Publisher | QoS / rate | Schema |
| --- | --- | --- | --- |
| `catarman/int01/vision/heartbeat` | Squad B | QoS 0, 2 Hz | `heartbeat.schema.json` |
| `catarman/int01/vision/density` | Squad B | QoS 0, 1 Hz | `density.schema.json` |
| `catarman/int01/vision/violation` | Squad B | QoS 1, on event | `violation.schema.json` |
| `catarman/int01/vision/status` | Squad B | QoS 1, retained; Last Will = `OFFLINE` | plain text `ONLINE` / `OFFLINE` |
| `catarman/int01/controller/state` | Squad A | QoS 0, on change + 1 Hz | `{ts, phase: "NS"|"EW", mode: "L1".."L4", fault, remaining_s, uptime_ms}` (Squad A to write the schema) |
| `catarman/int01/latency/ping` / `pong` | test harness | QoS 0 | `{seq, t_send}` |

Rules
- Timestamps are UTC ISO 8601. The dashboard converts to Asia/Manila.
- Opposite approaches share a phase: NS = N + S, EW = E + W.
- Any change to a schema needs agreement from all three squad leads, then a commit here.
