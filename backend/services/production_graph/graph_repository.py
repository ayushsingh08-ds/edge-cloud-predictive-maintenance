"""Repository layer for production line graph persistence."""

from __future__ import annotations

from sqlalchemy import select

from database.db_session import SessionLocal
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode
from database.models.route import Route


ALLOWED_NODE_TYPES = {"machine", "conveyor", "buffer", "storage"}


def _node_to_dict(node: ProductionNode) -> dict:
    return {
        "id": node.id,
        "node_name": node.node_name,
        "node_type": node.node_type,
        "machine_id": node.machine_id,
        "position_x": node.position_x,
        "position_y": node.position_y,
    }


def _edge_to_dict(edge: ProductionEdge) -> dict:
    return {
        "id": edge.id,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "distance": edge.distance,
        "travel_time": edge.travel_time,
        "capacity": edge.capacity,
    }


def _route_to_dict(route: Route) -> dict:
    return {
        "id": route.id,
        "route_name": route.route_name,
        "start_node_id": route.start_node_id,
        "end_node_id": route.end_node_id,
    }


def create_node(node_name: str, node_type: str, machine_id: int | None) -> dict:
    normalized_type = node_type.strip().lower()
    if normalized_type not in ALLOWED_NODE_TYPES:
        raise ValueError(f"Invalid node_type: {node_type}")

    db = SessionLocal()
    try:
        node = ProductionNode(
            node_name=node_name,
            node_type=normalized_type,
            machine_id=machine_id,
            position_x=0.0,
            position_y=0.0,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        return _node_to_dict(node)
    finally:
        db.close()


def get_node(node_id: int) -> dict | None:
    db = SessionLocal()
    try:
        node = db.scalar(select(ProductionNode).where(ProductionNode.id == node_id))
        if node is None:
            return None
        return _node_to_dict(node)
    finally:
        db.close()


def get_all_nodes() -> list[dict]:
    db = SessionLocal()
    try:
        nodes = db.scalars(select(ProductionNode).order_by(ProductionNode.id.asc())).all()
        return [_node_to_dict(node) for node in nodes]
    finally:
        db.close()


def create_edge(
    from_node_id: int,
    to_node_id: int,
    distance: float,
    travel_time: float,
) -> dict:
    if from_node_id == to_node_id:
        raise ValueError("A node cannot connect to itself")

    db = SessionLocal()
    try:
        from_node = db.scalar(select(ProductionNode).where(ProductionNode.id == from_node_id))
        to_node = db.scalar(select(ProductionNode).where(ProductionNode.id == to_node_id))
        if from_node is None or to_node is None:
            raise ValueError("Both nodes must exist before creating an edge")

        existing = db.scalar(
            select(ProductionEdge).where(
                ProductionEdge.from_node_id == from_node_id,
                ProductionEdge.to_node_id == to_node_id,
            )
        )
        if existing is not None:
            return _edge_to_dict(existing)

        edge = ProductionEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            distance=distance,
            travel_time=travel_time,
            capacity=1.0,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        return _edge_to_dict(edge)
    finally:
        db.close()


def get_edges() -> list[dict]:
    db = SessionLocal()
    try:
        edges = db.scalars(select(ProductionEdge).order_by(ProductionEdge.id.asc())).all()
        return [_edge_to_dict(edge) for edge in edges]
    finally:
        db.close()


def get_neighbors(node_id: int) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(ProductionEdge).where(ProductionEdge.from_node_id == node_id)
        ).all()

        neighbors: list[dict] = []
        for edge in rows:
            neighbor = db.scalar(select(ProductionNode).where(ProductionNode.id == edge.to_node_id))
            if neighbor is None:
                continue
            neighbors.append(
                {
                    "edge": _edge_to_dict(edge),
                    "node": _node_to_dict(neighbor),
                }
            )

        return neighbors
    finally:
        db.close()


def create_route(route_name: str, start_node_id: int, end_node_id: int) -> dict:
    db = SessionLocal()
    try:
        start_node = db.scalar(select(ProductionNode).where(ProductionNode.id == start_node_id))
        end_node = db.scalar(select(ProductionNode).where(ProductionNode.id == end_node_id))
        if start_node is None or end_node is None:
            raise ValueError("Both start and end nodes must exist before creating a route")

        route = Route(
            route_name=route_name,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
        )
        db.add(route)
        db.commit()
        db.refresh(route)
        return _route_to_dict(route)
    finally:
        db.close()


def get_routes() -> list[dict]:
    db = SessionLocal()
    try:
        routes = db.scalars(select(Route).order_by(Route.id.asc())).all()
        return [_route_to_dict(route) for route in routes]
    finally:
        db.close()


def get_route(route_id: int) -> dict | None:
    db = SessionLocal()
    try:
        route = db.scalar(select(Route).where(Route.id == route_id))
        if route is None:
            return None
        return _route_to_dict(route)
    finally:
        db.close()


def get_node_by_machine_id(machine_id: int) -> dict | None:
    db = SessionLocal()
    try:
        node = db.scalar(
            select(ProductionNode)
            .where(ProductionNode.machine_id == machine_id)
            .where(ProductionNode.node_type == "machine")
            .order_by(ProductionNode.id.asc())
            .limit(1)
        )
        if node is None:
            return None
        return _node_to_dict(node)
    finally:
        db.close()
