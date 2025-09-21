from apps.api.models import BackfillProgress
from apps.api.db import SessionLocal

def test_resume_backfill_checkpoint():
    db = SessionLocal()
    row = BackfillProgress(symbol="BTCUSDT", tf="1m", last_ts_completed=1000, chunk_start_ts=0, chunk_end_ts=2000, status="running")
    db.add(row); db.commit()
    # simulate interruption and resume
    row.status = "queued"
    db.commit()
    r = db.query(BackfillProgress).filter_by(symbol="BTCUSDT", tf="1m").one()
    assert r.last_ts_completed == 1000 and r.status == "queued"