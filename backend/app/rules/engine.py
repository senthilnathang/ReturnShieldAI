from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SafeEval(ast.NodeVisitor):
    allowed_names = {"abs": abs, "min": min, "max": max, "round": round}

    def __init__(self, context: dict[str, Any]):
        self.context = context

    def visit(self, node):  # type: ignore[override]
        return super().visit(node)

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        return node.value

    def visit_Name(self, node: ast.Name):
        if node.id in self.context:
            return self.context[node.id]
        if node.id in self.allowed_names:
            return self.allowed_names[node.id]
        raise KeyError(node.id)

    def visit_BoolOp(self, node: ast.BoolOp):
        values = [self.visit(value) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("Unsupported boolean operation")

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise ValueError("Unsupported unary operation")

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise ValueError("Unsupported binary operation")

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            if isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            else:
                raise ValueError("Unsupported comparison")
            if not ok:
                return False
            left = right
        return True

    def visit_Call(self, node: ast.Call):
        func = self.visit(node.func)
        args = [self.visit(arg) for arg in node.args]
        return func(*args)


@dataclass
class RuleResult:
    rule_id: str
    name: str
    score: int
    reason: str
    triggered: bool


class RuleEngine:
    def __init__(self, rules: list[dict[str, Any]]):
        self.rules = rules

    @classmethod
    def from_file(cls, path: str | Path):
        return cls(json.loads(Path(path).read_text()))

    def evaluate(self, context: dict[str, Any]) -> tuple[float, list[str], list[RuleResult]]:
        triggered: list[RuleResult] = []
        total = 0.0
        for raw_rule in self.rules:
            if not raw_rule.get("enabled", True):
                continue
            rule_context = dict(context)
            tree = ast.parse(raw_rule["condition"], mode="eval")
            matched = bool(SafeEval(rule_context).visit(tree))
            if matched:
                score = float(raw_rule.get("score", 0))
                total += score
                triggered.append(
                    RuleResult(
                        rule_id=str(raw_rule.get("id", raw_rule["name"])),
                        name=raw_rule["name"],
                        score=int(score),
                        reason=raw_rule.get("description") or raw_rule["name"],
                        triggered=True,
                    )
                )
        return min(total, 100.0), [rule.reason for rule in triggered], triggered
