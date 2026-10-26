"""Traffic logic: PCU scores, density message, red-light check."""

CLASSES = ("tricycle", "motorcycle", "car")


def pcu_score(counts, weights):
    return round(sum(weights[c] * n for c, n in counts.items()), 2)


def build_density(ts, seq, counts_by_approach, weights, phases):
    """counts_by_approach = {"N": {"tricycle": 1, "motorcycle": 0, "car": 2}, ...}"""
    approaches = {}
    for a, counts in counts_by_approach.items():
        full = {c: int(counts.get(c, 0)) for c in CLASSES}
        approaches[a] = {"counts": full, "pcu": pcu_score(full, weights)}
    phase_pcu = {p: round(sum(approaches[a]["pcu"] for a in members), 2)
                 for p, members in phases.items()}
    return {"ts": ts, "seq": seq, "approaches": approaches, "phases": phase_pcu}


def phase_of(approach, phases):
    for p, members in phases.items():
        if approach in members:
            return p
    return None


def is_red(approach, phases, state, now, stale_s):
    """True / False, or None when we must NOT judge violations.

    None if: no controller state yet, state is stale, flood mode (L4), or a fault.
    Contract: state["phase"] is the phase that currently has right of way.
    TODO (Squad A): add an "amber": true flag so amber is excluded too.
    """
    if not state or now - state.get("_rx", 0) > stale_s:
        return None
    if state.get("mode") == "L4" or state.get("fault") or state.get("amber"):
        return None
    green = state.get("phase")
    if green is None:
        return None
    return phase_of(approach, phases) != green
