import os
import vertexai
from vertexai.language_models import TextEmbeddingModel
from google.cloud import spanner
from config import config
from spanner_store import get_database, ensure_tables
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_and_execute_dml(db, sql_file_path):
    with open(sql_file_path, "r") as f:
        sql = f.read()

    # Find the DML section
    dml_start = sql.find("DML: SEED DATA")
    if dml_start == -1:
        logger.warning("Could not find DML section in schema file.")
        return

    dml_section = sql[dml_start:]
    statements = [s.strip() for s in dml_section.split(";") if s.strip()]
    statements = [s for s in statements if s.upper().startswith("INSERT")]

    def execute_inserts(transaction):
        for stmt in statements:
            try:
                transaction.execute_update(stmt)
            except Exception as e:
                # If AlreadyExists, we don't care, it's just seed data
                if "Already exists" not in str(e):
                    logger.warning(f"Failed to execute (might be duplicate): {stmt[:50]}... Error: {e}")

    db.run_in_transaction(execute_inserts)
    logger.info(f"Executed {len(statements)} seed DML statements.")

def backfill_embeddings():
    logger.info("Initializing Vertex AI with gemini-embedding-2 (text-embedding-004)...")
    vertexai.init(project=config.gcp_project_id, location=config.gcp_region)
    # text-embedding-004 is the model ID for "Gemini Embedding 2"
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    db = get_database()

    # 1. VideoSegments
    with db.snapshot() as snapshot:
        results = snapshot.execute_sql("SELECT SegmentId, AiSummary FROM VideoSegments WHERE AiSummary IS NOT NULL AND Embedding IS NULL")
        segments = list(results)

    if segments:
        logger.info(f"Computing embeddings for {len(segments)} VideoSegments...")
        def update_segments(transaction):
            for seg_id, summary in segments:
                emb = model.get_embeddings([summary])[0].values
                transaction.execute_update(
                    "UPDATE VideoSegments SET Embedding = @emb WHERE SegmentId = @id",
                    params={"emb": emb, "id": seg_id},
                    param_types={"emb": spanner.param_types.Array(spanner.param_types.FLOAT64), "id": spanner.param_types.STRING}
                )
        db.run_in_transaction(update_segments)
    
    # 2. Reports
    with db.snapshot() as snapshot:
        results = snapshot.execute_sql("SELECT ReportId, Description FROM Reports WHERE Description IS NOT NULL AND Embedding IS NULL")
        reports = list(results)

    if reports:
        logger.info(f"Computing embeddings for {len(reports)} Reports...")
        def update_reports(transaction):
            for rep_id, desc in reports:
                emb = model.get_embeddings([desc])[0].values
                transaction.execute_update(
                    "UPDATE Reports SET Embedding = @emb WHERE ReportId = @id",
                    params={"emb": emb, "id": rep_id},
                    param_types={"emb": spanner.param_types.Array(spanner.param_types.FLOAT64), "id": spanner.param_types.STRING}
                )
        db.run_in_transaction(update_reports)
    
    logger.info("Embeddings backfill completed.")

if __name__ == "__main__":
    logger.info("Ensuring Spanner Tables Exist (DDL)...")
    ensure_tables()
    
    sql_path = os.path.join(os.path.dirname(__file__), "spanner_schema_and_seed.sql")
    logger.info("Executing Spanner Seed (DML)...")
    db = get_database()
    try:
        parse_and_execute_dml(db, sql_path)
    except Exception as e:
        logger.error(f"Error seeding DB: {e}")

    logger.info("Backfilling Embeddings...")
    backfill_embeddings()
