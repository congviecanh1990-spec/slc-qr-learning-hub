"""Kiểm tra phép ghép nhật ký quét và phiên xem, không cần Flask hoặc tài khoản Google.
Chạy: python tests/test_combined_reporting_sql.py (cần SQLAlchemy).
"""
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, create_engine, select, and_, or_, literal, union_all
from sqlalchemy.orm import Session, aliased, declarative_base

Base = declarative_base()
class Scan(Base):
    __tablename__ = 'scan_logs'
    id = Column(Integer, primary_key=True)
    qr_id = Column(Integer)
    participant_code = Column(String)
    class_code = Column(String)
    role = Column(String)
    scanned_at = Column(DateTime)

class Watch(Base):
    __tablename__ = 'watch_sessions'
    id = Column(Integer, primary_key=True)
    qr_id = Column(Integer)
    participant_code = Column(String)
    class_code = Column(String)
    role = Column(String)
    started_at = Column(DateTime)

class Qr(Base):
    __tablename__ = 'qr_codes'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer)


def make_query():
    ref = aliased(Scan)
    latest_scan = (select(ref.id)
        .where(ref.role == 'SV', ref.qr_id == Watch.qr_id,
               ref.participant_code == Watch.participant_code,
               or_(ref.class_code == Watch.class_code,
                   and_(ref.class_code.is_(None), Watch.class_code.is_(None))),
               ref.scanned_at <= Watch.started_at,
               ref.scanned_at >= Watch.started_at - timedelta(days=1))
        .order_by(ref.scanned_at.desc(), ref.id.desc()).limit(1)
        .correlate(Watch).scalar_subquery())
    scans = (select(Scan.id.label('scan_id'), Watch.id.label('watch_id'), Scan.scanned_at.label('stamp'))
        .select_from(Scan).outerjoin(Watch, and_(Watch.role == 'SV', latest_scan == Scan.id))
        .join(Qr, Scan.qr_id == Qr.id).where(Scan.role == 'SV'))
    orphans = (select(literal(None).label('scan_id'), Watch.id.label('watch_id'), Watch.started_at.label('stamp'))
        .select_from(Watch).outerjoin(Scan, Scan.id == latest_scan)
        .join(Qr, Watch.qr_id == Qr.id).where(Watch.role == 'SV', Scan.id.is_(None)))
    return union_all(scans, orphans)


def run():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    at = datetime(2026, 10, 19, 8, 0)
    with Session(engine) as db:
        db.add_all([
            Qr(id=1, owner_id=1),
            Scan(id=1, qr_id=1, participant_code='SV01', class_code='L1', role='SV', scanned_at=at),
            # 1 lượt quét playlist, 2 video phát: phải hiện 2 dòng, không hiện dòng quét riêng.
            Watch(id=11, qr_id=1, participant_code='SV01', class_code='L1', role='SV', started_at=at + timedelta(seconds=5)),
            Watch(id=12, qr_id=1, participant_code='SV01', class_code='L1', role='SV', started_at=at + timedelta(seconds=13)),
            # 1 lượt quét chưa xem: 1 dòng.
            Scan(id=2, qr_id=1, participant_code='SV02', class_code='L1', role='SV', scanned_at=at + timedelta(minutes=2)),
            # Dữ liệu xem cũ không có log quét ghép được: vẫn phải hiện 1 dòng.
            Watch(id=13, qr_id=1, participant_code='SV03', class_code='L1', role='SV', started_at=at + timedelta(hours=1)),
            # Quét của một người khác không thể gán nhầm vào phiên xem.
            Scan(id=3, qr_id=1, participant_code='SV04', class_code='L1', role='SV', scanned_at=at + timedelta(minutes=3)),
        ])
        db.commit()
        rows = db.execute(make_query()).all()
        assert len(rows) == 5, rows
        assert [(x.scan_id, x.watch_id) for x in rows if x.scan_id == 1] == [(1, 11), (1, 12)]
        assert any(x.scan_id == 2 and x.watch_id is None for x in rows)
        assert any(x.scan_id is None and x.watch_id == 13 for x in rows)
        assert any(x.scan_id == 3 and x.watch_id is None for x in rows)
        assert len(db.execute(select(Scan.id).where(Scan.role == 'SV')).all()) == 3
        print('PASS: QR playlist, chưa xem, dữ liệu cũ và không ghép nhầm sinh viên')


if __name__ == '__main__':
    run()
