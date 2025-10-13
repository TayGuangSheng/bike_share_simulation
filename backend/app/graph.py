from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from .utils import haversine_m


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    lat: float
    lon: float


@dataclass(frozen=True)
class GraphEdgeData:
    to_node: str
    distance_m: float
    turn_penalty_s: float
    safe_score: float


class Graph:
    def __init__(self, nodes: Dict[str, GraphNode], adjacency: Dict[str, List[GraphEdgeData]]) -> None:
        self.nodes = nodes
        self.adjacency = adjacency

    @classmethod
    def from_json(cls, path: str | Path) -> "Graph":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes: Dict[str, GraphNode] = {}
        for node in data.get("nodes", []):
            nodes[node["id"]] = GraphNode(node_id=node["id"], lat=float(node["lat"]), lon=float(node["lon"]))
        adjacency: Dict[str, List[GraphEdgeData]] = {}
        for edge in data["edges"]:
            adjacency.setdefault(edge["from"], []).append(
                GraphEdgeData(
                    to_node=edge["to"],
                    distance_m=float(edge["distance_m"]),
                    turn_penalty_s=float(edge.get("turn_penalty_s", 0.0)),
                    safe_score=float(edge.get("safe_score", 1.0)),
                )
            )
        return cls(nodes=nodes, adjacency=adjacency)

    def nearest_node(self, lat: float, lon: float) -> GraphNode:
        best_node = None
        best_dist = float("inf")
        for node in self.nodes.values():
            dist = haversine_m(lat, lon, node.lat, node.lon)
            if dist < best_dist:
                best_node = node
                best_dist = dist
        if best_node is None:
            raise ValueError("Graph has no nodes")
        return best_node

    def dijkstra(self, src: str, dst: str, variant: str = "shortest", speed_mps: float = 4.0):
        import heapq

        dist: Dict[str, float] = {src: 0.0}
        prev: Dict[str, str] = {}
        pq: List[Tuple[float, str]] = [(0.0, src)]

        while pq:
            cost, node = heapq.heappop(pq)
            if node == dst:
                break
            if cost > dist.get(node, float("inf")):
                continue
            for edge in self.adjacency.get(node, []):
                edge_cost = edge.distance_m + edge.turn_penalty_s * speed_mps
                if variant == "safest":
                    risk_penalty = 1.0 + (1.0 / max(edge.safe_score, 1e-3))
                    edge_cost += edge.distance_m * 0.1 * risk_penalty
                tentative = cost + edge_cost
                if tentative < dist.get(edge.to_node, float("inf")):
                    dist[edge.to_node] = tentative
                    prev[edge.to_node] = node
                    heapq.heappush(pq, (tentative, edge.to_node))

        if dst not in dist:
            raise ValueError(f"No path between {src} and {dst}")

        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        path.reverse()

        total_distance = 0.0
        total_turn_penalty = 0.0
        for idx in range(len(path) - 1):
            u = path[idx]
            v = path[idx + 1]
            edge = next(e for e in self.adjacency[u] if e.to_node == v)
            total_distance += edge.distance_m
            total_turn_penalty += edge.turn_penalty_s

        est_time_s = total_distance / max(speed_mps, 0.1) + total_turn_penalty
        return path, total_distance, est_time_s

    def path_geojson(self, path: Iterable[str]) -> dict:
        coords = []
        for node_id in path:
            node = self.nodes.get(node_id)
            if node is None:
                raise ValueError(f"Unknown node {node_id}")
            coords.append([node.lon, node.lat])
        return {"type": "LineString", "coordinates": coords}


@lru_cache(maxsize=8)
def load_graph(name: str, base_dir: str) -> Graph:
    path = Path(base_dir) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Graph {name} not found at {path}")
    return Graph.from_json(path)
