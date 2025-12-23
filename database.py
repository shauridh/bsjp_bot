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

# Create tables
Base.metadata.create_all(engine)

def add_signal(code, price, tp, sl, date, time):
    session = SessionLocal()
    signal = Signal(code=code, price=price, tp=tp, sl=sl, date=date, time=time)
    session.add(signal)
    session.commit()
    session.close()

def get_pending_signals(date):
    session = SessionLocal()
    signals = session.query(Signal).filter_by(date=date, status=SignalStatus.PENDING).all()
    session.close()
    return signals

def update_signal_status(signal_id, status):
    session = SessionLocal()
    signal = session.query(Signal).filter_by(id=signal_id).first()
    if signal:
        signal.status = status
        session.commit()
    session.close()

def get_signals_by_date(date):
    session = SessionLocal()
    signals = session.query(Signal).filter_by(date=date).all()
    session.close()
    return signals
