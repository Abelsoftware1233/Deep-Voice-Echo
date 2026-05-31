from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import sqlite3
import json
import datetime
import threading

from modules.scanner import run_full_scan, run_vector_scan
from modules.database import init_db, save_scan, get_scan_history, get_stats

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# ── Init database on startup ──
init_db()

# ── Serve frontend ──
@app.route('/')
def index():
    return render_template('index.html')

# ── API: Run full or vector-specific scan ──
@app.route('/api/scan', methods=['POST'])
def api_scan():
    data = request.get_json(force=True)
    vector = data.get('vector', 'full')
    try:
        if vector == 'full':
            result = run_full_scan()
        else:
            result = run_vector_scan(vector)
        save_scan(vector, result)
        return jsonify({'status': 'ok', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ── API: Get scan history ──
@app.route('/api/history', methods=['GET'])
def api_history():
    limit = int(request.args.get('limit', 20))
    rows = get_scan_history(limit)
    return jsonify({'status': 'ok', 'history': rows})

# ── API: Get aggregated stats ──
@app.route('/api/stats', methods=['GET'])
def api_stats():
    stats = get_stats()
    return jsonify({'status': 'ok', 'stats': stats})

# ── API: Live system snapshot (no DB write) ──
@app.route('/api/snapshot', methods=['GET'])
def api_snapshot():
    from modules.scanner import system_snapshot
    snap = system_snapshot()
    return jsonify({'status': 'ok', 'snapshot': snap})

if __name__ == '__main__':
    print("=" * 50)
    print("  AI-Resilience Threat Simulator")
    print("  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
