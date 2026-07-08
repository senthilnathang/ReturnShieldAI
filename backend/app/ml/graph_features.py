from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
import hashlib
import re

try:
    import networkx as nx
except Exception:  # pragma: no cover - optional dependency for hackathon portability
    nx = None

from backend.app.models import Customer, Order, ReturnRecord

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "had", "has", "have",
    "i", "in", "is", "it", "need", "my", "of", "on", "or", "please", "product", "return",
    "the", "this", "to", "was", "we", "with", "would", "want", "request", "item", "box",
}


@dataclass
class FraudGraph:
    graph: Any
    node_index: dict[str, set[str]]
    customer_to_node: dict[UUID, str]
    return_to_node: dict[UUID, str]
    customer_rows: dict[UUID, Customer]
    order_rows: dict[UUID, Order]
    return_rows: dict[UUID, ReturnRecord]
    text_clusters: dict[str, set[UUID]]
    confirmed_fraud_customers: set[UUID]
    customer_order: dict[UUID, Order]


def _customer_node(customer_id: UUID) -> str:
    return f"customer:{customer_id}"


def _order_node(order_id: UUID) -> str:
    return f"order:{order_id}"


def _return_node(return_id: UUID) -> str:
    return f"return:{return_id}"


def _address_node(address: str) -> str:
    return f"address:{address.strip().lower()}"


def _phone_node(phone: str) -> str:
    return f"phone:{phone.strip().lower()}"


def _email_node(email: str) -> str:
    email = email.strip().lower()
    domain = email.split("@")[-1] if "@" in email else email
    return f"email:{domain}:{hashlib.sha1(email.encode()).hexdigest()[:8]}"


def _device_node(device_id: str) -> str:
    return f"device:{device_id.strip().lower()}"


def _payment_node(order: Order) -> str:
    return f"payment:{order.payment_method.strip().lower()}"


def _refund_account_proxy(customer: Customer, order: Order, return_record: ReturnRecord) -> str:
    # The MVP does not persist a dedicated refund-account field, so we use a stable proxy.
    reason_key = _text_cluster_key(return_record.return_reason)
    return f"refund:{customer.address.strip().lower()}:{order.payment_method.strip().lower()}:{reason_key}"


def _product_node(order: Order) -> str:
    return f"product:{order.sku.strip().lower()}"


def _text_cluster_key(text: str) -> str:
    tokens = [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOPWORDS]
    if not tokens:
        return "text:empty"
    return "text:" + "-".join(tokens[:8])


def _add_edge(graph: Any, left: str, right: str, relation: str) -> None:
    if nx is not None and hasattr(graph, "add_edge"):
        graph.add_edge(left, right, relation=relation)
        return
    graph[left].add(right)
    graph[right].add(left)


def _neighbors(graph: Any, node: str) -> set[str]:
    if nx is not None and hasattr(graph, "neighbors"):
        return set(graph.neighbors(node)) if graph.has_node(node) else set()
    return set(graph.get(node, set()))


def _shortest_path_length(graph: Any, start: str, goals: set[str]) -> int | None:
    if not goals:
        return None
    if nx is not None and hasattr(graph, "shortest_path_length"):
        best: int | None = None
        for goal in goals:
            try:
                distance = nx.shortest_path_length(graph, start, goal)
            except Exception:
                continue
            best = distance if best is None else min(best, distance)
        return best
    visited = {start}
    queue = deque([(start, 0)])
    while queue:
        node, depth = queue.popleft()
        if node in goals:
            return depth
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
    return None


