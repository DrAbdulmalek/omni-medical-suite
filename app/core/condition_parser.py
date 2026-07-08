"""
Safe Condition Parser - Replaces eval() with fail-closed behavior
"""
import ast
import logging
import operator
from typing import Any

logger = logging.getLogger(__name__)

# Allowed operators
ALLOWED_OPERATORS: dict[type, Any] = {
    # Arithmetic
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,

    # Comparison
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: operator.contains,
    ast.NotIn: lambda a, b: a not in b,

    # Boolean
    ast.And: operator.and_,
    ast.Or: operator.or_,
    ast.Not: operator.not_,
    ast.USub: operator.neg,
}

# Allowed built-in functions
ALLOWED_FUNCTIONS: dict[str, Any] = {
    # Type conversion
    'int': int,
    'float': float,
    'str': str,
    'bool': bool,

    # Math
    'abs': abs,
    'min': min,
    'max': max,
    'sum': sum,
    'round': round,
    'pow': pow,

    # String
    'len': len,
    'lower': str.lower,
    'upper': str.upper,
    'strip': str.strip,
    'startswith': str.startswith,
    'endswith': str.endswith,
    'contains': lambda s, sub: sub in s,

    # Collection
    'all': all,
    'any': any,
}

# Allowed attributes
ALLOWED_ATTRIBUTES: set[str] = {
    # String
    'lower', 'upper', 'strip', 'replace', 'split', 'join', 'startswith', 'endswith',
    'contains', 'find', 'index', 'count', 'isalpha', 'isdigit', 'isalnum',

    # List
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'reverse', 'sort', 'copy',

    # Dict
    'keys', 'values', 'items', 'get', 'update', # Common
    'length', 'size', 'empty'
}

