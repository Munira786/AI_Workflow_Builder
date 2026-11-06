from collections import deque

from app.schemas import Graph


def topological_order(graph: Graph) -> list[str] | None:
    """Return node ids in execution order (Kahn's algorithm), or None if the graph has a cycle.

    Assumes the graph has already been validated (every edge points at a known node).
    """
    adjacency: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    indegree: dict[str, int] = {node.id: 0 for node in graph.nodes}

    for edge in graph.edges:
        adjacency[edge.source].append(edge.target)
        indegree[edge.target] += 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in adjacency[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == len(graph.nodes) else None


def is_dag(graph: Graph) -> bool:
    return topological_order(graph) is not None
