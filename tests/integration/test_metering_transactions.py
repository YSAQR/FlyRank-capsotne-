from app.db.models.usage import UsageEvent, UsageType
from app.db.seed import DEMO_TENANT_ID, run_seed
from app.repositories.usage_repository import UsageRepository
from app.services.metering_service import MeteringService
from app.utils.hashing import canonical_hash
from sqlalchemy.orm import sessionmaker


def test_failed_transaction_leaves_no_usage(engine) -> None:
    Session = sessionmaker(bind=engine, future=True)
    bootstrap = Session()
    run_seed(bootstrap)
    bootstrap.close()
    session = Session()
    repo = UsageRepository(session)
    meter = MeteringService(repo)
    meter.record(
        tenant_id=DEMO_TENANT_ID,
        usage_type=UsageType.api_call,
        quantity=1,
        idempotency_key="rollback-key",
        request_hash=canonical_hash({"q": 1}),
    )
    session.flush()
    assert session.query(UsageEvent).filter(UsageEvent.idempotency_key == "rollback-key").count() == 1
    session.rollback()
    session.close()

    verify = Session()
    assert verify.query(UsageEvent).filter(UsageEvent.idempotency_key == "rollback-key").count() == 0
    verify.close()


def test_seed_is_repeatable(engine) -> None:
    from app.db.models.plan import Plan
    from app.db.seed import run_seed

    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    run_seed(session)
    run_seed(session)
    plans = session.query(Plan).count()
    assert plans == 2
    session.close()
