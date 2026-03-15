"""
Benchmark Service for Clear Route.

Allows users to test specific gene values against the fitness function
before running a full optimization.
"""

import logging
from typing import Any

from app.services.optimization import (
    compile_fitness_function,
    OptimizationError,
)

logger = logging.getLogger(__name__)


class BenchmarkError(Exception):
    """Raised when a benchmark evaluation fails."""
    pass


class BenchmarkService:
    """Evaluates specific gene value combinations against the fitness function."""

    @staticmethod
    def run_benchmark(
        fitness_code: str,
        gene_values: dict[str, Any],
        genes: list[dict],
    ) -> dict[str, Any]:
        """
        Evaluate a specific set of gene values using the fitness function.

        Args:
            fitness_code: Python source defining fitness_function.
            gene_values: Dict mapping gene names to their values.
            genes: Pre-parsed list of gene dicts (from gene_record_to_dict).

        Returns:
            Dict with keys:
                - fitness: float or list[float] (the raw fitness value(s))
                - gene_values: dict of resolved gene values used
                - objective_values: dict mapping objective indices to values
                - constraint_violations: list of any detected issues
        """
        # Compile fitness function
        try:
            fitness_fn = compile_fitness_function(fitness_code)
        except OptimizationError as exc:
            raise BenchmarkError(f"Cannot compile fitness function: {exc}") from exc

        # Build solution array in gene order
        solution = []
        resolved_values = {}
        constraint_violations = []

        for gene in genes:
            name = gene["name"]

            if name not in gene_values:
                raise BenchmarkError(
                    f"Missing value for gene '{name}'. "
                    f"Required genes: {[g['name'] for g in genes]}"
                )

            raw_value = gene_values[name]

            try:
                value, resolved = _resolve_gene_value(gene, raw_value)
            except ValueError as exc:
                raise BenchmarkError(
                    f"Invalid value for gene '{name}': {exc}"
                ) from exc

            solution.append(value)
            resolved_values[name] = resolved

            # Check boundaries
            violation = _check_gene_boundaries(gene, value, raw_value)
            if violation:
                constraint_violations.append(violation)

        # Execute the fitness function
        try:
            result = fitness_fn(None, solution, 0)
        except Exception as exc:
            raise BenchmarkError(
                f"Fitness function execution failed: {exc}"
            ) from exc

        # Format response
        response: dict[str, Any] = {
            "gene_values": resolved_values,
            "constraint_violations": constraint_violations,
        }

        if isinstance(result, (tuple, list)):
            response["fitness"] = [float(v) for v in result]
            response["objective_values"] = {
                f"objective_{i+1}": float(v) for i, v in enumerate(result)
            }
        else:
            response["fitness"] = float(result)
            response["objective_values"] = {"objective_1": float(result)}

        return response


def _resolve_gene_value(gene: dict, raw_value: Any) -> tuple[Any, Any]:
    """
    Convert a raw input value to the appropriate type for the solution array.

    Returns:
        Tuple of (solution_value, display_value).

    Raises:
        ValueError: If the value cannot be converted.
    """
    gene_type = gene["type"]

    if gene_type == "int":
        try:
            int_val = int(round(float(raw_value)))
        except (ValueError, TypeError):
            raise ValueError(
                f"Cannot convert '{raw_value}' to integer"
            )
        return int_val, int_val

    elif gene_type == "float":
        try:
            float_val = float(raw_value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Cannot convert '{raw_value}' to float"
            )
        decimals = gene.get("decimals", 2)
        rounded = round(float_val, decimals)
        return rounded, rounded

    elif gene_type == "enum":
        options = gene["options"]
        str_val = str(raw_value).strip()

        # Accept either the option string or an integer index
        if str_val.isdigit():
            idx = int(str_val)
            if 0 <= idx < len(options):
                return idx, options[idx]
            raise ValueError(
                f"Index {idx} out of range for options: {options}"
            )

        # Match by name (case-insensitive)
        lower_options = [o.lower() for o in options]
        if str_val.lower() in lower_options:
            idx = lower_options.index(str_val.lower())
            return idx, options[idx]

        raise ValueError(
            f"'{str_val}' is not a valid option. Valid options: {options}"
        )

    raise ValueError(f"Unknown gene type: {gene_type}")


def _check_gene_boundaries(gene: dict, value: Any, raw_value: Any) -> str | None:
    """Check if a gene value is within its defined boundaries."""
    gene_type = gene["type"]
    name = gene["name"]

    if gene_type in ("int", "float"):
        low = gene.get("low")
        high = gene.get("high")
        if low is not None and float(value) < float(low):
            return (
                f"Gene '{name}': value {value} is below minimum {low}"
            )
        if high is not None and float(value) > float(high):
            return (
                f"Gene '{name}': value {value} exceeds maximum {high}"
            )

    return None
