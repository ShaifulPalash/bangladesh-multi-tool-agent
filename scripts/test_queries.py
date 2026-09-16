"""
STEP 7: Test the agent on the representative example queries from the
project brief, printing which tool got called (the routing decision) and
the final natural-language answer for each.

Run with:  python scripts/test_queries.py
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

from agent.main_agent import ask, build_agent, final_answer_text  # noqa: E402

# ^ import must come after load_dotenv() above — see main.py for why.

TEST_CASES = [
    ("How many hospitals are in Dhaka?", "hospitals_db_tool"),
    ("List restaurants in Chittagong with a rating above 4.", "restaurants_db_tool"),
    ("What government universities are in Sylhet?", "institutions_db_tool"),
    ("What is the role of DGHS in Bangladesh?", "web_search_tool"),
    ("What is Bangladesh's national health policy?", "web_search_tool"),
]


def get_called_tools(result: dict) -> list:
    called = []
    for msg in result["messages"]:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            called.extend(call["name"] for call in tool_calls)
    return called


def main():
    agent = build_agent()

    for question, expected_tool in TEST_CASES:
        print("\n" + "=" * 70)
        print("QUESTION:", question)
        print("EXPECTED TOOL:", expected_tool)

        result = ask(agent, question)
        called_tools = get_called_tools(result)

        print("ACTUAL TOOL(S) CALLED:", called_tools)
        match = expected_tool in called_tools
        print("ROUTING CORRECT:", "YES" if match else "NO -- check the tool descriptions/system prompt")

        print("ANSWER:", final_answer_text(result))


if __name__ == "__main__":
    main()
