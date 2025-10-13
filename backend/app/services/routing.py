from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from ..graph import Graph, load_graph


@dataclass
class RouteResult:
    polyline_geojson: dict
    total_distance_m: float
    est_time_s: float
    nodes: list[str]
    start_node: str
    end_node: str


class RoutingService:
    def __init__(self, graph_name: str | None = None) -> None:
        self.graph_name = graph_name or settings.default_graph_name

    def _resolve_graph(self) -> Graph:
        return load_graph(self.graph_name, settings.graphs_dir)

    def compute_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        variant: str,
    ) -> RouteResult:
        graph = self._resolve_graph()
        src_node = graph.nearest_node(start_lat, start_lon)
        dst_node = graph.nearest_node(end_lat, end_lon)
        nodes, distance, est_time = graph.dijkstra(
            src_node.node_id,
            dst_node.node_id,
            variant=variant,
            speed_mps=settings.default_speed_mps,
        )
        polyline = graph.path_geojson(nodes)
        return RouteResult(
            polyline_geojson=polyline,
            total_distance_m=distance,
            est_time_s=est_time,
            nodes=nodes,
            start_node=src_node.node_id,
            end_node=dst_node.node_id,
        )

