from app.db.models.monthly_summary import MonthlyUsageSummary
from app.jobs.monthly_usage_job import reconcile_month
from app.utils.period import utc_month_bounds
from sqlalchemy.orm import sessionmaker
from tests.conftest import generate_body


def test_monthly_job_is_idempotent(client, engine, auth_headers) -> None:
    client.post("/generate", headers={**auth_headers, "Idempotency-Key": "job-1"}, json=generate_body())
    Session = sessionmaker(bind=engine, future=True)
    start, end = utc_month_bounds()
    session = Session()
    first = reconcile_month(session, start, end)
    session.close()
    session = Session()
    second = reconcile_month(session, start, end)
    rows = session.query(MonthlyUsageSummary).all()
    session.close()
    assert first == second
    assert len(rows) >= 1
    demo_rows = [r for r in rows if str(r.tenant_id) == "11111111-1111-1111-1111-111111111111"]
    assert len(demo_rows) == 1
    assert demo_rows[0].api_calls == 1
    assert demo_rows[0].ai_tokens == 235
    assert demo_rows[0].cost_nano_usd == 1_791_000
