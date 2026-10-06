"""VLSM addressing calculations, generated with the standard ipaddress module."""

from ipaddress import ip_network

PLAN = [
    ("Check-in", 50, "172.16.0.0/26"),
    ("Cargo", 25, "172.16.0.64/27"),
    ("Airport Services", 10, "172.16.0.96/28"),
    ("Check-in ↔ Services", 2, "172.16.0.112/30"),
    ("Services ↔ Cargo", 2, "172.16.0.116/30"),
    ("Cargo ↔ Check-in", 2, "172.16.0.120/30"),
]


def addressing_plan():
    rows = []
    for name, required, cidr in PLAN:
        net = ip_network(cidr)
        hosts = list(net.hosts())
        rows.append({
            "name": name, "required": required, "subnet": cidr,
            "mask": str(net.netmask), "network": str(net.network_address),
            "broadcast": str(net.broadcast_address),
            "usable_range": f"{hosts[0]} – {hosts[-1]}",
            "usable_capacity": len(hosts), "allocated": net.num_addresses,
        })
    return rows


def validate_plan():
    networks = [ip_network(cidr) for _, _, cidr in PLAN]
    return all(not a.overlaps(b) for i, a in enumerate(networks) for b in networks[i + 1:])

