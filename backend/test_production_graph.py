"""Integration-style test for Production Line Graph service.

Validates node/edge/route persistence and graph traversal for a factory layout.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete

from database.db_session import SessionLocal
from database.init_db import init_db
from database.models.machine import Machine
from database.models.production_edge import ProductionEdge
from database.models.production_node import ProductionNode
from database.models.route import Route
from services.production_graph.graph_service import ProductionGraphService
from services.production_graph import graph_repository


def print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_production_graph_test() -> None:
    print_header("Production Graph Test Started")

    print("[1/10] Initializing database schema...")
    init_db()

    db = SessionLocal()
    service = ProductionGraphService()

    try:
        print("[2/10] Resetting production graph tables for deterministic test run...")
        db.execute(delete(Route))
        db.execute(delete(ProductionEdge))
        db.execute(delete(ProductionNode))
        db.commit()

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        print("[3/10] Creating machine records (required for machine node foreign keys)...")
        machine_a = Machine(
            name=f"Machine A - PG Test {timestamp}",
            type="CNC",
            location="Line 1 - Station A",
            status="running",
        )
        machine_b = Machine(
            name=f"Machine B - PG Test {timestamp}",
            type="Assembler",
            location="Line 1 - Station B",
            status="running",
        )
        machine_c = Machine(
            name=f"Machine C - PG Test {timestamp}",
            type="Inspection",
            location="Line 1 - Station C",
            status="running",
        )
        db.add_all([machine_a, machine_b, machine_c])
        db.commit()
        db.refresh(machine_a)
        db.refresh(machine_b)
        db.refresh(machine_c)

        print("[4/10] Creating production nodes...")
        node_machine_a = service.add_machine_node(machine_a.id, "Machine A")
        node_conveyor_1 = service.add_conveyor_node("Conveyor 1")
        node_machine_b = service.add_machine_node(machine_b.id, "Machine B")
        node_machine_c = service.add_machine_node(machine_c.id, "Machine C")

        print("\nNodes Created:")
        print(node_machine_a["node_name"])
        print(node_conveyor_1["node_name"])
        print(node_machine_b["node_name"])
        print(node_machine_c["node_name"])

        print("[5/10] Connecting nodes using edges...")
        edge_1 = service.connect_nodes(node_machine_a["id"], node_conveyor_1["id"])
        edge_2 = service.connect_nodes(node_conveyor_1["id"], node_machine_b["id"])
        edge_3 = service.connect_nodes(node_machine_b["id"], node_machine_c["id"])

        print("\nEdges Created:")
        print("Machine A -> Conveyor 1")
        print("Conveyor 1 -> Machine B")
        print("Machine B -> Machine C")

        print("[6/10] Creating production route...")
        route = graph_repository.create_route(
            route_name="Route 1",
            start_node_id=node_machine_a["id"],
            end_node_id=node_machine_c["id"],
        )

        print("\nRoute Created:")
        print("Route 1: Machine A -> Machine C")

        print("[7/10] Querying all nodes and edges...")
        all_nodes = graph_repository.get_all_nodes()
        all_edges = graph_repository.get_edges()

        _ensure(len(all_nodes) >= 4, "Expected at least 4 nodes")
        _ensure(len(all_edges) >= 3, "Expected at least 3 edges")

        print("\nAll Nodes:")
        for node in all_nodes:
            print(
                f"id={node['id']} name={node['node_name']} "
                f"type={node['node_type']} machine_id={node['machine_id']}"
            )

        print("\nAll Edges:")
        for edge in all_edges:
            print(
                f"id={edge['id']} from={edge['from_node_id']} "
                f"to={edge['to_node_id']} distance={edge['distance']} "
                f"travel_time={edge['travel_time']}"
            )

        print("[8/10] Getting neighbors for Machine A and finding path to Machine C...")
        neighbors = service.get_next_nodes(node_machine_a["id"])
        _ensure(len(neighbors) >= 1, "Machine A should have at least one neighbor")

        print("\nNeighbors of Machine A:")
        for item in neighbors:
            print(item["node"]["node_name"])

        path_node_ids = service.find_path(node_machine_a["id"], node_machine_c["id"])
        _ensure(path_node_ids, "Path from Machine A to Machine C should not be empty")

        node_name_by_id = {node["id"]: node["node_name"] for node in all_nodes}
        path_names = [node_name_by_id.get(node_id, str(node_id)) for node_id in path_node_ids]

        print("\nPath from Machine A to Machine C:")
        print(" -> ".join(path_names))

        expected_path = ["Machine A", "Conveyor 1", "Machine B", "Machine C"]
        _ensure(path_names == expected_path, f"Unexpected path: {path_names}")

        print("[9/10] Printing factory graph structure and route info...")
        graph = service.get_factory_graph()

        print("\nFactory Graph:")
        for edge in graph["edges"]:
            from_name = node_name_by_id.get(edge["from_node_id"], str(edge["from_node_id"]))
            to_name = node_name_by_id.get(edge["to_node_id"], str(edge["to_node_id"]))
            print(f"{from_name} -> {to_name}")

        route_info = graph_repository.get_route(route["id"])
        _ensure(route_info is not None, "Route should exist")
        _ensure(route_info["start_node_id"] == node_machine_a["id"], "Route start node mismatch")
        _ensure(route_info["end_node_id"] == node_machine_c["id"], "Route end node mismatch")

        print("\nRoute Information:")
        print(
            f"id={route_info['id']} name={route_info['route_name']} "
            f"start={node_name_by_id.get(route_info['start_node_id'])} "
            f"end={node_name_by_id.get(route_info['end_node_id'])}"
        )

        print("[10/10] Verifying core goals...")
        _ensure(any(node["node_name"] == "Machine A" for node in all_nodes), "Machine A node not found")
        _ensure(any(node["node_name"] == "Conveyor 1" for node in all_nodes), "Conveyor 1 node not found")
        _ensure(any(edge["id"] == edge_1["id"] for edge in all_edges), "Edge 1 not stored")
        _ensure(any(edge["id"] == edge_2["id"] for edge in all_edges), "Edge 2 not stored")
        _ensure(any(edge["id"] == edge_3["id"] for edge in all_edges), "Edge 3 not stored")
        _ensure(route_info["route_name"] == "Route 1", "Route not stored correctly")
        _ensure(len(graph["nodes"]) >= 4, "Graph nodes missing")
        _ensure(len(graph["edges"]) >= 3, "Graph edges missing")
        _ensure(len(graph["routes"]) >= 1, "Graph routes missing")

        print("\nProduction Line Graph Test Completed Successfully.")

    except Exception as exc:
        db.rollback()
        print_header("TEST FAILED")
        print(f"Error: {exc}")
        raise
    finally:
        db.close()
        print("\nDatabase session closed.")


if __name__ == "__main__":
    run_production_graph_test()
