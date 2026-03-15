"""
LLM Service for Clear Route.

Dispatches chat requests to OpenAI, Anthropic, Gemini, or Ollama providers.
Includes the system prompt that instructs the AI to translate natural language
business optimization problems into genetic algorithm components.
"""

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Clear Route AI, an expert optimization consultant. Your ONLY job is to help users \
define three things about their optimization problem:

1. **Genes description** — the decision variables
2. **Objectives description** — what to optimize
3. **Constraints description** — business rules the solution must respect

These three descriptions are the SOLE input used by the system to automatically generate \
Python fitness functions, run genetic algorithms, and benchmark solutions. You do NOT \
generate code. You ONLY produce rich, self-contained descriptions.

## Conversation flow

- Ask clarifying questions to fully understand the business problem.
- Identify all decision variables, their types, ranges, and business meaning.
- Identify what the user wants to minimize or maximize and how it is computed.
- Identify hard constraints, soft constraints, penalties, and business rules.
- When you have enough information, output a JSON block (see below).
- After an initial definition, if the user requests changes, output an UPDATED JSON block \
  with the complete (not partial) descriptions reflecting all changes.

## What to capture in each description

### genes_description
Each gene (decision variable) must include:
- A clear name
- Type and boundaries: `[int](low, high)`, `[float](low, high, decimals=N)`, or `[enum](opt1, opt2, ...)`
- A detailed description explaining what this variable represents in the business context, \
  its unit of measure, how it relates to other genes, and any domain knowledge \
  (e.g. typical values, cost per unit, capacity, conversion rates).

When a gene pattern applies to multiple items (products, locations, time periods, etc.), \
you have two options:
1. **List every gene explicitly** — best for small sets (under ~20 genes).
2. **Describe the pattern clearly** — for large sets, describe the template and \
   enumerate all items/dimensions so the system can expand them programmatically. \
   Example: "For each of the 10 movies (M1..M10) × 8 quarters (Q1..Q8), create an \
   Assignment gene: [int](-1, 5) — platform assignment. -1=not released, 0-5=platform index." \
   The system will generate all 80 genes from this description automatically.

Make sure to always list the COMPLETE set of items/dimensions (e.g. all movie names, \
all quarter names) so the system knows exactly how many genes to generate.

Example:
```
- Workers_DayShift: [int](1, 30) - Number of workers on the day shift. Each worker costs $25/hour \
  and works 8 hours. Productivity is ~12 units/worker/hour. Day shift has a maximum capacity of 30.
- Workers_NightShift: [int](0, 20) - Number of workers on the night shift. Night workers cost $35/hour \
  (includes premium) and work 8 hours. Productivity drops to ~9 units/worker/hour due to fatigue.
- Marketing_Budget: [float](0.0, 50000.0, decimals=2) - Total marketing spend in USD. \
  Conversion rate is approximately 0.02 (2 customers per $100 spent). Diminishing returns \
  above $30,000.
- Supplier: [enum](local, overseas, hybrid) - Sourcing strategy. Local: $15/unit, 2-day lead time. \
  Overseas: $8/unit, 21-day lead time. Hybrid: $11/unit, 10-day lead time.
```

### objectives_description
Must include:
- Whether this is a minimization or maximization problem (or multi-objective).
- The exact business metric(s) being optimized — name, unit, and direction.
- The FORMULA or LOGIC for computing each objective from the gene values — step by step. \
  Include all constants, rates, conversion factors, lookup values, and mathematical \
  relationships. This must be detailed enough to write code from.
- For multi-objective: list each objective separately with its formula and direction.

Example:
```
Maximize total monthly profit (USD).

Formula:
  revenue = units_produced * selling_price_per_unit
  units_produced = (Workers_DayShift * 12 * 8 + Workers_NightShift * 9 * 8) * 22 working days
  selling_price_per_unit = $50
  labor_cost = (Workers_DayShift * 25 * 8 + Workers_NightShift * 35 * 8) * 22
  material_cost = units_produced * cost_per_unit_from_Supplier
  marketing_cost = Marketing_Budget
  new_customers = Marketing_Budget * 0.02
  extra_revenue = new_customers * 50  (average first purchase)
  profit = revenue + extra_revenue - labor_cost - material_cost - marketing_cost

Objectives:
- Monthly Profit: maximize — computed as profit above (in USD)
```

### constraints_description
Must include:
- Each constraint's name, description, and the exact condition or formula.
- Whether it is a hard constraint (solution is infeasible) or soft constraint (penalty).
- The penalty amount or approach for violations.
- All threshold values, limits, and business rules with their numeric values.

