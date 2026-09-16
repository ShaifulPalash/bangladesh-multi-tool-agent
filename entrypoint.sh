#!/bin/sh
# Runs once at container startup:
#   1. If the SQLite databases don't exist yet (e.g. first run, or a fresh
#      volume), download the datasets and build them.
#   2. Then start the Streamlit app.
#
# This means `docker compose up` alone is enough to go from nothing to a
# running chat UI — no separate manual steps required inside the container.

set -e

if [ ! -f "db/hospitals.db" ] || [ ! -f "db/institutions.db" ] || [ ! -f "db/restaurants.db" ]; then
    echo "Databases not found — downloading datasets and building SQLite DBs..."
    python scripts/download_and_inspect.py
    python scripts/build_databases.py
else
    echo "Databases already exist, skipping build step."
fi

echo "Starting Streamlit..."
exec streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0
