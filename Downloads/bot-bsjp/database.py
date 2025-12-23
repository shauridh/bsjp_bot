from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
import os

DB_PATH = os.getenv('DB_PATH', 'bsjp.db')
engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class SignalStatus(enum.Enum):
    PENDING = 'PENDING'
    WIN = 'WIN'
    LOSS = 'LOSS'

class Signal(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    tp = Column(Float, nullable=False)
    sl = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    status = Column(Enum(SignalStatus), default=SignalStatus.PENDING)
    time = Column(String, nullable=False)  # e.g. '15:45'
    strategy = Column(String, nullable=False, default='BSJP')  # 'BSJP' or 'BPJS'


# Migration: add strategy column if not exists
from sqlalchemy import inspect
def migrate_add_strategy_column():
    insp = inspect(engine)
    columns = [col['name'] for col in insp.get_columns('signals')]
    if 'strategy' not in columns:
        with engine.connect() as conn:
            conn.execute('ALTER TABLE signals ADD COLUMN strategy TEXT DEFAULT "BSJP"')

migrate_add_strategy_column()
Base.metadata.create_all(engine)


def add_signal(code, price, tp, sl, date, time, strategy='BSJP'):
    session = SessionLocal()
    signal = Signal(code=code, price=price, tp=tp, sl=sl, date=date, time=time, strategy=strategy)
    session.add(signal)
    session.commit()
    session.close()


def get_pending_signals(date, strategy=None):
    session = SessionLocal()
    query = session.query(Signal).filter_by(date=date, status=SignalStatus.PENDING)
    if strategy:
        query = query.filter_by(strategy=strategy)
    signals = query.all()
    session.close()
    return signals

def update_signal_status(signal_id, status):
    session = SessionLocal()
    signal = session.query(Signal).filter_by(id=signal_id).first()
    if signal:
        signal.status = status
        session.commit()
    session.close()


def get_signals_by_date(date, strategy=None):
    session = SessionLocal()
    query = session.query(Signal).filter_by(date=date)
    if strategy:
        query = query.filter_by(strategy=strategy)
    signals = query.all()
    session.close()
    return signals