Example:
```
Constraints:
- Minimum Production: units_produced must be >= 5000 units/month. Hard constraint. \
  Penalty: -100000 * max(0, 5000 - units_produced) subtracted from fitness.
- Budget Limit: total costs (labor + material + marketing) must not exceed $200,000/month. \
  Hard constraint. Penalty: -50000 * max(0, total_cost - 200000).
- Worker Safety: total workers (day + night) must not exceed 45. Hard constraint. \
  Penalty: -100000 per excess worker.
- Lead Time: if Supplier is overseas, units_produced must be planned 21 days ahead \
  (no constraint on fitness, informational for interpretation).
```

## JSON output format

```json
{
    "genes_description": "... complete genes text ...",
    "objectives_description": "... complete objectives text with formulas ...",
    "constraints_description": "... complete constraints text with conditions and penalties ..."
}
```

Rules:
- The JSON block must be valid JSON enclosed in ```json and ``` markers.
- Each field must contain the COMPLETE description (not a diff or partial update).
- The descriptions must be self-contained — a code generator reading ONLY these three \
  fields must have all the information needed to write a working fitness function.
- Include all numeric constants, rates, formulas, relationships, and business logic inline.
- Do NOT include fitness_function_code — the system generates it automatically.
- Continue the conversation naturally around the JSON block, explaining what you defined.

## General guidelines

- Be conversational and helpful. Explain concepts in business terms.
- Ask one or two questions at a time, don't overwhelm the user.
- Probe for formulas, rates, costs, capacities, and relationships — these are critical.
- If the user is vague (e.g. "minimize cost"), ask exactly how cost is computed.
- If the user mentions items/categories, confirm the full list so you can expand genes.
- When presenting the structured output, explain it in plain language.
- For large gene sets, describe the pattern and list all items/dimensions explicitly. \
  The system will programmatically expand them into individual genes.
"""

FITNESS_FUNCTION_SYSTEM_PROMPT = """\
You are a Python code generator for PyGAD genetic algorithm fitness functions.

You are given three self-contained descriptions: genes, objectives, and constraints. \
These descriptions contain ALL the information you need — formulas, constants, rates, \
penalties, and business logic. Translate them faithfully into code.

Generate ONLY the raw Python function code. No explanations, no markdown, no code blocks.

Requirements:
- Function signature: def fitness_function(ga_instance, solution, solution_idx):
- `solution` is a list of gene values in the order the genes are defined.
- Map each solution index to its gene name with an inline comment.
- For enum genes, solution contains an integer index into the options list. \
  Map indices to their meaning using if/elif or a lookup dict.
- Implement the objective formula(s) EXACTLY as described in the objectives description. \
  Use all constants, rates, and conversion factors provided.
- Implement every constraint as described: apply the specified penalty formula for violations.
- For minimization objectives, negate the value (PyGAD maximizes by default).
- For multi-objective, return a tuple of floats (one per objective).
- Use only `math` module and Python builtins. No external imports.
- The function must be fully self-contained — all constants and lookup values inline.
"""


GENE_SQL_SYSTEM_PROMPT = """\
You generate PostgreSQL INSERT statements to populate a genes table from a text description \
of decision variables for a genetic algorithm optimization problem.

## Table schema

CREATE TABLE genes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    type VARCHAR NOT NULL,       -- must be 'int', 'float', or 'enum'
    low DOUBLE PRECISION,        -- lower boundary (for int/float types, NULL for enum)
    high DOUBLE PRECISION,       -- upper boundary (for int/float types, NULL for enum)
    decimals INTEGER,            -- decimal places (for float type only, NULL otherwise)
    options TEXT,                 -- comma-separated values (for enum type only, NULL otherwise)
    description TEXT,
    "order" INTEGER NOT NULL     -- 0-based position in the gene list
);

## Rules

- Generate ONLY INSERT INTO genes (...) VALUES (...); statements.
- The user message provides the project_id to use and the genes description.
- Set "order" sequentially starting from 0 across ALL rows produced.
- For int genes: set low, high; leave decimals and options as NULL.
- For float genes: set low, high, decimals (default 2 if not specified); leave options as NULL.
- For enum genes: set options as a single comma-separated string (e.g. 'ground,air,express'); \
  leave low, high, decimals as NULL.
- Use generate_series() and CROSS JOIN for large combinatorial gene sets \
  (e.g. 10 movies × 8 quarters = 80 genes).
- Return ONLY raw SQL. No markdown, no code fences, no explanation.

## Example 1 — simple genes:

