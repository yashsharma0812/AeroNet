"""Static device and link definitions for the airport topology."""

DEVICES = {
    "R-CHECKIN": {"name": "Check-in Router", "type": "router", "zone": "Check-in", "area": 0, "lan_ip": "172.16.0.1"},
    "R-CARGO": {"name": "Cargo Router", "type": "router", "zone": "Cargo", "area": 0, "lan_ip": "172.16.0.65"},
    "R-SERVICES": {"name": "Services Router", "type": "router", "zone": "Airport Services", "area": 0, "lan_ip": "172.16.0.97"},
    "SW-CHECKIN": {"name": "Check-in Switch", "type": "switch", "zone": "Check-in"},
    "SW-CARGO": {"name": "Cargo Switch", "type": "switch", "zone": "Cargo"},
    "SW-SERVICES": {"name": "Services Switch", "type": "switch", "zone": "Airport Services"},
    "PC-CHECKIN-1": {"name": "Check-in PC 1", "type": "pc", "zone": "Check-in", "ip": "172.16.0.2", "gateway": "172.16.0.1"},
    "PC-CHECKIN-2": {"name": "Check-in PC 2", "type": "pc", "zone": "Check-in", "ip": "172.16.0.3", "gateway": "172.16.0.1"},
    "PC-CARGO-1": {"name": "Cargo PC 1", "type": "pc", "zone": "Cargo", "ip": "172.16.0.66", "gateway": "172.16.0.65"},
    "PC-CARGO-2": {"name": "Cargo PC 2", "type": "pc", "zone": "Cargo", "ip": "172.16.0.67", "gateway": "172.16.0.65"},
    "HTTP-SERVER": {"name": "Flight Information Server", "type": "server", "zone": "Airport Services", "ip": "172.16.0.98", "gateway": "172.16.0.97"},
}

LINK_DEFINITIONS = {
    "checkin-services": {
        "name": "Check-in ↔ Services", "a": "R-CHECKIN", "b": "R-SERVICES",
        "interfaces": {"R-CHECKIN": "S0/0/0", "R-SERVICES": "S0/0/0"},
        "addresses": {"R-CHECKIN": "172.16.0.113", "R-SERVICES": "172.16.0.114"},
        "subnet": "172.16.0.112/30",
    },
    "services-cargo": {
        "name": "Services ↔ Cargo", "a": "R-SERVICES", "b": "R-CARGO",
        "interfaces": {"R-SERVICES": "S0/0/1", "R-CARGO": "S0/0/0"},
        "addresses": {"R-SERVICES": "172.16.0.117", "R-CARGO": "172.16.0.118"},
        "subnet": "172.16.0.116/30",
    },
    "cargo-checkin": {
        "name": "Cargo ↔ Check-in", "a": "R-CARGO", "b": "R-CHECKIN",
        "interfaces": {"R-CARGO": "S0/0/1", "R-CHECKIN": "S0/0/1"},
        "addresses": {"R-CARGO": "172.16.0.121", "R-CHECKIN": "172.16.0.122"},
        "subnet": "172.16.0.120/30",
    },
}

SOURCE_PCS = ["PC-CHECKIN-1", "PC-CHECKIN-2", "PC-CARGO-1", "PC-CARGO-2"]
ZONE_ROUTERS = {"Check-in": "R-CHECKIN", "Cargo": "R-CARGO", "Airport Services": "R-SERVICES"}
LAN_SUBNETS = {"R-CHECKIN": "172.16.0.0/26", "R-CARGO": "172.16.0.64/27", "R-SERVICES": "172.16.0.96/28"}