class ConditionParser:
    """
    Safe condition parser with whitelist of allowed operations.
    Replaces eval() with fail-closed behavior.
    """

    def __init__(
        self,
        allowed_operators: dict[type, Any] | None = None,
        allowed_functions: dict[str, Any] | None = None,
        allowed_attributes: set[str] | None = None,
        max_depth: int = 10
    ):
        """
        Initialize the condition parser.

        Args:
            allowed_operators: Dictionary of allowed AST node types to functions
            allowed_functions: Dictionary of allowed function names to functions
            allowed_attributes: Set of allowed attribute names
            max_depth: Maximum depth of AST to prevent DoS
        """
        self.allowed_operators = allowed_operators or ALLOWED_OPERATORS
        self.allowed_functions = allowed_functions or ALLOWED_FUNCTIONS
        self.allowed_attributes = allowed_attributes or ALLOWED_ATTRIBUTES
        self.max_depth = max_depth

    def evaluate(
        self,
        condition: str,
        context: dict[str, Any] | None = None,
        fail_closed: bool = True
    ) -> bool:
        """
        Safely evaluate a condition string.

        Args:
            condition: The condition string to evaluate
            context: Dictionary of variables available in the condition
            fail_closed: If True, return False on any error (secure default)

        Returns:
            bool: Result of the condition evaluation

        Raises:
            ValueError: If condition contains disallowed operations and fail_closed=False
        """
        try:
            # Parse the condition into AST
            tree = ast.parse(condition, mode='eval')

            # Validate the AST
            self._validate_ast(tree)

            # Compile to code object
            code = compile(tree, '<string>', 'eval')

            # Create safe globals
            safe_globals: dict[str, Any] = {
                '__builtins__': dict(self.allowed_functions.items()),
                **self.allowed_functions
            }

            # Add context variables
            if context:
                safe_globals.update(context)

            # Execute with restricted globals and empty locals
            result = eval(code, safe_globals, {})

            # Ensure result is boolean
            if not isinstance(result, bool):
                if fail_closed:
                    logger.warning(f"Condition returned non-boolean: {result}")
                    return False
                raise ValueError(f"Condition must return boolean, got {type(result).__name__}")

            return result

        except (SyntaxError, ValueError) as e:
            logger.error(f"Invalid condition syntax: {e}")
            return False if fail_closed else False
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False if fail_closed else False

    def _validate_ast(self, node: ast.AST, depth: int = 0) -> None:
        """
        Recursively validate AST nodes against whitelist.

        Args:
            node: AST node to validate
            depth: Current depth in AST tree

        Raises:
            ValueError: If disallowed operations are found
        """
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
            # Check function is allowed
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name not in self.allowed_functions:
                    raise ValueError(f"Function '{func_name}' is not allowed")
            elif isinstance(node.func, ast.Attribute):
                # Check attribute is allowed
                if node.func.attr not in self.allowed_attributes:
                    raise ValueError(f"Attribute '{node.func.attr}' is not allowed")

            for arg in node.args:
                self._validate_ast(arg, depth + 1)
            for keyword in node.keywords:
                self._validate_ast(keyword.value, depth + 1)
        elif isinstance(node, ast.Name):
            # Variable names are allowed (will be in context)
            pass
        elif isinstance(node, ast.Constant):
            # Constants are allowed
            pass
        elif isinstance(node, ast.List):
            for elt in node.elts:
                self._validate_ast(elt, depth + 1)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=False):
                self._validate_ast(key, depth + 1)
                self._validate_ast(value, depth + 1)
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                self._validate_ast(elt, depth + 1)
        elif isinstance(node, ast.IfExp):
            self._validate_ast(node.test, depth + 1)
            self._validate_ast(node.body, depth + 1)
            self._validate_ast(node.orelse, depth + 1)
        elif isinstance(node, ast.DictComp):
            self._validate_ast(node.key, depth + 1)
            self._validate_ast(node.value, depth + 1)
            for generator in node.generators:
                self._validate_ast(generator, depth + 1)
        elif isinstance(node, ast.ListComp):
            self._validate_ast(node.elt, depth + 1)
            for generator in node.generators:
                self._validate_ast(generator, depth + 1)
        elif isinstance(node, ast.comprehension):
            self._validate_ast(node.target, depth + 1)
            self._validate_ast(node.iter, depth + 1)
            for if_expr in node.ifs:
                self._validate_ast(if_expr, depth + 1)
        elif isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
                              ast.FloorDiv, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
                              ast.Gt, ast.GtE, ast.And, ast.Or, ast.Not, ast.Is,
                              ast.IsNot, ast.In, ast.NotIn, ast.USub)):
            # Check operator is allowed
            if type(node) not in self.allowed_operators:
                raise ValueError(f"Operator '{type(node).__name__}' is not allowed")
        elif isinstance(node, (ast.NameConstant, ast.Num, ast.Str)):
            # Python 3.7 compatibility
            pass
        else:
            raise ValueError(f"AST node type '{type(node).__name__}' is not allowed")

    def validate_condition(self, condition: str) -> bool:
        """
        Validate that a condition string is safe to evaluate.

        Args:
            condition: The condition string to validate

        Returns:
            bool: True if condition is safe, False otherwise
        """
        try:
            tree = ast.parse(condition, mode='eval')
            self._validate_ast(tree)
            return True
        except (SyntaxError, ValueError):
            return False

    def extract_variables(self, condition: str) -> set[str]:
        """
        Extract variable names from a condition string.

        Args:
            condition: The condition string to analyze

        Returns:
            Set[str]: Set of variable names used in the condition
        """
        try:
            tree = ast.parse(condition, mode='eval')
            return self._extract_variables_from_ast(tree)
        except SyntaxError:
            return set()

    def _extract_variables_from_ast(self, node: ast.AST) -> set[str]:
        """Recursively extract variable names from AST"""
        variables = set()

        if isinstance(node, ast.Name):
            variables.add(node.id)
        elif isinstance(node, ast.Attribute):
            variables.add(node.attr)
            if isinstance(node.value, ast.Name):
                variables.add(node.value.id)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                variables.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                variables.add(node.func.attr)
                if isinstance(node.func.value, ast.Name):
                    variables.add(node.func.value.id)
            for arg in node.args:
                variables.update(self._extract_variables_from_ast(arg))
            for keyword in node.keywords:
                variables.update(self._extract_variables_from_ast(keyword.value))

        # Recursively process child nodes
        for _field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        variables.update(self._extract_variables_from_ast(item))
            elif isinstance(value, ast.AST):
                variables.update(self._extract_variables_from_ast(value))

        return variables

# Global parser instance with default settings
condition_parser = ConditionParser()

def evaluate_condition(
    condition: str,
    context: dict[str, Any] | None = None
) -> bool:
    """
    Safely evaluate a condition string with fail-closed behavior.

    This is the main function to use throughout the application to replace eval().

    Args:
        condition: Condition string to evaluate
        context: Dictionary of variables available in the condition

    Returns:
        bool: Result of the condition evaluation (False on any error)

    Example:
        >>> evaluate_condition("x > 5 and y < 10", {"x": 6, "y": 8})
        True
        >>> evaluate_condition("x > 5 and y < 10", {"x": 4, "y": 8})
        False
        >>> evaluate_condition("exec('rm -rf /')", {})  # Malicious code
        False
    """
    return condition_parser.evaluate(condition, context, fail_closed=True)

def validate_condition_syntax(condition: str) -> bool:
    """
    Validate that a condition string has valid syntax and uses only allowed operations.

    Args:
        condition: Condition string to validate

    Returns:
        bool: True if condition is syntactically valid and safe, False otherwise
    """
    return condition_parser.validate_condition(condition)

def get_condition_variables(condition: str) -> set[str]:
    """
    Extract variable names from a condition string.

    Args:
        condition: Condition string to analyze

    Returns:
        Set[str]: Set of variable names used in the condition
    """
    return condition_parser.extract_variables(condition)
