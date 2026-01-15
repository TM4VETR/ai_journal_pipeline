"""
Initializes a Neo4j graph database with occupation data (KldB 2010).
"""

import os
import re

from dotenv import load_dotenv
import pandas as pd
from neo4j import GraphDatabase

from logger import logger

load_dotenv()

NEO4J_URI  = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASS = os.getenv("NEO4J_PASS")

INPUT_FILE = "oc/data/Gesamtberufsliste_der_BA.xlsx"
SHEET_NAME = "Gesamtberufsliste der BA"

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASS)
)

# =====================
# Cypher Query
# =====================
QUERY = """
MERGE (g:OccupationGroup {group_id: $group_id})

MERGE (o:Occupation {code: $code})
ON CREATE SET
    o.title = $title,
    o.label = $label

MERGE (o)-[:IN_GROUP]->(g)
"""

GROUP_RE = re.compile(r"B\s*(\d{5})-")

def extract_group_id(code: str) -> str | None:
    """
    Extracts 5-digit group id from 'B 32101-10600'
    """
    m = GROUP_RE.search(code)
    return m.group(1) if m else None


def process_input_file(session):
    """
    Processes the input Excel file and inserts occupations into Neo4j.
    """
    logger.info(f"Loading Excel file: {INPUT_FILE}")

    assert os.path.exists(INPUT_FILE), f"Input file not found: {INPUT_FILE}"

    df = pd.read_excel(
        INPUT_FILE,
        sheet_name=SHEET_NAME,
        skiprows=3,
        usecols=["Codenummer", "Bezeichnung neutral kurz"]
    )

    count = 0

    for i, row in df.iterrows():
        code  = str(row["Codenummer"]).strip()
        title = str(row["Bezeichnung neutral kurz"]).strip()

        if not code or not title:
            continue

        group_id = extract_group_id(code)
        if not group_id:
            logger.info(f"Could not extract group from code: {code}")
            continue

        label = f"{code}: {title}"

        session.run(
            QUERY,
            code=code,
            title=title,
            label=label,
            group_id=group_id
        )

        if (i + 1) % 100 == 0:
            logger.info(f"Inserted {i + 1} occupations...")

        count += 1

    logger.info(f"Inserted {count} occupations.")

def main():
    """
    Main function to initialize the occupation graph.
    """
    logger.info("Initializing occupation graph...")
    with driver.session() as session:
        process_input_file(session)
    logger.info("Initialized occupation graph.")

if __name__ == "__main__":
    main()
