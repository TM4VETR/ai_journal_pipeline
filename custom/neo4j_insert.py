"""
Linking a document to occupations (nodes) in Neo4j based on job IDs found.
"""

import os
import json
import re

from neo4j import GraphDatabase
from dotenv import load_dotenv

from logger import logger
from utility import extract_doc_id

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASS")

driver = GraphDatabase.driver(uri, auth=(user, password))

GROUP_RE = re.compile(r"^(\d{5})")


def extract_group_id(job_id: str) -> str | None:
    """
    Extract first 5 digits from job id, e.g.
    '32242' -> '32242'
    """
    m = GROUP_RE.match(job_id)
    return m.group(1) if m else None


QUERY = """
MERGE (d:Document {id: $doc_id})
MERGE (g:OccupationGroup {group_id: $group_id})
MERGE (d)-[:MENTIONS]->(g)
"""


def main(project_dir: str) -> None:
    """
    Main function to link document to occupation groups.
    :param project_dir: Project directory.
    """
    doc_id = extract_doc_id(project_dir)

    job_ids_file = os.path.join(project_dir, "job_ids.json")
    if not os.path.exists(job_ids_file):
        raise FileNotFoundError(job_ids_file)

    with open(job_ids_file, encoding="utf-8") as f:
        data = json.load(f)

    job_ids = data.get("job_ids", [])

    with driver.session() as session:
        for job_id in job_ids:
            try:
                job_id = str(job_id).strip()
                group_id = extract_group_id(job_id)

                if not group_id:
                    logger.warning(f"Could not extract group from job_id: {job_id}")
                    continue

                session.run(
                    QUERY,
                    doc_id=doc_id,
                    group_id=group_id
                )
            except Exception as e:
                logger.error(f"Error linking document to job id {job_id}: {e}")

    logger.info(
        f"Linked document {doc_id} to {len(job_ids)} occupation groups."
    )


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
