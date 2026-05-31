import sqlite3
import json
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'resilience.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vector      TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            risk_score  REAL,
            risk_level  TEXT,
            logs        TEXT,
            metrics     TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            cpu_pct     REAL,
            mem_pct     REAL,
            net_conns   INTEGER,
            open_ports  TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("[DB] Database initialized.")

def save_scan(vector, result):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO scans (vector, timestamp, risk_score, risk_level, logs, metrics)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        vector,
        datetime.datetime.utcnow().isoformat(),
        result.get('risk_score', 0),
        result.get('risk_level', 'UNKNOWN'),
        json.dumps(result.get('logs', [])),
        json.dumps(result.get('metrics', {}))
    ))
    conn.commit()
    conn.close()

def get_scan_history(limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        SELECT id, vector, timestamp, risk_score, risk_level
        FROM scans
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as total FROM scans')
    total = c.fetchone()['total']
    c.execute('SELECT AVG(risk_score) as avg_score FROM scans')
    avg = c.fetchone()['avg_score'] or 0
    c.execute('''
        SELECT vector, AVG(risk_score) as avg_score, COUNT(*) as count
        FROM scans GROUP BY vector
    ''')
    by_vector = [dict(r) for r in c.fetchall()]
    c.execute('''
        SELECT risk_level, COUNT(*) as count
        FROM scans GROUP BY risk_level
    ''')
    by_level = [dict(r) for r in c.fetchall()]
    conn.close()
    return {
        'total_scans': total,
        'avg_risk_score': round(avg, 1),
        'by_vector': by_vector,
        'by_level': by_level
    }
