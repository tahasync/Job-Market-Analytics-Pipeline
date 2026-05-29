import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Tahan\AppData\Local\Temp\n8n_db.sqlite"
c = sqlite3.connect(db)
print("=== workflow_entity ===")
for row in c.execute(
    "SELECT id, name, active, activeVersionId, versionId, triggerCount FROM workflow_entity"
):
    print(row)
print("=== publish history ===")
for row in c.execute("SELECT * FROM workflow_publish_history LIMIT 10"):
    print(row)
print("=== published version ===")
for row in c.execute("SELECT * FROM workflow_published_version LIMIT 10"):
    print(row)
print("=== workflow_history (latest Taha) ===")
for row in c.execute(
    "SELECT versionId, workflowId, createdAt FROM workflow_history WHERE workflowId='TahaJobMarketAlert2026' ORDER BY createdAt DESC LIMIT 5"
):
    print(row)
print("=== published columns ===")
cols = [r[1] for r in c.execute("PRAGMA table_info(workflow_entity)")]
print(cols)
for col in cols:
    if "publish" in col.lower() or "version" in col.lower():
        print(col)
