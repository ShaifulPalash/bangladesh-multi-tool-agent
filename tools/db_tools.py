"""
STEP 4: DB-specific LangChain tools.

HOW EACH TOOL WORKS (natural language -> SQL -> safe execution -> answer):

  1. The main agent calls a tool like `hospitals_db_tool` with the user's
     plain-English question (e.g. "How many hospitals are in Dhaka?").
  2. The tool asks a small LLM to write ONE SQLite SELECT query against
     the table's real schema (pulled live from the .db file, not hardcoded).
  3. `tools/sql_safety.py` validates the generated SQL is read-only-safe,
     adds a row LIMIT if missing, and executes it against the SQLite file
     opened in read-only mode.
  4. Python formats the database result directly. We do NOT send the result
     back to Gemini for summarization, which reduces Gemini API requests
     and token usage.

Each of the 3 concrete tools below is a thin wrapper around this same
factory function, pointed at a different database + table + description.
The description is what the agent's router reads to decide which tool
fits a given question, so it explicitly lists the kinds of questions each
tool is good for and (importantly) what it is NOT for, to reduce mis-routing.
"""

import os

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from tools.sql_safety import UnsafeSQLError, get_table_schema, run_read_only_query

DB_DIR = os.path.join(os.path.dirname(__file__), "..", "db")

def _get_sql_llm():
    """
    Create the Gemini client only when SQL generation is actually needed.

    Lazy initialization prevents importing this module from requiring
    the Gemini API key immediately.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        temperature=0,
    )

def _generate_sql(question: str, schema_sql: str, table_name: str) -> str:
    """Generate one safe SQLite SELECT query from the user's question."""
    prompt = f"""You are a SQLite expert. Given this table schema:

{schema_sql}

Write ONE single SQLite SELECT query that answers the user's question below.

Rules:
- Only query the table "{table_name}".
- Return ONLY the raw SQL, no markdown fences, no explanation.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, or any write statement.
- Use LIKE with wildcards for text/location matching (e.g. WHERE location LIKE '%Dhaka%')
  since location names in the data may have inconsistent spacing/case.

Question: {question}
SQL:"""

    sql_llm = _get_sql_llm()
    response = sql_llm.invoke(prompt)
    sql = response.content[0]["text"].strip()

    # Strip accidental markdown code fences if the model adds them anyway.
    sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql


def _format_result(columns: list, rows: list) -> str:
    """
    Format database results directly in Python.

    This replaces the previous Gemini-based result summarization step.
    It handles empty results, single-value results such as COUNT(*),
    and multi-row/multi-column results.
    """
    if not rows:
        return "I ran the query but found no matching records in the database."

    # Handle simple single-value results such as COUNT(*).
    if len(columns) == 1 and len(rows) == 1:
        value = rows[0][0]
        return f"Based on the database records, the answer is: {value}"

    # Handle list/table results without another LLM call.
    header = " | ".join(columns)
    lines = []

    for row in rows:
        values = [
            str(value) if value is not None else "N/A"
            for value in row
        ]
        lines.append(" | ".join(values))

    return f"{header}\n" + "\n".join(lines)


def _make_db_tool(db_filename: str, table_name: str):
    """
    Return a function that runs the full NL -> SQL -> execute -> format
    pipeline for one specific database and table.
    """
    db_path = os.path.join(DB_DIR, db_filename)

    def _run(question: str) -> str:
        schema_sql = get_table_schema(db_path, table_name)

        if not schema_sql:
            return (
                f"Database error: table '{table_name}' not found in {db_filename}. "
                f"Did you run scripts/build_databases.py?"
            )

        sql = _generate_sql(question, schema_sql, table_name)

        try:
            columns, rows = run_read_only_query(db_path, sql)
        except UnsafeSQLError as e:
            return f"I couldn't safely run that query ({e}). Try rephrasing the question."
        except Exception as e:
            return f"The database query failed: {e}. Try rephrasing the question."

        return _format_result(columns, rows)

    return _run


# ---------------------------------------------------------------------------
# The three concrete tools the main agent will register.
# ---------------------------------------------------------------------------

_institutions_runner = _make_db_tool("institutions.db", "institutions")
_hospitals_runner = _make_db_tool("hospitals.db", "hospitals")
_restaurants_runner = _make_db_tool("restaurants.db", "restaurants")


@tool
def institutions_db_tool(question: str) -> str:
    """Use this tool for questions about EDUCATIONAL and GOVERNMENT
    INSTITUTIONS in Bangladesh: universities, colleges, schools, government
    offices/agencies — their names, locations, types, and similar structured
    details. Examples: "What government universities are in Sylhet?",
    "List private colleges in Dhaka." Do NOT use this for hospitals or
    restaurants, and do NOT use this for general knowledge questions like
    policy or history — use the web search tool for those instead."""
    return _institutions_runner(question)


@tool
def hospitals_db_tool(question: str) -> str:
    """Use this tool for questions about HOSPITALS in Bangladesh: hospital
    names, locations, number of beds, doctors, facilities, and similar
    structured details. Examples: "How many hospitals are in Dhaka?",
    "Which hospitals in Chittagong have more than 100 beds?". Do NOT use this
    for institutions or restaurants, and do NOT use this for general
    healthcare-policy questions (e.g. "What is DGHS?") — use the web search
    tool for those instead."""
    return _hospitals_runner(question)


@tool
def restaurants_db_tool(question: str) -> str:
    """Use this tool for questions about RESTAURANTS in Bangladesh:
    restaurant names, locations, cuisine type, and ratings. Examples:
    "List restaurants in Chittagong with a rating above 4.",
    "What Thai restaurants are in Dhaka?". Do NOT use this for hospitals or
    institutions, and do NOT use this for general food-culture questions
    (e.g. "What is a popular Bangladeshi dish?") — use the web search tool
    for those instead."""
    return _restaurants_runner(question)
