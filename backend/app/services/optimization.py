"""
Optimization Service for Clear Route.

Runs genetic algorithm optimizations using PyGAD with dynamically generated
fitness functions from the LLM.
"""

import logging
import math
from typing import Any, Callable, Optional

import numpy as np
import pygad

logger = logging.getLogger(__name__)


class OptimizationError(Exception):
    """Raised when an optimization run fails."""
    pass


# ------------------------------------------------------------------
# Fitness Function Execution
# ------------------------------------------------------------------

# Allowed builtins for fitness function execution
_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "pow": pow,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "True": True,
    "False": False,
    "None": None,
}

# Modules that are safe to import inside fitness functions
_ALLOWED_MODULES = {
    "math": math,
    "numpy": np,
    "np": np,
}


def _safe_import(name, *args, **kwargs):
    """Restricted import that only allows pre-approved modules and numpy internals."""
    if name in _ALLOWED_MODULES:
        return _ALLOWED_MODULES[name]
    # Allow numpy's own internal submodule imports (e.g. numpy._core.arrayprint)
    if name.startswith("numpy.") or name.startswith("numpy._"):
        import importlib
        return importlib.import_module(name)
    raise ImportError(f"Import of '{name}' is not allowed in fitness functions")


def compile_fitness_function(fitness_code: str) -> Callable:
    """
    Compile a fitness function string into a callable in a controlled namespace.

    The namespace includes math module and safe builtins, but excludes
    dangerous operations like file I/O, imports, exec, eval, etc.

    Args:
        fitness_code: Python source code defining fitness_function.

    Returns:
        The compiled fitness_function callable.

    Raises:
        OptimizationError: If the code cannot be compiled or doesn't define
                          fitness_function.
    """
    if not fitness_code or not fitness_code.strip():
        raise OptimizationError("Fitness function code is empty")

    safe_builtins = {**_SAFE_BUILTINS, "__import__": _safe_import}
    namespace = {
        "__builtins__": safe_builtins,
        "math": math,
        "np": np,
        "numpy": np,
    }

    try:
        exec(fitness_code, namespace)
    except SyntaxError as exc:
        raise OptimizationError(
            f"Syntax error in fitness function (line {exc.lineno}): {exc.msg}"
        ) from exc
    except Exception as exc:
        raise OptimizationError(
            f"Error compiling fitness function: {exc}"
        ) from exc

    if "fitness_function" not in namespace:
        raise OptimizationError(
            "Fitness code must define a function named 'fitness_function'"
        )

    fn = namespace["fitness_function"]
    if not callable(fn):
        raise OptimizationError("'fitness_function' is not callable")

    return fn


# ------------------------------------------------------------------
# Gene Space Builder
# ------------------------------------------------------------------

def build_gene_space(genes: list[dict]) -> tuple[list, list[str], Optional[list[int]]]:
    """
    Build PyGAD gene_space and gene_type from parsed gene definitions.

    Returns:
        - gene_space: list of dicts/lists for PyGAD
        - gene_type: list of type strings for PyGAD
        - enum_mappings: None (enum genes are mapped to integer indices)
    """
    gene_space = []
    gene_type = []

    for gene in genes:
        if gene["type"] == "int":
            gene_space.append({
                "low": gene["low"],
                "high": gene["high"] + 1,  # PyGAD uses exclusive upper bound for ints
            })
            gene_type.append(int)

        elif gene["type"] == "float":
            gene_space.append({
                "low": gene["low"],
                "high": gene["high"],
            })
            gene_type.append(float)

        elif gene["type"] == "enum":
            # Map enum options to integer indices
            gene_space.append(list(range(len(gene["options"]))))
            gene_type.append(int)

    return gene_space, gene_type, None


# ------------------------------------------------------------------
# Detect Multi-Objective
# ------------------------------------------------------------------

def _is_multi_objective(fitness_fn: Callable, genes: list[dict]) -> bool:
    """
    Probe the fitness function with a dummy solution to determine if it
    returns a tuple (multi-objective) or a single value (mono-objective).
    """
    dummy_solution = []
    for gene in genes:
        if gene["type"] == "int":
            dummy_solution.append(gene["low"])
        elif gene["type"] == "float":
            dummy_solution.append(gene["low"])
        elif gene["type"] == "enum":
            dummy_solution.append(0)

    try:
        result = fitness_fn(None, dummy_solution, 0)
        return isinstance(result, (tuple, list)) and len(result) > 1
    except Exception:
        # If the probe fails, assume mono-objective
        logger.warning(
            "Could not probe fitness function for multi-objective detection; "
            "assuming mono-objective"
        )
        return False


