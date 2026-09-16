"""
STEP 6: The main routing agent.

A NOTE ON THE AGENT API
-----------------------
LangGraph's older `create_react_agent` API has been deprecated in favor of
LangChain's `create_agent` API.

The current recommended approach is:

    from langchain.agents import create_agent

This project uses `create_agent` because it is the current agent factory
recommended by the LangChain/LangGraph ecosystem.

ROUTING LOGIC
-------------
We don't hand-write if/else routing rules. Instead, the LLM itself decides
which tool to call based on:

1. Each tool's docstring/description
   (see tools/db_tools.py and tools/web_search_tool.py).
2. The system prompt below, which gives worked examples to reinforce the
   boundary between "structured data lookup" and "general knowledge".
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from tools.db_tools import (
    hospitals_db_tool,
    institutions_db_tool,
    restaurants_db_tool,
)
from tools.web_search_tool import web_search_tool

# Load API keys and other environment variables from .env.
load_dotenv()


SYSTEM_PROMPT = """You are a helpful assistant that answers questions about
Bangladesh using four tools:

1. institutions_db_tool — structured data about universities, colleges, and
   government institutions (names, locations, types).
2. hospitals_db_tool — structured data about hospitals (names, locations,
   beds, doctors, facilities).
3. restaurants_db_tool — structured data about restaurants (names,
   locations, cuisine, ratings).
4. web_search_tool — general knowledge: definitions, policy, history,
   culture — anything NOT found in the three databases above.

ROUTING RULES:
- If the question asks to COUNT, LIST, or FILTER specific hospitals,
  institutions, or restaurants (e.g. mentions a city, a rating threshold, a
  bed count, an institution type) -> use the matching DB tool.
- If the question asks "what is", "what is the role of", "explain", or asks
  about policy/history/culture/definitions -> use web_search_tool.
- Only call ONE tool per question unless the question genuinely has two
  distinct parts that need two different tools.
- Base your final answer ONLY on what the tool returned. If a tool returns
  no data, say so honestly instead of guessing.

WORKED EXAMPLES:
- "How many hospitals are in Dhaka?" -> hospitals_db_tool
- "List restaurants in Chittagong with a rating above 4." -> restaurants_db_tool
- "What government universities are in Sylhet?" -> institutions_db_tool
- "What is the role of DGHS in Bangladesh?" -> web_search_tool
- "What is Bangladesh's national health policy?" -> web_search_tool
"""


def build_agent():
    """
    Creates and returns a ready-to-invoke LangChain agent with all four
    tools registered and the routing system prompt attached.
    """

    # Gemini is used as the main routing/tool-calling LLM.
    # GEMINI_API_KEY is loaded automatically from the environment.
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("AGENT_MODEL", "gemini-3.6-flash"),
        temperature=0,
    )

    # Register all tools that the agent is allowed to use.
    tools = [
        institutions_db_tool,
        hospitals_db_tool,
        restaurants_db_tool,
        web_search_tool,
    ]

    # Current LangChain agent API.
    #
    # `system_prompt` replaces the old `prompt` parameter used by
    # `create_react_agent`.
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


def ask(agent, question: str) -> dict:
    """
    Sends one question to the agent and returns the full result dict
    (including the tool-call trace, useful for STEP 7 testing/debugging).
    """

    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]}
    )

    return result


def final_answer_text(result: dict) -> str:
    """Extract only the visible text from the final assistant message."""

    content = result["messages"][-1].content

    # Gemini may return the response as a list of content blocks.
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                # Get only the actual text.
                text = block.get("text")

                if text:
                    return text.strip()

        return ""

    # If the response is already a normal string, return it directly.
    return str(content).strip()
