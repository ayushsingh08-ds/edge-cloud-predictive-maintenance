"""Digital Twin Layout graph system endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.schemas.dependencies import get_db
from sqlalchemy.orm import Session
from typing import Generator, Any

def get_db() -> Generator[Session, None, None]:
    from api.schemas.dependencies import get_db as original_get_db
    yield from original_get_db()
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/layout", tags=["layout"])

class WaypointConnectionSchema(BaseModel):
    target_id: str
    waypoints: list[dict[str, float]] = []

class LayoutNodeSchema(BaseModel):
    id: str  # Can be integer string like '1' or transient like 'new_123'
    name: str
    type: str
    position_x: float
    position_y: float
    connections: list[WaypointConnectionSchema] = []
    connected_to_ids: list[str] = [] # Fallback


class LayoutSaveRequest(BaseModel):
    nodes: list[LayoutNodeSchema]


@router.get("/")
def get_layout(db: Session = Depends(get_db)) -> dict:
    """Returns the comprehensive graph representation of the factory floor."""
    nodes = db.scalars(select(ProductionNode)).all()
    edges = db.scalars(select(ProductionEdge)).all()
    
    node_list = []
    for node in nodes:
        connected = []
        for e in edges:
            if e.from_node_id == node.id:
                 connected.append({
                     "target_id": str(e.to_node_id),
                     "waypoints": e.waypoints if e.waypoints else []
                 })
        
        node_list.append({
            "id": str(node.id),
            "name": node.node_name,
            "type": node.node_type,
            "position_x": node.position_x,
            "position_y": node.position_y,
            "connections": connected,
            "status": "Idle" # Default required by UI payload struct
        })
        
    return {"nodes": node_list}


@router.post("/save")
def save_layout(request: LayoutSaveRequest, db: Session = Depends(get_db)) -> dict:
    """Receives a complete snapshot of the workspace canvas and syncs the DB."""
    try:
        id_map: dict[str, int] = {}
        
        # 1. Upsert nodes
        for req_node in request.nodes:
            if req_node.id.startswith("new_"):
                # Create brand new structural node
                new_node = ProductionNode(
                    node_name=req_node.name,
                    node_type=req_node.type,
                    position_x=req_node.position_x,
                    position_y=req_node.position_y
                )
                db.add(new_node)
                db.flush() # Force ID generation
                id_map[req_node.id] = new_node.id
            else:
                # Update existing 
                node_id = int(req_node.id)
                id_map[req_node.id] = node_id
                
                db_node = db.scalar(select(ProductionNode).where(ProductionNode.id == node_id))
                if db_node:
                    db_node.position_x = req_node.position_x
                    db_node.position_y = req_node.position_y
                    db_node.node_name = req_node.name
                    
        # Delete nodes that have been removed from the canvas
        valid_ids = list(id_map.values())
        if valid_ids:
            db.execute(delete(ProductionNode).where(ProductionNode.id.notin_(valid_ids)))
        else:
            # If valid_ids is empty, it means all nodes were deleted
            db.execute(delete(ProductionNode))

        # Flush node updates
        db.flush()
        
        from services.simulation.simulation_manager import simulation_manager
        if simulation_manager.is_running:
            for internal_id in id_map.values():
                simulation_manager.start_machine_sensor(str(internal_id))
        
        # 2. Re-create Edges (Conveyors) 
        # Safest graph reconciliation: Delete all existing edges and rebuild from UI source truth
        db.execute(delete(ProductionEdge))
        
        for req_node in request.nodes:
            from_internal_id = id_map.get(req_node.id)
            if not from_internal_id:
                continue
            
            # Use new connections or fallback
            if req_node.connections:
                for conn in req_node.connections:
                    to_internal_id = id_map.get(conn.target_id)
                    if to_internal_id:
                        new_edge = ProductionEdge(
                            from_node_id=from_internal_id,
                            to_node_id=to_internal_id,
                            distance=10.0,
                            travel_time=1.0,
                            capacity=100.0,
                            waypoints=conn.waypoints
                        )
                        db.add(new_edge)
            else:
                # Fallback to connected_to_ids for backward compat
                for target_ui_id in req_node.connected_to_ids:
                    to_internal_id = id_map.get(target_ui_id)
                    if to_internal_id:
                        new_edge = ProductionEdge(
                            from_node_id=from_internal_id,
                            to_node_id=to_internal_id,
                            distance=10.0,
                            travel_time=1.0,
                            capacity=100.0,
                            waypoints=[]
                        )
                        db.add(new_edge)
                    
        db.commit()
        return {"status": "success", "message": f"Successfully mapped {len(request.nodes)} nodes."}
        
    except Exception as e:
        db.rollback()
        logger.exception("Failed to save layout")
        raise HTTPException(status_code=500, detail=str(e))
