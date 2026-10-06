"""Deterministic Dijkstra routing over operational inter-router links."""

import heapq


def shortest_path(links, source, destination):
    if source == destination:
        return [source], 0
    graph = {router: [] for router in ("R-CHECKIN", "R-CARGO", "R-SERVICES")}
    for link in links.values():
        if link["operational"]:
            graph[link["a"]].append((link["b"], link["cost"]))
            graph[link["b"]].append((link["a"], link["cost"]))
    # The path tuple makes equal-cost results deterministic and lexicographic.
    queue = [(0, (source,), source)]
    best = {source: (0, (source,))}
    while queue:
        cost, path_tuple, node = heapq.heappop(queue)
        if best.get(node) != (cost, path_tuple):
            continue
        if node == destination:
            return list(path_tuple), cost
        for neighbor, edge_cost in sorted(graph[node]):
            candidate = (cost + edge_cost, path_tuple + (neighbor,))
            if neighbor not in best or candidate < best[neighbor]:
                best[neighbor] = candidate
                heapq.heappush(queue, (candidate[0], candidate[1], neighbor))
    return None, None

