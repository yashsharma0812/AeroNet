"""Authoritative, in-memory AeroNet simulation state."""

from copy import deepcopy
from datetime import datetime
from threading import RLock

from .addressing import addressing_plan
from .flights import FLIGHTS
from .routing import shortest_path
from .topology import DEVICES, LAN_SUBNETS, LINK_DEFINITIONS, SOURCE_PCS, ZONE_ROUTERS

MAX_COST = 10000


class ValidationError(ValueError):
    pass


class NetworkState:
    def __init__(self):
        self._lock = RLock()
        self.reset(initial=True)

    def _now(self):
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _log(self, event_type, message, **details):
        self.events.append({"timestamp": self._now(), "type": event_type, "message": message, "details": details})
        self.events = self.events[-100:]

    @staticmethod
    def _effective(link):
        if not link["admin_up"]:
            return False, "Administratively disabled"
        values = set(link["encapsulation"].values())
        if len(values) != 1:
            return False, "Encapsulation mismatch"
        mode = next(iter(values))
        return True, f"Operational with {mode}"

    def _refresh_link(self, link):
        link["operational"], link["status_reason"] = self._effective(link)

    def _route_for_pc(self, pc_id):
        source_router = ZONE_ROUTERS[DEVICES[pc_id]["zone"]]
        path, cost = shortest_path(self.links, source_router, "R-SERVICES")
        return {"source_pc": pc_id, "destination": "HTTP-SERVER", "reachable": path is not None,
                "router_path": path or [], "cost": cost}

    def reset(self, initial=False):
        with self._lock:
            self.links = {}
            for link_id, definition in LINK_DEFINITIONS.items():
                link = deepcopy(definition)
                link.update({"id": link_id, "admin_up": True, "cost": 10,
                             "encapsulation": {link["a"]: "PPP", link["b"]: "PPP"}})
                self._refresh_link(link)
                self.links[link_id] = link
            self.selected_pc = "PC-CHECKIN-1"
            self.last_request = None
            self.events = []
            self._log("reset", "Demo initialized" if initial else "Demo reset to default state")
            self._last_route = self._route_for_pc(self.selected_pc)
            return self.snapshot()

    def _record_route_change(self, before, after):
        signature_before = (before["reachable"], before["router_path"], before["cost"])
        signature_after = (after["reachable"], after["router_path"], after["cost"])
        if signature_before != signature_after:
            old = " → ".join(before["router_path"]) if before["reachable"] else "unreachable"
            new = " → ".join(after["router_path"]) if after["reachable"] else "unreachable"
            self._log("route", f"Selected route changed: {old} → {new}", before=before, after=after)

    def update_link(self, link_id, changes):
        with self._lock:
            if link_id not in self.links:
                raise ValidationError("Unknown link ID")
            allowed = {"admin_up", "cost", "encapsulation"}
            if not isinstance(changes, dict) or set(changes) - allowed:
                raise ValidationError("Only admin_up, cost, and encapsulation may be changed")
            link = self.links[link_id]
            # Validate the complete patch before changing anything, so rejected
            # compound requests cannot leave partially applied state behind.
            if "admin_up" in changes and not isinstance(changes["admin_up"], bool):
                raise ValidationError("admin_up must be a boolean")
            if "cost" in changes:
                cost = changes["cost"]
                if isinstance(cost, bool) or not isinstance(cost, int) or not 1 <= cost <= MAX_COST:
                    raise ValidationError(f"Cost must be an integer from 1 to {MAX_COST}")
            if "encapsulation" in changes:
                enc = changes["encapsulation"]
                if not isinstance(enc, dict) or not enc:
                    raise ValidationError("encapsulation must map link endpoint routers to PPP or HDLC")
                for router, value in enc.items():
                    if router not in (link["a"], link["b"]):
                        raise ValidationError("Encapsulation endpoint is not on this link")
                    if value not in ("PPP", "HDLC"):
                        raise ValidationError("Encapsulation must be PPP or HDLC")
            before_route = self._route_for_pc(self.selected_pc)
            old_operational = link["operational"]
            if "admin_up" in changes:
                if not isinstance(changes["admin_up"], bool):
                    raise ValidationError("admin_up must be a boolean")
                if link["admin_up"] != changes["admin_up"]:
                    old = link["admin_up"]
                    link["admin_up"] = changes["admin_up"]
                    self._log("link", f"{link['name']} {'enabled' if link['admin_up'] else 'disabled'}", before=old, after=link["admin_up"])
            if "cost" in changes:
                cost = changes["cost"]
                if isinstance(cost, bool) or not isinstance(cost, int) or not 1 <= cost <= MAX_COST:
                    raise ValidationError(f"Cost must be an integer from 1 to {MAX_COST}")
                if link["cost"] != cost:
                    old = link["cost"]
                    link["cost"] = cost
                    self._log("cost", f"{link['name']} cost changed from {old} to {cost}", before=old, after=cost)
            if "encapsulation" in changes:
                enc = changes["encapsulation"]
                if not isinstance(enc, dict) or not enc:
                    raise ValidationError("encapsulation must map link endpoint routers to PPP or HDLC")
                for router, value in enc.items():
                    if router not in (link["a"], link["b"]):
                        raise ValidationError("Encapsulation endpoint is not on this link")
                    if value not in ("PPP", "HDLC"):
                        raise ValidationError("Encapsulation must be PPP or HDLC")
                for router, value in enc.items():
                    if link["encapsulation"][router] != value:
                        old = link["encapsulation"][router]
                        link["encapsulation"][router] = value
                        self._log("encapsulation", f"{link['name']} {router}: {old} → {value}", router=router, before=old, after=value)
            self._refresh_link(link)
            if link["operational"] != old_operational:
                self._log("operational", f"{link['name']} is now {'operational' if link['operational'] else 'unavailable'}: {link['status_reason']}")
            after_route = self._route_for_pc(self.selected_pc)
            self._record_route_change(before_route, after_route)
            self._last_route = after_route
            return self.snapshot()

    def select_source(self, pc_id):
        with self._lock:
            if pc_id not in SOURCE_PCS:
                raise ValidationError("Source must be one of the four client PCs")
            before = self._route_for_pc(self.selected_pc)
            self.selected_pc = pc_id
            after = self._route_for_pc(pc_id)
            self._record_route_change(before, after)
            self._last_route = after
            return self.snapshot()

    def send_request(self, pc_id=None):
        with self._lock:
            if pc_id is not None:
                if pc_id not in SOURCE_PCS:
                    raise ValidationError("Source must be one of the four client PCs")
                self.selected_pc = pc_id
            route = self._route_for_pc(self.selected_pc)
            source = DEVICES[self.selected_pc]
            source_switch = "SW-CHECKIN" if source["zone"] == "Check-in" else "SW-CARGO"
            source_router = ZONE_ROUTERS[source["zone"]]
            playback_routers = route["router_path"] if route["reachable"] else [source_router]
            animation_path = [self.selected_pc, source_switch] + playback_routers
            if route["reachable"]:
                animation_path += ["SW-SERVICES", "HTTP-SERVER"]
            result = {**route, "animation_path": animation_path,
                      "flights": deepcopy(FLIGHTS) if route["reachable"] else [],
                      "message": "HTTP response delivered successfully" if route["reachable"] else "Destination unreachable in the simulated topology",
                      "timestamp": self._now()}
            self.last_request = result
            self._log("request", f"Simulated HTTP request {'delivered' if route['reachable'] else 'unreachable'}", route=route)
            return result

    def routing_tables(self):
        tables = {}
        for router in LAN_SUBNETS:
            rows = []
            for destination, subnet in LAN_SUBNETS.items():
                if destination == router:
                    continue
                path, cost = shortest_path(self.links, router, destination)
                next_router = path[1] if path else None
                next_hop = None
                if next_router:
                    for link in self.links.values():
                        if {link["a"], link["b"]} == {router, next_router}:
                            next_hop = link["addresses"][next_router]
                            break
                rows.append({"subnet": subnet, "destination_router": destination, "next_hop_router": next_router,
                             "next_hop_address": next_hop, "cost": cost, "reachable": path is not None})
            tables[router] = rows
        return tables

    def snapshot(self):
        route = self._route_for_pc(self.selected_pc)
        return {"devices": deepcopy(DEVICES), "links": deepcopy(self.links), "sources": SOURCE_PCS,
                "selected_pc": self.selected_pc, "route": route, "routing_tables": self.routing_tables(),
                "addressing": addressing_plan(), "last_request": deepcopy(self.last_request),
                "events": list(reversed(deepcopy(self.events))),
                "operational_links": sum(1 for link in self.links.values() if link["operational"]),
                "server_status": "HTTP service available locally"}
