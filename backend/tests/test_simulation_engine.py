import pytest
import simpy
from events import EventBus
from layout import LayoutGraph, LayoutNode, LayoutNodeType, LayoutEdge, LayoutPosition
from simulation.engine import FactorySimulationEngine

def test_engine_buffer_flow_no_deadlock():
    """
    Test that a buffer correctly releases jobs when a downstream machine becomes available,
    even if it was initially unavailable.
    """
    # Create a simple layout: Source -> Buffer -> Machine -> Sink
    nodes = [
        LayoutNode(id="src", type=LayoutNodeType.SOURCE, position=LayoutPosition(0,0), properties={"interarrival_time": 0.1, "max_jobs": 5}),
        LayoutNode(id="buf", type=LayoutNodeType.BUFFER, position=LayoutPosition(100,0), properties={"capacity": 10}),
        LayoutNode(id="mac", type=LayoutNodeType.MACHINE, position=LayoutPosition(200,0), properties={"processing_time": 1.0}),
        LayoutNode(id="snk", type=LayoutNodeType.SINK, position=LayoutPosition(300,0), properties={})
    ]
    edges = [
        LayoutEdge(from_node="src", to_node="buf"),
        LayoutEdge(from_node="buf", to_node="mac"),
        LayoutEdge(from_node="mac", to_node="snk")
    ]
    graph = LayoutGraph(nodes=nodes, edges=edges)
    
    env = simpy.Environment()
    bus = EventBus(env)
    engine = FactorySimulationEngine(layout_graph=graph, environment=env, event_bus=bus)
    
    # Run simulation for a bit
    # The source emits jobs every 0.1s. The machine takes 1.0s.
    # After 10s, the machine should have processed some jobs.
    engine.run(until=10.0)
    
    assert len(engine.completed_jobs) > 0
    print(f"Completed jobs: {len(engine.completed_jobs)}")

def test_engine_available_edge_recheck():
    """
    Specifically tests that the engine re-evaluates edge availability.
    We'll mock some parts or use a layout that forces a wait.
    """
    # Source -> Buffer -> Machine
    # Machine is slow, Buffer will fill up.
    nodes = [
        LayoutNode(id="s", type=LayoutNodeType.SOURCE, position=LayoutPosition(0,0), properties={"interarrival_time": 0.5, "max_jobs": 2}),
        LayoutNode(id="b", type=LayoutNodeType.BUFFER, position=LayoutPosition(100,0), properties={"capacity": 5}),
        LayoutNode(id="m", type=LayoutNodeType.MACHINE, position=LayoutPosition(200,0), properties={"processing_time": 5.0}),
        LayoutNode(id="sink", type=LayoutNodeType.SINK, position=LayoutPosition(300,0), properties={})
    ]
    edges = [
        LayoutEdge(from_node="s", to_node="b"),
        LayoutEdge(from_node="b", to_node="m"),
        LayoutEdge(from_node="m", to_node="sink")
    ]
    graph = LayoutGraph(nodes=nodes, edges=edges)
    
    env = simpy.Environment()
    bus = EventBus(env)
    engine = FactorySimulationEngine(layout_graph=graph, environment=env, event_bus=bus)
    
    # Run long enough for machine to process at least one job
    engine.run(until=15.0)
    
    # If it was deadlocked, it would have 0 or 1 jobs (the first one might go through if mac was IDLE)
    # The second job must wait in buffer until machine is IDLE again.
    assert len(engine.completed_jobs) >= 2
