"""
Streamlit chat UI for the Multi-Tool Bangladesh Agent.

This is a thin UI layer on top of the same agent/tools code used by main.py.

It:
  - Lets you ask questions in a chat box.
  - Shows the agent's tool calls in a collapsible "Tool trace" section.
  - Keeps chat history during the current browser session.

RUN LOCALLY:
    pip install -r requirements.txt
    cp .env.example .env   # fill in GEMINI_API_KEY
    python scripts/download_and_inspect.py
    python scripts/build_databases.py
    streamlit run streamlit_app.py

RUN VIA DOCKER COMPOSE:
    docker compose up --build
    (open http://localhost:8501)
"""

import os

import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env before importing the agent.
load_dotenv()

from agent.main_agent import ask, build_agent, final_answer_text  # noqa: E402

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Bangladesh Multi-Tool Agent",
    page_icon="🇧🇩",
    layout="centered",
)

st.title("🇧🇩 Bangladesh Multi-Tool AI Agent")
st.caption(
    "Ask about hospitals, institutions, restaurants, or general knowledge."
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------


@st.cache_resource(show_spinner="Starting the agent...")
def get_agent():
    """Create and cache the agent."""
    return build_agent()


def check_databases_exist() -> bool:
    """Check whether all required SQLite databases exist."""
    db_dir = os.path.join(os.path.dirname(__file__), "db")

    required_databases = [
        "institutions.db",
        "hospitals.db",
        "restaurants.db",
    ]

    return all(
        os.path.exists(os.path.join(db_dir, database))
        for database in required_databases
    )


def check_api_key() -> bool:
    """Check whether the Gemini API key is available."""
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


# ---------------------------------------------------------
# Startup checks
# ---------------------------------------------------------

if not check_api_key():
    st.error(
        "GEMINI_API_KEY was not found.\n\n"
        "Create a `.env` file from `.env.example`, add your Gemini API key, "
        "and restart the app."
    )
    st.stop()


if not check_databases_exist():
    st.error(
        "The SQLite databases have not been built yet."
    )

    st.code(
        "python scripts/download_and_inspect.py\n"
        "python scripts/build_databases.py"
    )

    st.stop()


# ---------------------------------------------------------
# Create the agent
# ---------------------------------------------------------

agent = get_agent()


# ---------------------------------------------------------
# Chat history
# ---------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Display previous conversation.
for turn in st.session_state.chat_history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

        # Show tool calls only when available.
        if turn.get("tool_trace"):
            with st.expander("Tool trace"):
                for call in turn["tool_trace"]:
                    st.code(
                        f"{call['name']}({call['args']})",
                        language="python",
                    )


# ---------------------------------------------------------
# Example questions
# ---------------------------------------------------------

st.write("**Try an example:**")

example_columns = st.columns(2)

examples = [
    "How many hospitals are in Dhaka?",
    "List restaurants in Chittagong with a rating above 4.",
    "How many institutions are there in Sylhet?",
    "What is the role of DGHS in Bangladesh?",
]

clicked_example = None

for index, example in enumerate(examples):
    if example_columns[index % 2].button(
        example,
        use_container_width=True,
    ):
        clicked_example = example


# ---------------------------------------------------------
# Chat input
# ---------------------------------------------------------

user_input = st.chat_input(
    "Ask a question about Bangladesh..."
)

question = clicked_example or user_input


# ---------------------------------------------------------
# Process the question
# ---------------------------------------------------------

if question:
    # Save and display the user's question.
    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    # Generate the agent's answer.
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = ask(agent, question)

            # Convert Gemini/LangChain's response into clean text.
            answer = final_answer_text(result)

            # Collect tool calls for the optional trace.
            tool_trace = []

            for message in result["messages"]:
                tool_calls = getattr(message, "tool_calls", None)

                if tool_calls:
                    tool_trace.extend(tool_calls)

        # Display only the clean answer.
        st.markdown(answer)

        # Keep the technical tool information hidden inside an expander.
        if tool_trace:
            with st.expander("Tool trace"):
                for call in tool_trace:
                    st.code(
                        f"{call['name']}({call['args']})",
                        language="python",
                    )

    # Save the assistant's answer.
    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": answer,
            "tool_trace": tool_trace,
        }
    )
