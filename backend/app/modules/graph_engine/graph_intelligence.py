from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import networkx as nx
import numpy as np

from backend.app.models import Customer, Order, ReturnRecord
from backend.app.ml.graph_features import (
    build_fraud_graph as _build_base_graph,
    extract_graph_features as _extract_base_features,
    FraudGraph as BaseFraudGraph,
    _customer_node, _address_node, _device_node,
    _neighbors,
)


@dataclass
class EnhancedGraphFeatures:
    graph: nx.Graph
    customer_to_node: dict[UUID, str]
    return_to_node: dict[UUID, str]
    confirmed_fraud_customers: set[UUID]


def build_enhanced_fraud_graph(
    customers: list[Customer],
    orders: list[Order],
    returns: list[ReturnRecord],
    confirmed_fraud_set: set[UUID] | None = None,
) -> EnhancedGraphFeatures:
    base = _build_base_graph(customers, orders, returns)
    base.confirmed_fraud_customers = confirmed_fraud_set or _detect_confirmed_fraud(base)
    _add_ip_nodes(base, customers)
    _add_courier_nodes(base, orders, returns)
    return EnhancedGraphFeatures(
        graph=base.graph,
        customer_to_node=base.customer_to_node,
        return_to_node=base.return_to_node,
        confirmed_fraud_customers=base.confirmed_fraud_customers,
    )


def _detect_confirmed_fraud(graph: BaseFraudGraph) -> set[UUID]:
    confirmed = set(graph.confirmed_fraud_customers)
    for customer_id, node in graph.customer_to_node.items():
        if node in graph.graph:
            neighbors = _neighbors(graph.graph, node)
            if any(n in confirmed for n in neighbors):
                continue
    return confirmed


def _add_ip_nodes(graph: BaseFraudGraph, customers: list[Customer]) -> None:
    pass


def _add_courier_nodes(graph: BaseFraudGraph, orders: list[Order], returns: list[ReturnRecord]) -> None:
    pass


def extract_enhanced_graph_features(
    graph_features: EnhancedGraphFeatures,
    customer_id: UUID,
    return_id: UUID,
) -> dict[str, Any]:
    g = graph_features.graph
    customer_node = graph_features.customer_to_node.get(customer_id, "")
    if not customer_node or not g.has_node(customer_node):
        return _empty_features()

    component = set(nx.node_connected_component(g, customer_node)) if g.has_node(customer_node) else {customer_node}
    customer_nodes_in_component = {n for n in component if str(n).startswith("customer:")}
    connected_customers = customer_nodes_in_component - {customer_node}
    connected_customers_count = len(connected_customers)

    confirmed_fraud_nodes = {graph_features.customer_to_node[c] for c in graph_features.confirmed_fraud_customers if c in graph_features.customer_to_node}
    fraud_neighbor_count = len(connected_customers & confirmed_fraud_nodes)
    component_size = len(customer_nodes_in_component)
    fraud_ratio = round(fraud_neighbor_count / max(connected_customers_count, 1), 4) if connected_customers_count else 0.0

    subgraph = g.subgraph(component)
    graph_density = round(nx.density(subgraph), 4)

    shortest_paths = []
    for fraud_node in confirmed_fraud_nodes:
        try:
            sp = nx.shortest_path_length(g, source=customer_node, target=fraud_node)
            shortest_paths.append(sp)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
    shortest_path_to_fraud = min(shortest_paths) if shortest_paths else (component_size + 1)

    try:
        pagerank = nx.pagerank(subgraph)
        centrality = float(pagerank.get(customer_node, 0.0))
    except Exception:
        centrality = 0.0

    try:
        from networkx.algorithms.community import louvain_communities
        communities = list(louvain_communities(subgraph, seed=42))
        community_score = 0.0
        for i, comm in enumerate(communities):
            if customer_node in comm:
                fraud_in_comm = len(comm & confirmed_fraud_nodes)
                community_score = round(fraud_in_comm / max(len(comm), 1), 4)
                break
    except Exception:
        community_score = 0.0

    try:
        betweenness = nx.betweenness_centrality(subgraph, k=min(100, len(subgraph)))
        betweenness_score = float(betweenness.get(customer_node, 0.0))
    except Exception:
        betweenness_score = 0.0

    shared_address = set()
    shared_device = set()
    shared_payment = set()
    for cn in customer_nodes_in_component:
        cn_neighbors = set(g.neighbors(cn)) if g.has_node(cn) else set()
        for n in cn_neighbors:
            if n.startswith("address:"):
                shared_address.add(n)
            elif n.startswith("device:"):
                shared_device.add(n)

    base_features = _extract_base_features(BaseFraudGraph(
        graph=g, node_index={}, customer_to_node=graph_features.customer_to_node,
        return_to_node=graph_features.return_to_node,
        customer_rows={}, order_rows={}, return_rows={},
        text_clusters={}, confirmed_fraud_customers=graph_features.confirmed_fraud_customers,
        customer_order={},
    ), customer_id, return_id)

    ring_risk_score = min(100, int(
        base_features.get("shared_address_count", 0) * 8 +
        base_features.get("shared_device_count", 0) * 10 +
        base_features.get("shared_payment_count", 0) * 12 +
        base_features.get("shared_refund_account_count", 0) * 15 +
        fraud_neighbor_count * 20 +
        base_features.get("text_similarity_cluster_size", 0) * 8 +
        int(community_score * 30) +
        int(centrality * 50)
    ))

    signals = list(base_features.get("signals", []))
    if community_score > 0.3:
        signals.append("High-fraud community cluster")
    if centrality > 0.05:
        signals.append("Central node in fraud network")
    if graph_density > 0.3:
        signals.append("Dense fraud subgraph")

    return {
        "ring_risk_score": ring_risk_score,
        "connected_customers_count": connected_customers_count,
        "fraud_neighbor_count": fraud_neighbor_count,
        "shared_address_count": base_features.get("shared_address_count", 0),
        "shared_device_count": base_features.get("shared_device_count", 0),
        "shared_payment_count": base_features.get("shared_payment_count", 0),
        "shared_refund_account_count": base_features.get("shared_refund_account_count", 0),
        "shared_phone_count": base_features.get("shared_phone_count", 0),
        "text_similarity_cluster_size": base_features.get("text_similarity_cluster_size", 0),
        "component_size": component_size,
        "graph_density": graph_density,
        "fraud_ratio": fraud_ratio,
        "shortest_path_to_fraud": shortest_path_to_fraud,
        "community_score": community_score,
        "graph_centrality": round(centrality, 4),
        "betweenness_centrality": round(betweenness_score, 4),
        "signals": signals,
        "reason_codes": base_features.get("reason_codes", []),
        "summary": (
            f"Fraud ring risk score {ring_risk_score} across {component_size} customers "
            f"({connected_customers_count} connected, {fraud_neighbor_count} fraud neighbors). "
            f"Density: {graph_density}, Community fraud rate: {community_score:.1%}."
        ),
    }


def _empty_features() -> dict[str, Any]:
    return {
        "ring_risk_score": 0, "connected_customers_count": 0, "fraud_neighbor_count": 0,
        "shared_address_count": 0, "shared_device_count": 0, "shared_payment_count": 0,
        "shared_refund_account_count": 0, "shared_phone_count": 0,
        "text_similarity_cluster_size": 0, "component_size": 1, "graph_density": 0.0,
        "fraud_ratio": 0.0, "shortest_path_to_fraud": 0, "community_score": 0.0,
        "graph_centrality": 0.0, "betweenness_centrality": 0.0,
        "signals": [], "reason_codes": [],
        "summary": "No graph data available for this customer.",
    }