def build_fraud_graph(customers: list[Customer], orders: list[Order], returns: list[ReturnRecord]) -> FraudGraph:
    graph = nx.Graph() if nx is not None else defaultdict(set)
    node_index: dict[str, set[str]] = defaultdict(set)
    customer_to_node: dict[UUID, str] = {}
    return_to_node: dict[UUID, str] = {}
    customer_rows = {customer.id: customer for customer in customers}
    order_rows = {order.id: order for order in orders}
    return_rows = {return_record.id: return_record for return_record in returns}
    customer_order = {order.customer_id: order for order in orders}
    text_clusters: dict[str, set[UUID]] = defaultdict(set)

    for customer in customers:
        c_node = _customer_node(customer.id)
        customer_to_node[customer.id] = c_node
        if nx is not None:
            graph.add_node(c_node, kind="customer", entity_id=str(customer.id))
        node_index[c_node].add(c_node)
        for node, relation in [
            (_address_node(customer.address), "USES_ADDRESS"),
            (_phone_node(customer.phone), "USES_PHONE"),
            (_email_node(customer.email), "USES_EMAIL"),
            (_device_node(customer.device_id), "USES_DEVICE"),
        ]:
            if nx is not None:
                graph.add_node(node)
            node_index[node].add(c_node)
            _add_edge(graph, c_node, node, relation)

    for order in orders:
        o_node = _order_node(order.id)
        if nx is not None:
            graph.add_node(o_node, kind="order", entity_id=str(order.id))
        node_index[o_node].add(_customer_node(order.customer_id))
        _add_edge(graph, _customer_node(order.customer_id), o_node, "CREATED_ORDER")
        for node, relation in [
            (_payment_node(order), "USES_PAYMENT"),
            (_product_node(order), "RETURNED_PRODUCT"),
        ]:
            if nx is not None:
                graph.add_node(node)
            _add_edge(graph, o_node, node, relation)
            node_index[node].add(o_node)

    for return_record in returns:
        r_node = _return_node(return_record.id)
        return_to_node[return_record.id] = r_node
        if nx is not None:
            graph.add_node(r_node, kind="return", entity_id=str(return_record.id))
        _add_edge(graph, _customer_node(return_record.customer_id), r_node, "CREATED_RETURN")
        order = order_rows.get(return_record.order_id)
        if order:
            _add_edge(graph, r_node, _order_node(order.id), "CREATED_FROM_ORDER")
            text_key = _text_cluster_key(return_record.return_reason)
            text_clusters[text_key].add(return_record.customer_id)
            text_node = text_key
            if nx is not None:
                graph.add_node(text_node, kind="text_pattern")
            _add_edge(graph, r_node, text_node, "SIMILAR_TEXT")
            node_index[text_node].add(r_node)
            refund_proxy = _refund_account_proxy(customer_rows[return_record.customer_id], order, return_record)
            if nx is not None:
                graph.add_node(refund_proxy, kind="refund_account")
            _add_edge(graph, r_node, refund_proxy, "USED_REFUND_ACCOUNT")
            node_index[refund_proxy].add(r_node)
            pickup_proxy = _address_node(customer_rows[return_record.customer_id].address)
            _add_edge(graph, r_node, pickup_proxy, "SHARED_PICKUP_LOCATION")

    confirmed_fraud_customers = set()
    return FraudGraph(
        graph=graph,
        node_index=node_index,
        customer_to_node=customer_to_node,
        return_to_node=return_to_node,
        customer_rows=customer_rows,
        order_rows=order_rows,
        return_rows=return_rows,
        text_clusters=text_clusters,
        confirmed_fraud_customers=confirmed_fraud_customers,
        customer_order=customer_order,
    )