# ------------------------------------------------------------------
# OptimizationService
# ------------------------------------------------------------------

def load_genes_from_db(project_id: int, db) -> list[dict]:
    """Load gene definitions from the database and return them as parsed dicts."""
    from app.models.gene import Gene

    gene_rows = (
        db.query(Gene)
        .filter(Gene.project_id == project_id)
        .order_by(Gene.order)
        .all()
    )
    if not gene_rows:
        raise OptimizationError(
            "No genes found in the database for this project. "
            "Save the definition first."
        )
    return [gene_record_to_dict(g) for g in gene_rows]


class OptimizationService:
    """Runs genetic algorithm optimizations using PyGAD."""

    @staticmethod
    def run_optimization(
        fitness_code: str,
        project_id: int,
        db,
        num_iterations: int = 100,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> dict[str, Any]:
        """
        Run a genetic algorithm optimization.

        Args:
            fitness_code: Python source defining fitness_function.
            project_id: Project ID — genes are loaded from the genes table.
            db: SQLAlchemy session.
            num_iterations: Number of GA generations.
            on_progress: Optional callback(current_generation, total_generations).

        Returns:
            Dict with keys:
                - best_solutions: list of solution dicts
                - best_fitness: fitness value(s)
                - fitness_history: list of best fitness per generation
                - is_multi_objective: bool
                - pareto_front: list of dicts (only for multi-objective)
        """
        # Load genes from the database
        genes = load_genes_from_db(project_id, db)
        num_genes = len(genes)

        # Compile fitness function
        fitness_fn = compile_fitness_function(fitness_code)

        # Build gene space
        gene_space, gene_type_list, _ = build_gene_space(genes)

        # Detect multi-objective
        multi_objective = _is_multi_objective(fitness_fn, genes)

        # Track fitness history
        fitness_history = []

        def on_generation(ga):
            gen = ga.generations_completed
            if multi_objective:
                # For multi-objective, record the first objective's best
                best_fitness = ga.best_solutions_fitness
                if len(best_fitness) > 0:
                    if isinstance(best_fitness[0], (tuple, list)):
                        fitness_history.append([float(v) for v in best_fitness[0]])
                    else:
                        fitness_history.append(float(best_fitness[0]))
                else:
                    fitness_history.append(None)
            else:
                best = ga.best_solutions_fitness
                if len(best) > 0:
                    fitness_history.append(float(best[-1]))
                else:
                    fitness_history.append(None)

            if on_progress is not None:
                on_progress(gen, num_iterations)

        # Configure PyGAD
        ga_kwargs = {
            "num_generations": num_iterations,
            "num_parents_mating": 10,
            "sol_per_pop": 50,
            "num_genes": num_genes,
            "gene_space": gene_space,
            "gene_type": gene_type_list,
            "fitness_func": fitness_fn,
            "on_generation": on_generation,
            "suppress_warnings": True,
            "keep_elitism": 5,
            "crossover_type": "single_point",
            "mutation_type": "random",
            "mutation_percent_genes": 20,
            "parent_selection_type": "tournament",
            "K_tournament": 3,
        }

        if multi_objective:
            # Probe to determine number of objectives
            dummy = []
            for gene in genes:
                if gene["type"] == "int":
                    dummy.append(gene["low"])
                elif gene["type"] == "float":
                    dummy.append(gene["low"])
                elif gene["type"] == "enum":
                    dummy.append(0)
            try:
                result = fitness_fn(None, dummy, 0)
                num_objectives = len(result)
            except Exception:
                num_objectives = 2

            # Multi-objective: all objectives are maximized in PyGAD
            # (the fitness function should negate minimization objectives)
            ga_kwargs["parent_selection_type"] = "nsga2"

        try:
            ga = pygad.GA(**ga_kwargs)
            ga.run()
        except Exception as exc:
            raise OptimizationError(
                f"PyGAD optimization failed: {exc}"
            ) from exc

        # Extract results
        return _extract_results(ga, genes, multi_objective, fitness_history)


def _solution_to_dict(solution: list, genes: list[dict]) -> dict:
    """Convert a solution array to a labeled dict, resolving enum indices."""
    result = {}
    for i, gene in enumerate(genes):
        value = solution[i]
        if gene["type"] == "enum":
            idx = int(round(float(value)))
            idx = max(0, min(idx, len(gene["options"]) - 1))
            result[gene["name"]] = gene["options"][idx]
        elif gene["type"] == "int":
            result[gene["name"]] = int(round(float(value)))
        else:
            decimals = gene.get("decimals", 2)
            result[gene["name"]] = round(float(value), decimals)
    return result


def _extract_results(
    ga: pygad.GA,
    genes: list[dict],
    multi_objective: bool,
    fitness_history: list,
) -> dict[str, Any]:
    """Extract and format results from a completed GA run."""
    result = {
        "convergence": fitness_history,
        "is_multi_objective": multi_objective,
    }

    if multi_objective:
        population = ga.population
        compiled_fn = ga.fitness_func
        pareto_solutions = []
        for idx, sol in enumerate(population):
            try:
                fit = compiled_fn(ga, sol, idx)
                if isinstance(fit, (tuple, list)):
                    entry = _solution_to_dict(sol.tolist(), genes)
                    for i, v in enumerate(fit):
                        entry[f"objective_{i+1}"] = float(v)
                    pareto_solutions.append({"solution": entry, "fitness": [float(v) for v in fit]})
            except Exception:
                continue

        pareto_front = _extract_pareto_front(pareto_solutions)
        # Flatten to list of dicts with gene values + objective values
        result["pareto_front"] = [p["solution"] for p in pareto_front[:10]]
        result["top_solutions"] = [p["solution"] for p in pareto_front[:5]]
        result["best_fitness"] = [p["fitness"] for p in pareto_front[:5]]
    else:
        solution, fitness, _ = ga.best_solution()
        result["best_fitness"] = float(fitness)

        # Get top 5 solutions from final population
        population = ga.population
        compiled_fn = ga.fitness_func
        pop_fitness = []
        for idx, sol in enumerate(population):
            try:
                fit = compiled_fn(ga, sol, idx)
                pop_fitness.append((sol.tolist(), float(fit)))
            except Exception:
                continue

        pop_fitness.sort(key=lambda x: x[1], reverse=True)
        top5 = pop_fitness[:5]
        result["top_solutions"] = []
        for sol, fit in top5:
            entry = _solution_to_dict(sol, genes)
            entry["fitness"] = fit
            result["top_solutions"].append(entry)

    return result


async def sync_genes(project_id: int, genes_description: str, db, llm=None) -> None:
    """
    Use the LLM to generate SQL INSERT statements that populate the genes table.

    The LLM reads the genes_description and produces PostgreSQL INSERT
    statements (potentially using generate_series / CROSS JOIN for large
    combinatorial gene sets).  The SQL is validated for safety before execution.

    Silently clears genes if the description is empty or no LLM is available.
    """
    from sqlalchemy import text

    from app.models.gene import Gene

    # Always clear existing genes first
    db.query(Gene).filter(Gene.project_id == project_id).delete()

    if not genes_description or not genes_description.strip():
        db.commit()
        return

    if llm is None:
        logger.warning("sync_genes called without LLM for project %d; genes cleared", project_id)
        db.commit()
        return

    try:
        sql = await llm.generate_gene_sql(genes_description, project_id)
        logger.info("Executing LLM-generated gene SQL for project %d", project_id)
        db.execute(text(sql))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Gene SQL generation/execution failed for project %d: %s", project_id, exc)
        raise


def gene_record_to_dict(gene) -> dict:
    """Convert a Gene ORM row to the parsed-gene dict format used by services."""
    d: dict = {
        "name": gene.name,
        "type": gene.type,
        "description": gene.description or "",
    }
    if gene.type in ("int", "float"):
        d["low"] = gene.low
        d["high"] = gene.high
        if gene.decimals is not None:
            d["decimals"] = gene.decimals
        elif gene.type == "float":
            d["decimals"] = 2
    elif gene.type == "enum":
        d["options"] = (
            [o.strip() for o in gene.options.split(",") if o.strip()]
            if gene.options
            else []
        )
    return d


def _extract_pareto_front(solutions: list[dict]) -> list[dict]:
    """
    Extract the non-dominated (Pareto front) solutions.

    A solution is non-dominated if no other solution is better in all objectives.
    """
    if not solutions:
        return []

    front = []
    for i, candidate in enumerate(solutions):
        dominated = False
        for j, other in enumerate(solutions):
            if i == j:
                continue
            # Check if 'other' dominates 'candidate'
            # (all objectives at least as good, and at least one strictly better)
            at_least_as_good = all(
                o >= c for o, c in zip(other["fitness"], candidate["fitness"])
            )
            strictly_better = any(
                o > c for o, c in zip(other["fitness"], candidate["fitness"])
            )
            if at_least_as_good and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate)

    return front