INSERT INTO genes (project_id, name, type, low, high, decimals, options, description, "order") VALUES
(42, 'Workers', 'int', 1, 50, NULL, NULL, 'number of workers', 0),
(42, 'Budget', 'float', 0.0, 1.0, 2, NULL, 'budget fraction', 1),
(42, 'Method', 'enum', NULL, NULL, NULL, 'ground,air,express', 'shipping method', 2);

## Example 2 — cross-product with generate_series:

-- 10 movies × 8 quarters = 80 assignment genes
INSERT INTO genes (project_id, name, type, low, high, decimals, options, description, "order")
SELECT
    42,
    'Assignment_M' || m || '_Q' || q,
    'int',
    -1,
    5,
    NULL,
    NULL,
    'Platform assignment for Movie ' || m || ' in Quarter ' || q || '. -1=not released, 0-5=platform index',
    (m - 1) * 8 + (q - 1)
FROM generate_series(1, 10) AS m
CROSS JOIN generate_series(1, 8) AS q;

## Example 3 — mixed: static genes + generated genes:

INSERT INTO genes (project_id, name, type, low, high, decimals, options, description, "order") VALUES
(42, 'Total_Budget', 'float', 0.0, 100000.0, 2, NULL, 'Total budget in USD', 0);

INSERT INTO genes (project_id, name, type, low, high, decimals, options, description, "order")
SELECT
    42,
    'Hours_' || dept,
    'float',
    0.0,
    40.0,
    1,
    NULL,
    'Weekly hours allocated to ' || dept,
    row_number() OVER () -- continues ordering
