"""Fail-closed expression parser with bounded evaluation cost."""
from __future__ import annotations

import ast
import logging
import operator
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_OPERATORS: dict[type, Any] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv, ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Is: operator.is_, ast.IsNot: operator.is_not, ast.In: operator.contains,
    ast.NotIn: lambda a, b: a not in b, ast.And: operator.and_, ast.Or: operator.or_,
    ast.Not: operator.not_, ast.USub: operator.neg,
}

ALLOWED_FUNCTIONS: dict[str, Any] = {
    "int": int, "float": float, "str": str, "bool": bool,
    "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
    "len": len, "lower": str.lower, "upper": str.upper, "strip": str.strip,
    "startswith": str.startswith, "endswith": str.endswith,
    "contains": lambda s, sub: sub in s, "all": all, "any": any,
}

ALLOWED_ATTRIBUTES = {
    "lower", "upper", "strip", "replace", "split", "join", "startswith", "endswith",
    "contains", "find", "index", "count", "isalpha", "isdigit", "isalnum",
    "keys", "values", "items", "get", "update", "length", "size", "empty",
}

_ALLOWED_OPERATOR_NODES = tuple(ALLOWED_OPERATORS)


class ConditionParser:
    """Whitelist-based expression evaluator with explicit resource limits."""

    def __init__(
        self,
        allowed_operators: dict[type, Any] | None = None,
        allowed_functions: dict[str, Any] | None = None,
        allowed_attributes: set[str] | None = None,
        max_depth: int = 10,
        max_nodes: int = 256,
        max_expression_length: int = 4096,
        max_power_exponent: int = 32,
        max_sequence_repeat: int = 100_000,
    ) -> None:
        self.allowed_operators = allowed_operators or ALLOWED_OPERATORS
        self.allowed_functions = allowed_functions or ALLOWED_FUNCTIONS
        self.allowed_attributes = allowed_attributes or ALLOWED_ATTRIBUTES
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.max_expression_length = max_expression_length
        self.max_power_exponent = max_power_exponent
        self.max_sequence_repeat = max_sequence_repeat

    def evaluate(self, condition: str, context: dict[str, Any] | None = None, fail_closed: bool = True) -> bool:
        try:
            if not isinstance(condition, str) or len(condition) > self.max_expression_length:
                raise ValueError("condition is missing or exceeds the expression-size limit")
            tree = ast.parse(condition, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > self.max_nodes:
                raise ValueError("condition exceeds the AST node limit")
            self._validate_ast(tree)
            self._validate_runtime_cost(tree, context or {})
            code = compile(tree, "<condition>", "eval")
            safe_globals: dict[str, Any] = {"__builtins__": {}, **self.allowed_functions}
            if context:
                safe_globals.update(context)
            result = eval(code, safe_globals, {})
            if not isinstance(result, bool):
                raise ValueError("condition must return boolean")
            return result
        except Exception as exc:
            logger.warning("Condition rejected/evaluation failed: %s", exc)
            if fail_closed:
                return False
            raise

    def _validate_runtime_cost(self, tree: ast.AST, context: dict[str, Any]) -> None:
        """Reject sequence repetition that could allocate unbounded memory."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
                continue

            left = self._resolve_static_value(node.left, context)
            right = self._resolve_static_value(node.right, context)

            for sequence, multiplier in ((left, right), (right, left)):
                if isinstance(sequence, (str, bytes, list, tuple)) and isinstance(multiplier, int):
                    if abs(multiplier) > self.max_sequence_repeat:
                        raise ValueError("sequence repetition exceeds safety limit")

            # If either side cannot be proven numeric, reject the multiplication
            # rather than allowing an unknown string/list from context or a
            # function call to become an allocation primitive.
            if left is _UNKNOWN or right is _UNKNOWN:
                continue
            if not self._is_numeric_value(left) or not self._is_numeric_value(right):
                raise ValueError("non-numeric multiplication is not allowed")

    @staticmethod
    def _is_numeric_value(value: Any) -> bool:
        return isinstance(value, (int, float, complex)) and not isinstance(value, bool)

    @staticmethod
    def _resolve_static_value(node: ast.AST, context: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return context.get(node.id, _UNKNOWN)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = ConditionParser._resolve_static_value(node.operand, context)
            if value is _UNKNOWN:
                return _UNKNOWN
            try:
                return -value if isinstance(node.op, ast.USub) else +value
            except Exception:
                return _UNKNOWN
        return _UNKNOWN

    def _validate_ast(self, node: ast.AST, depth: int = 0) -> None:
        if depth > self.max_depth:
            raise ValueError(f"AST depth exceeds maximum of {self.max_depth}")

        if isinstance(node, ast.Expression):
            self._validate_ast(node.body, depth + 1)
        elif isinstance(node, ast.BoolOp):
            self._validate_ast(node.op, depth + 1)
            for value in node.values:
                self._validate_ast(value, depth + 1)
        elif isinstance(node, ast.BinOp):
            self._validate_ast(node.left, depth + 1)
            self._validate_ast(node.right, depth + 1)
            self._validate_ast(node.op, depth + 1)
            if isinstance(node.op, ast.Pow):
                if not isinstance(node.right, ast.Constant) or not isinstance(node.right.value, int):
                    raise ValueError("power exponent must be a bounded integer constant")
                if abs(node.right.value) > self.max_power_exponent:
                    raise ValueError("power exponent exceeds safety limit")
        elif isinstance(node, ast.UnaryOp):
            self._validate_ast(node.operand, depth + 1)
            self._validate_ast(node.op, depth + 1)
        elif isinstance(node, ast.Compare):
            self._validate_ast(node.left, depth + 1)
            for comparator in node.comparators:
                self._validate_ast(comparator, depth + 1)
            for op in node.ops:
                self._validate_ast(op, depth + 1)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in self.allowed_functions:
                    raise ValueError(f"Function '{node.func.id}' is not allowed")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr not in self.allowed_attributes:
                    raise ValueError(f"Attribute '{node.func.attr}' is not allowed")
                self._validate_ast(node.func.value, depth + 1)
            else:
                raise ValueError("call target is not allowed")
            for arg in node.args:
                self._validate_ast(arg, depth + 1)
            for keyword in node.keywords:
                self._validate_ast(keyword.value, depth + 1)
        elif isinstance(node, ast.Attribute):
            if node.attr not in self.allowed_attributes:
                raise ValueError(f"Attribute '{node.attr}' is not allowed")
            self._validate_ast(node.value, depth + 1)
        elif isinstance(node, ast.Name):
            pass
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (bytes, str)) and len(node.value) > self.max_expression_length:
                raise ValueError("constant exceeds safety limit")
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for elt in node.elts:
                self._validate_ast(elt, depth + 1)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    self._validate_ast(key, depth + 1)
                self._validate_ast(value, depth + 1)
        elif isinstance(node, ast.IfExp):
            self._validate_ast(node.test, depth + 1)
            self._validate_ast(node.body, depth + 1)
            self._validate_ast(node.orelse, depth + 1)
        elif isinstance(node, _ALLOWED_OPERATOR_NODES):
            if type(node) not in self.allowed_operators:
                raise ValueError(f"Operator '{type(node).__name__}' is not allowed")
        else:
            raise ValueError(f"AST node type '{type(node).__name__}' is not allowed")

    def validate_condition(self, condition: str) -> bool:
        try:
            if not isinstance(condition, str) or len(condition) > self.max_expression_length:
                return False
            tree = ast.parse(condition, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > self.max_nodes:
                return False
            self._validate_ast(tree)
            return True
        except (SyntaxError, ValueError):
            return False

    def extract_variables(self, condition: str) -> set[str]:
        try:
            tree = ast.parse(condition, mode="eval")
            return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        except SyntaxError:
            return set()


_UNKNOWN = object()
condition_parser = ConditionParser()


def evaluate_condition(condition: str, context: dict[str, Any] | None = None) -> bool:
    return condition_parser.evaluate(condition, context, fail_closed=True)


def validate_condition_syntax(condition: str) -> bool:
    return condition_parser.validate_condition(condition)


def get_condition_variables(condition: str) -> set[str]:
    return condition_parser.extract_variables(condition)
