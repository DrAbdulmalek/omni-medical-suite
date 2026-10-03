"""
Pipeline Engine - Updated to use Safe Condition Parser
"""
import logging
from typing import Any

from app.core.condition_parser import evaluate_condition, validate_condition_syntax

logger = logging.getLogger(__name__)

class PipelineEngine:
    """
    Pipeline engine with safe condition evaluation.
    Replaces eval() with fail-closed condition parser.
    """

    def __init__(self):
        self.hooks = {}
        self.registry = {}

    def register_hook(self, hook_name: str, hook_func: callable):
        """Register a hook function"""
        self.hooks[hook_name] = hook_func

    def register_step(self, step_name: str, step_func: callable):
        """Register a pipeline step"""
        self.registry[step_name] = step_func

    def evaluate_condition(
        self,
        condition: str,
        context: dict[str, Any] | None = None
    ) -> bool:
        """
        Evaluate a pipeline condition safely.

        Args:
            condition: Condition string to evaluate
            context: Variables available in the condition

        Returns:
            bool: Result of the condition evaluation (False on any error)

        Note:
            This method uses fail-closed behavior. If the condition cannot be
            evaluated safely, it returns False rather than raising an exception.
        """
        if not condition:
            return True  # Empty condition is considered True

        try:
            return evaluate_condition(condition, context)
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False

    def validate_condition(self, condition: str) -> bool:
        """
        Validate that a condition is syntactically valid and safe.

        Args:
            condition: Condition string to validate

        Returns:
            bool: True if condition is valid and safe, False otherwise
        """
        return validate_condition_syntax(condition)

    def run_step(
        self,
        step_name: str,
        data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run a pipeline step with condition evaluation.

        Args:
            step_name: Name of the step to run
            data: Input data for the step
            context: Additional context for condition evaluation

        Returns:
            Dict[str, Any]: Output data from the step
        """
        if step_name not in self.registry:
            raise ValueError(f"Step '{step_name}' not registered")

        step_func = self.registry[step_name]
        return step_func(data, context)

    def run_pipeline(
        self,
        pipeline_definition: list[dict[str, Any]],
        initial_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Run a complete pipeline with conditional steps.

        Args:
            pipeline_definition: List of pipeline step definitions
            initial_data: Initial data for the pipeline
            context: Additional context for condition evaluation

        Returns:
            Dict[str, Any]: Final output data from the pipeline
        """
        if context is None:
            context = {}

        current_data = initial_data.copy()

        for step_def in pipeline_definition:
            step_name = step_def.get('name')
            condition = step_def.get('condition')
            step_data = step_def.get('data', {})

            # Check if step should be executed
            if condition:
                if not self.evaluate_condition(condition, {**current_data, **context, **step_data}):
                    logger.debug(f"Skipping step '{step_name}' - condition not met")
                    continue

            # Run the step
            try:
                if step_name in self.registry:
                    result = self.run_step(step_name, current_data, context)
                    current_data.update(result)
                else:
                    logger.warning(f"Step '{step_name}' not found in registry")
            except Exception as e:
                logger.error(f"Step '{step_name}' failed: {e}")
                # Fail-closed: stop pipeline on error
                return {
                    **current_data,
                    '_error': str(e),
                    '_failed_step': step_name
                }

        return current_data

# Global pipeline engine instance
pipeline_engine = PipelineEngine()