def extract_graph_features(graph_bundle: FraudGraph, customer_id: UUID, return_id: UUID) -> dict[str, Any]:
    customer = graph_bundle.customer_rows[customer_id]
    order = graph_bundle.customer_order.get(customer_id)
    return_record = graph_bundle.return_rows[return_id]
    graph = graph_bundle.graph
    customer_node = graph_bundle.customer_to_node[customer_id]
    return_node = graph_bundle.return_to_node[return_id]

    address_node = _address_node(customer.address)
    phone_node = _phone_node(customer.phone)
    device_node = _device_node(customer.device_id)
    email_node = _email_node(customer.email)
    payment_node = _payment_node(order) if order else ""
    refund_node = _refund_account_proxy(customer, order, return_record) if order else ""
    text_node = _text_cluster_key(return_record.return_reason)
    product_node = _product_node(order) if order else ""

    node_neighbors = _neighbors(graph, customer_node)
    same_address_customers = node_neighbors.intersection(_neighbors(graph, address_node)) if address_node else set()
    same_phone_customers = node_neighbors.intersection(_neighbors(graph, phone_node)) if phone_node else set()
    same_device_customers = node_neighbors.intersection(_neighbors(graph, device_node)) if device_node else set()

    shared_address_count = max(0, len(_neighbors(graph, address_node)) - 1) if address_node else 0
    shared_phone_count = max(0, len(_neighbors(graph, phone_node)) - 1) if phone_node else 0
    shared_device_count = max(0, len(_neighbors(graph, device_node)) - 1) if device_node else 0
    shared_payment_count = max(0, len(_neighbors(graph, payment_node)) - 1) if payment_node else 0
    shared_refund_account_count = max(0, len(_neighbors(graph, refund_node)) - 1) if refund_node else 0
    text_similarity_cluster_size = max(1, len(graph_bundle.text_clusters.get(text_node, {customer_id})))
    same_sku_return_cluster_count = max(0, len(_neighbors(graph, product_node)) - 1) if product_node else 0
    component_nodes = set()
    if nx is not None and hasattr(graph, "has_node") and graph.has_node(customer_node):
        component_nodes = set(nx.node_connected_component(graph, customer_node))
    else:
        visited = {customer_node}
        queue = deque([customer_node])
        while queue:
            node = queue.popleft()
            component_nodes.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

    connected_customers = {
        node for node in component_nodes if node.startswith("customer:") and node != customer_node
    }
    connected_customers_count = len(connected_customers)

    confirmed_fraud_nodes = set()
    for other_customer_id in graph_bundle.confirmed_fraud_customers:
        confirmed_fraud_nodes.add(graph_bundle.customer_to_node[other_customer_id])
    fraud_neighbor_count = len(connected_customers.intersection(confirmed_fraud_nodes))
    high_risk_neighbor_ratio = round(fraud_neighbor_count / max(connected_customers_count, 1), 2) if connected_customers_count else 0.0
    component_size = len({node for node in component_nodes if node.startswith("customer:")})

    shortest_path_to_fraud = _shortest_path_length(graph, customer_node, confirmed_fraud_nodes)
    if shortest_path_to_fraud is None:
        shortest_path_to_fraud = component_size + 1 if component_size else 0

    ring_risk_score = min(
        100,
        int(
            shared_address_count * 8
            + shared_device_count * 10
            + shared_payment_count * 12
            + shared_refund_account_count * 15
            + fraud_neighbor_count * 20
            + text_similarity_cluster_size * 8
        ),
    )
    return_velocity_in_component = round((component_size or 1) * max(return_record.returned_weight or 0.1, 0.1), 2)

    signals = []
    if shared_address_count >= 3:
        signals.append("Shared address ring")
    if shared_device_count >= 3:
        signals.append("Device reuse ring")
    if shared_payment_count >= 3:
        signals.append("Shared payment cluster")
    if shared_refund_account_count >= 3:
        signals.append("Shared refund account ring")
    if fraud_neighbor_count >= 1:
        signals.append("Confirmed fraud neighbor")
    if text_similarity_cluster_size >= 3:
        signals.append("Reused return script cluster")

    reason_codes = [
        *( ["Multiple customers use the same address"] if shared_address_count >= 3 else []),
        *( ["Same device is linked to multiple customers"] if shared_device_count >= 3 else []),
        *( ["Same payment method appears across accounts"] if shared_payment_count >= 3 else []),
        *( ["Multiple refunds resolve to the same account proxy"] if shared_refund_account_count >= 3 else []),
        *( ["Connected to a confirmed fraud neighbor"] if fraud_neighbor_count >= 1 else []),
        *( ["Return story is reused across accounts"] if text_similarity_cluster_size >= 3 else []),
    ]

    return {
        "connected_customers_count": connected_customers_count,
        "shared_address_count": shared_address_count,
        "shared_device_count": shared_device_count,
        "shared_payment_count": shared_payment_count,
        "shared_refund_account_count": shared_refund_account_count,
        "shared_phone_count": shared_phone_count,
        "text_similarity_cluster_size": text_similarity_cluster_size,
        "fraud_neighbor_count": fraud_neighbor_count,
        "ring_risk_score": ring_risk_score,
        "shortest_path_to_fraud": shortest_path_to_fraud,
        "component_size": component_size,
        "high_risk_neighbor_ratio": high_risk_neighbor_ratio,
        "same_sku_return_cluster_count": same_sku_return_cluster_count,
        "same_pickup_location_count": shared_address_count,
        "return_velocity_in_component": return_velocity_in_component,
        "signals": signals,
        "reason_codes": reason_codes,
        "summary": (
            f"Fraud ring risk score {ring_risk_score} across {component_size} connected customers."
            if ring_risk_score >= 40
            else "No strong fraud ring detected from current graph links."
        ),
    }