FROM unnest(ARRAY['HR', 'Eng', 'Sales', 'Marketing', 'Finance']) AS dept;
"""


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMProviderError(LLMServiceError):
    """Raised when a provider-specific error occurs."""
    pass


class LLMConfigurationError(LLMServiceError):
    """Raised when the service is misconfigured."""
    pass


# ------------------------------------------------------------------
# SQL safety validation for LLM-generated gene SQL
# ------------------------------------------------------------------

import re as _re

_FORBIDDEN_SQL_PATTERNS = _re.compile(
    r"\b(DROP|ALTER|TRUNCATE|UPDATE|DELETE|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    _re.IGNORECASE,
)


def _validate_gene_sql(sql: str) -> None:
    """Ensure LLM-generated SQL only contains INSERT/SELECT statements."""
    match = _FORBIDDEN_SQL_PATTERNS.search(sql)
    if match:
        raise LLMProviderError(
            f"LLM-generated gene SQL contains forbidden keyword: {match.group()}"
        )
    # Must contain at least one INSERT
    if "INSERT" not in sql.upper():
        raise LLMProviderError("LLM-generated gene SQL does not contain any INSERT statements")


# ------------------------------------------------------------------
# Response cache — keyed on (provider, model, system_prompt, messages)
# ------------------------------------------------------------------
_LLM_CACHE: OrderedDict[str, str] = OrderedDict()
_LLM_CACHE_MAX_SIZE = 256


def _cache_key(provider: str, model: str, system_prompt: str, messages: list[dict]) -> str:
    """Build a deterministic hash key for an LLM request."""
    raw = json.dumps(
        {"provider": provider, "model": model, "system_prompt": system_prompt, "messages": messages},
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class LLMService:
    """
    Dispatches chat requests to the configured LLM provider.

    Supported providers: openai, anthropic, gemini, ollama.
    """

    SUPPORTED_PROVIDERS = ("openai", "anthropic", "gemini", "ollama")

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
    ):
        provider = provider.lower().strip()
        if provider not in self.SUPPORTED_PROVIDERS:
            raise LLMConfigurationError(
                f"Unsupported provider '{provider}'. "
                f"Supported: {', '.join(self.SUPPORTED_PROVIDERS)}"
            )

        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

        if provider != "ollama" and not api_key:
            raise LLMConfigurationError(
                f"API key is required for provider '{provider}'"
            )

    async def chat(self, messages: list[dict], system_prompt: str = SYSTEM_PROMPT, use_cache: bool = True) -> str:
        """
        Send a chat request to the configured provider.

        Results are cached by (provider, model, system_prompt, messages).
        Identical requests return the cached response without hitting the API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            system_prompt: System prompt to use (defaults to SYSTEM_PROMPT).
            use_cache: Whether to use the response cache (default True).

        Returns:
            The assistant's response text.

        Raises:
            LLMProviderError: If the provider request fails.
        """
        key = _cache_key(self.provider, self.model, system_prompt, messages)

        if use_cache and key in _LLM_CACHE:
            logger.debug("LLM cache hit for %s/%s", self.provider, self.model)
            _LLM_CACHE.move_to_end(key)
            return _LLM_CACHE[key]

        dispatch = {
            "openai": self._chat_openai,
            "anthropic": self._chat_anthropic,
            "gemini": self._chat_gemini,
            "ollama": self._chat_ollama,
        }
        handler = dispatch[self.provider]

        try:
            result = await handler(messages, system_prompt)
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.exception("LLM provider '%s' request failed", self.provider)
            raise LLMProviderError(
                f"Request to {self.provider} failed: {exc}"
            ) from exc

        if use_cache:
            _LLM_CACHE[key] = result
            if len(_LLM_CACHE) > _LLM_CACHE_MAX_SIZE:
                _LLM_CACHE.popitem(last=False)

        return result

    async def generate_fitness_function(
        self,
        genes_description: str,
        objectives_description: str,
        constraints_description: str,
    ) -> str:
        """
        Generate a PyGAD fitness function from the given optimization definitions.

        Returns the raw Python function code (no markdown).
        """
        user_message = (
            f"## Genes (decision variables — solution array in this order):\n{genes_description}\n\n"
            f"## Objectives (what to optimize — includes formulas and constants):\n{objectives_description}\n\n"
            f"## Constraints (conditions and penalties to apply):\n{constraints_description or 'No constraints.'}\n\n"
            "Generate the fitness function using ONLY the information above. "
            "All formulas, constants, and penalties are specified in the descriptions."
        )
        messages = [{"role": "user", "content": user_message}]
        code = await self.chat(messages, system_prompt=FITNESS_FUNCTION_SYSTEM_PROMPT)

        # Strip any accidental markdown fences the model might add
        code = code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            # Drop first and last fence lines
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            code = "\n".join(lines[start:end]).strip()

        return code

    async def generate_gene_sql(self, genes_description: str, project_id: int) -> str:
        """
        Use the LLM to generate SQL INSERT statements that populate the genes table.

        Returns raw SQL string ready for execution.
        Raises LLMProviderError if the call fails.
        """
        user_message = (
            f"project_id = {project_id}\n\n"
            f"Genes description:\n{genes_description}"
        )
        messages = [{"role": "user", "content": user_message}]
        raw = await self.chat(messages, system_prompt=GENE_SQL_SYSTEM_PROMPT)

        # Strip accidental markdown fences
        sql = raw.strip()
        if sql.startswith("```"):
            lines = sql.splitlines()
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            sql = "\n".join(lines[start:end]).strip()

        if not sql:
            raise LLMProviderError("LLM returned empty SQL for gene generation")

        # Safety check: only allow INSERT and SELECT statements
        _validate_gene_sql(sql)

        return sql

    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------

    async def _chat_openai(self, messages: list[dict], system_prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=0.7,
                max_tokens=4096,
            )
            return response.choices[0].message.content
        except Exception as exc:
            raise LLMProviderError(f"OpenAI API error: {exc}") from exc

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    async def _chat_anthropic(self, messages: list[dict], system_prompt: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)

        api_messages = []
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        try:
            response = await client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=api_messages,
                max_tokens=4096,
                temperature=0.7,
            )
            # Anthropic returns a list of content blocks
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            return "".join(text_parts)
        except Exception as exc:
            raise LLMProviderError(f"Anthropic API error: {exc}") from exc

    # ------------------------------------------------------------------
    # Gemini
    # ------------------------------------------------------------------

    async def _chat_gemini(self, messages: list[dict], system_prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)

        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )

        # Build Gemini chat history from messages (all but the last one)
        history = []
        for msg in messages[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history.append({"role": role, "parts": [msg["content"]]})

        try:
            chat = model.start_chat(history=history)
            # Send the last message
            last_message = messages[-1]["content"] if messages else ""
            response = await chat.send_message_async(last_message)
            return response.text
        except Exception as exc:
            raise LLMProviderError(f"Gemini API error: {exc}") from exc

    # ------------------------------------------------------------------
    # Ollama (local)
    # ------------------------------------------------------------------

    async def _chat_ollama(self, messages: list[dict], system_prompt: str) -> str:
        base_url = (self.base_url or "http://localhost:11434").rstrip("/")
        url = f"{base_url}/api/chat"

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(
                f"Ollama HTTP error {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMProviderError(
                f"Cannot connect to Ollama at {base_url}. "
                f"Is the server running? Error: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMProviderError(f"Ollama API error: {exc}") from exc
