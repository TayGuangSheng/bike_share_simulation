from fastapi import APIRouter, Depends, HTTPException, status

from ...api import deps
from ...schemas import RouteRequest, RouteResponse
from ...services.routing import RoutingService

router = APIRouter(prefix="/routes", tags=["routing"])


@router.post("", response_model=RouteResponse)
def compute_route(
    payload: RouteRequest,
    _user=Depends(deps.get_current_user),
) -> RouteResponse:
    graph_name = payload.graph or "toy"
    service = RoutingService(graph_name=graph_name)
    try:
        result = service.compute_route(
            start_lat=payload.from_location.lat,
            start_lon=payload.from_location.lon,
            end_lat=payload.to_location.lat,
            end_lon=payload.to_location.lon,
            variant=payload.variant,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return RouteResponse(
        polyline_geojson=result.polyline_geojson,
        total_distance_m=result.total_distance_m,
        est_time_s=result.est_time_s,
        nodes=result.nodes,
        start_node=result.start_node,
        end_node=result.end_node,
    )

