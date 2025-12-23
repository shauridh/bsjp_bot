import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = 'signals.db'

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                strategy TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                target_tp REAL NOT NULL,
                limit_sl REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            )
        ''')

def insert_signal(ticker, strategy, signal_date, entry_price, target_tp, limit_sl, status='PENDING'):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO signals (ticker, strategy, signal_date, entry_price, target_tp, limit_sl, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ticker, strategy, signal_date, entry_price, target_tp, limit_sl, status, datetime.now().isoformat()))

def get_signals(strategy=None, status=None, date=None):
    query = 'SELECT * FROM signals WHERE 1=1'
    params = []
    if strategy:
        query += ' AND strategy = ?'
        params.append(strategy)
    if status:
        query += ' AND status = ?'
        params.append(status)
    if date:
        query += ' AND signal_date = ?'
        params.append(date)
    with get_db() as conn:
        return conn.execute(query, params).fetchall()

def update_signal_status(signal_id, status):
    with get_db() as conn:
        conn.execute('UPDATE signals SET status = ? WHERE id = ?', (status, signal_id))
