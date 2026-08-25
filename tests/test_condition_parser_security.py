"""Regression tests for condition-parser resource exhaustion hardening."""

from app.core.condition_parser import ConditionParser, evaluate_condition


def test_string_repetition_is_rejected_before_eval() -> None:
    parser = ConditionParser(max_sequence_repeat=100_000)
    assert parser.evaluate('len("a" * 999999999) > 0') is False


def test_context_string_repetition_is_rejected() -> None:
    parser = ConditionParser(max_sequence_repeat=100_000)
    assert parser.evaluate("len(value * 999999999) > 0", {"value": "a"}) is False


def test_bounded_numeric_multiplication_still_works() -> None:
    parser = ConditionParser()
    assert parser.evaluate("2 * 3 == 6") is True


def test_pow_escape_remains_blocked() -> None:
    assert evaluate_condition("2 ** 10000 > 0") is False


def test_attribute_escape_remains_blocked() -> None:
    assert evaluate_condition("().__class__") is False
