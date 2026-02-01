from __future__ import annotations

from dataclasses import dataclass

from config import DEFAULT_CONFIG


@dataclass
class Decision:
    state: str
    reason_codes: list[str]


def decide(leader: str, current_asset: str, edge: float, net_edge: float) -> Decision:
    reason_codes: list[str] = []
    if leader == current_asset:
        reason_codes.append("LEADER_IS_CURRENT")
    if edge < DEFAULT_CONFIG.edge_threshold:
        reason_codes.append("EDGE_TOO_SMALL")
    if net_edge < DEFAULT_CONFIG.net_edge_min:
        reason_codes.append("NET_EDGE_TOO_SMALL")

    if leader != current_asset and edge >= DEFAULT_CONFIG.edge_threshold and net_edge >= DEFAULT_CONFIG.net_edge_min:
        return Decision(state="READY_TO_SWITCH", reason_codes=[])

    return Decision(state="HOLD", reason_codes=reason_codes)
