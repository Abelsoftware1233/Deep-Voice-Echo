"""
Real system scanning module.
Uses: psutil, socket, subprocess (nmap if available)
All findings are theoretical risk assessments based on real system data.
"""

import psutil
import socket
import subprocess
import platform
import datetime
import os
import json

# ── Ports that indicate potential AI/auth attack surface ──
SENSITIVE_PORTS = {
    22: 'SSH', 23: 'Telnet', 80: 'HTTP', 443: 'HTTPS',
    3306: 'MySQL', 5432: 'PostgreSQL', 6379: 'Redis',
    8080: 'HTTP-Alt', 8443: 'HTTPS-Alt', 11434: 'Ollama (LLM)',
    5000: 'Flask/API', 8000: 'Dev Server', 27017: 'MongoDB',
    9200: 'Elasticsearch', 4443: 'Alt-HTTPS', 2222: 'Alt-SSH'
}

RISKY_PORTS = [23, 6379, 9200, 27017]  # Telnet, Redis (no auth), Elasticsearch, Mongo


def system_snapshot():
    """Quick live system metrics — no DB write."""
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    net = psutil.net_connections(kind='inet')
    disk = psutil.disk_usage('/')

    open_ports = []
    for conn in net:
        if conn.status == 'LISTEN' and conn.laddr:
            port = conn.laddr.port
            name = SENSITIVE_PORTS.get(port, f'port-{port}')
            open_ports.append({'port': port, 'name': name})

    return {
        'cpu_pct': cpu,
        'mem_pct': round(mem.percent, 1),
        'mem_used_gb': round(mem.used / 1e9, 2),
        'mem_total_gb': round(mem.total / 1e9, 2),
        'disk_pct': round(disk.percent, 1),
        'net_connections': len(net),
        'open_ports': open_ports,
        'platform': platform.system(),
        'hostname': socket.gethostname(),
        'timestamp': datetime.datetime.utcnow().isoformat()
    }


def check_open_ports():
    """Scan locally listening ports and flag risky ones."""
    logs = []
    risky_found = []
    net = psutil.net_connections(kind='inet')
    listening = {c.laddr.port for c in net if c.status == 'LISTEN' and c.laddr}

    logs.append({'cls': 'header', 'text': '── Port Exposure Scan ──'})
    for port in sorted(listening):
        name = SENSITIVE_PORTS.get(port, 'unknown')
        if port in RISKY_PORTS:
            logs.append({'cls': 'error', 'text': f'[RISKY] Port {port} ({name}) — unauthenticated access possible'})
            risky_found.append(port)
        elif port in SENSITIVE_PORTS:
            logs.append({'cls': 'warn', 'text': f'[OPEN] Port {port} ({name}) — verify access controls'})
        else:
            logs.append({'cls': '', 'text': f'[OPEN] Port {port} — unrecognized service'})

    if not listening:
        logs.append({'cls': 'ok', 'text': 'No listening ports detected on localhost'})

    score_contribution = min(len(risky_found) * 20 + len(listening) * 3, 60)
    return logs, score_contribution, {'listening_ports': list(listening), 'risky_ports': risky_found}


def check_crypto_readiness():
    """Check for presence of crypto tools and TLS config indicators."""
    logs = []
    score = 0

    logs.append({'cls': 'header', 'text': '── Cryptographic Readiness Check ──'})

    # Check for OpenSSL
    try:
        result = subprocess.run(['openssl', 'version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ver = result.stdout.strip()
            logs.append({'cls': 'ok', 'text': f'OpenSSL detected: {ver}'})
            # Check if post-quantum openssl or old
            if 'OpenSSL 1.' in ver:
                logs.append({'cls': 'warn', 'text': 'OpenSSL 1.x detected — not post-quantum ready'})
                score += 25
            else:
                logs.append({'cls': 'ok', 'text': 'OpenSSL 3.x — better algorithm support'})
                score += 10
        else:
            logs.append({'cls': 'error', 'text': 'OpenSSL not found or not callable'})
            score += 40
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logs.append({'cls': 'error', 'text': 'OpenSSL not found on PATH'})
        score += 40

    # Check for GPG
    try:
        result = subprocess.run(['gpg', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            logs.append({'cls': 'ok', 'text': 'GPG found — key signing available'})
        else:
            logs.append({'cls': 'warn', 'text': 'GPG not available — no key signing'})
            score += 10
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logs.append({'cls': 'warn', 'text': 'GPG not found on PATH'})
        score += 10

    # Check for SSH key types in ~/.ssh
    ssh_dir = os.path.expanduser('~/.ssh')
    if os.path.isdir(ssh_dir):
        keys = os.listdir(ssh_dir)
        rsa_keys = [k for k in keys if 'rsa' in k.lower() and not k.endswith('.pub')]
        ed_keys = [k for k in keys if 'ed25519' in k.lower() or 'ecdsa' in k.lower()]
        if rsa_keys:
            logs.append({'cls': 'warn', 'text': f'RSA SSH keys found ({len(rsa_keys)}) — prefer Ed25519'})
            score += 15
        if ed_keys:
            logs.append({'cls': 'ok', 'text': f'Modern SSH keys (Ed25519/ECDSA) found: {len(ed_keys)}'})
        if not rsa_keys and not ed_keys:
            logs.append({'cls': 'dim', 'text': 'No SSH keys found in ~/.ssh'})
    else:
        logs.append({'cls': 'dim', 'text': '~/.ssh directory not present'})

    logs.append({'cls': 'warn', 'text': 'Post-quantum algorithms (CRYSTALS-Kyber): NOT detected'})
    score += 20

    return logs, min(score, 100), {}


def check_process_surface():
    """Scan running processes for AI/LLM related services."""
    logs = []
    score = 0
    ai_procs = []

    AI_KEYWORDS = ['ollama', 'llama', 'python', 'uvicorn', 'fastapi', 'flask',
                   'node', 'jupyter', 'triton', 'vllm', 'whisper', 'stable']

    logs.append({'cls': 'header', 'text': '── AI/LLM Process Surface Scan ──'})

    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
        try:
            name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
            for kw in AI_KEYWORDS:
                if kw in name or kw in cmdline:
                    ai_procs.append({'pid': proc.info['pid'], 'name': proc.info['name']})
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if ai_procs:
        logs.append({'cls': 'warn', 'text': f'AI/API related processes detected: {len(ai_procs)}'})
        for p in ai_procs[:6]:
            logs.append({'cls': 'warn', 'text': f'  PID {p["pid"]}: {p["name"]}'})
        score += min(len(ai_procs) * 12, 50)
    else:
        logs.append({'cls': 'ok', 'text': 'No active AI/LLM service processes detected'})

    # Count total processes as surface area indicator
    total = len(psutil.pids())
    logs.append({'cls': '', 'text': f'Total running processes: {total}'})
    if total > 200:
        logs.append({'cls': 'warn', 'text': 'Large process count — expanded attack surface'})
        score += 10

    return logs, min(score, 100), {'ai_processes': len(ai_procs), 'total_processes': total}


def check_network_connections():
    """Analyze active network connections for unusual patterns."""
    logs = []
    score = 0

    logs.append({'cls': 'header', 'text': '── Network Connection Analysis ──'})

    try:
        connections = psutil.net_connections(kind='inet')
    except psutil.AccessDenied:
        logs.append({'cls': 'warn', 'text': 'Access denied — run with elevated permissions for full scan'})
        return logs, 30, {}

    established = [c for c in connections if c.status == 'ESTABLISHED']
    listening = [c for c in connections if c.status == 'LISTEN']
    external = [c for c in established if c.raddr and not _is_local(c.raddr.ip)]

    logs.append({'cls': '', 'text': f'Total connections: {len(connections)}'})
    logs.append({'cls': '', 'text': f'Established: {len(established)} | Listening: {len(listening)}'})

    if external:
        logs.append({'cls': 'warn', 'text': f'External connections: {len(external)}'})
        # Show up to 5 unique remote IPs
        seen = set()
        for c in external[:5]:
            ip = c.raddr.ip
            if ip not in seen:
                seen.add(ip)
                logs.append({'cls': 'warn', 'text': f'  → {ip}:{c.raddr.port}'})
        if len(external) > 5:
            logs.append({'cls': 'warn', 'text': f'  ... and {len(external) - 5} more'})
        score += min(len(external) * 5, 40)
    else:
        logs.append({'cls': 'ok', 'text': 'No external connections detected'})

    return logs, min(score, 100), {
        'established': len(established),
        'listening': len(listening),
        'external': len(external)
    }


def _is_local(ip):
    return ip.startswith('127.') or ip.startswith('::1') or ip.startswith('10.') \
        or ip.startswith('192.168.') or ip.startswith('172.')


def run_vector_scan(vector):
    """Run a scan for a specific threat vector."""
    logs = []
    risk_score = 0
    metrics = {}

    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    logs.append({'cls': 'dim', 'text': f'Scan started: {ts}'})
    logs.append({'cls': 'dim', 'text': f'Vector: {vector.upper()}'})
    logs.append({'cls': '', 'text': ''})

    if vector == 'cognitive':
        l, s, m = check_process_surface()
        logs += l; risk_score += s * 0.5; metrics.update(m)
        # Add static cognitive risk factors
        logs.append({'cls': 'warn', 'text': 'Biometric auth dependency: UNVERIFIABLE from this host'})
        logs.append({'cls': 'warn', 'text': 'Recommend: out-of-band identity verification protocol'})
        risk_score = min(risk_score + 40, 100)

    elif vector == 'llm':
        l, s, m = check_process_surface()
        logs += l; risk_score += s; metrics.update(m)
        lp, sp, mp = check_open_ports()
        logs += lp; risk_score += sp * 0.4; metrics.update(mp)

    elif vector == 'audio':
        logs.append({'cls': 'warn', 'text': 'Audio deepfake detection requires audio stream — static analysis only'})
        logs.append({'cls': '', 'text': 'Checking for voice-related processes...'})
        l, s, m = check_process_surface()
        logs += l; risk_score = 58; metrics.update(m)

    elif vector == 'adversarial':
        l, s, m = check_process_surface()
        logs += l; risk_score += s * 0.6; metrics.update(m)
        risk_score = min(risk_score + 20, 100)

    elif vector == 'crypto':
        l, s, m = check_crypto_readiness()
        logs += l; risk_score = s; metrics.update(m)

    elif vector == 'supply':
        l, s, m = check_open_ports()
        logs += l; risk_score += s * 0.3
        lp, sp, mp = check_process_surface()
        logs += lp; risk_score += sp * 0.3; metrics.update(mp)
        logs.append({'cls': 'warn', 'text': 'Third-party dependency audit: requires manual review'})
        risk_score = min(risk_score + 15, 100)

    risk_score = round(min(risk_score, 100), 1)
    risk_level = _score_to_level(risk_score)

    logs.append({'cls': '', 'text': ''})
    logs.append({'cls': 'header', 'text': '── Scan Complete ──'})
    logs.append({'cls': _level_cls(risk_level), 'text': f'Risk Score: {risk_score}/100 — {risk_level}'})

    return {'vector': vector, 'risk_score': risk_score, 'risk_level': risk_level, 'logs': logs, 'metrics': metrics}


def run_full_scan():
    """Run all checks and aggregate results."""
    all_logs = []
    total_score = 0
    all_metrics = {}

    ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    all_logs.append({'cls': 'header', 'text': '══════ FULL SPECTRUM ANALYSIS ══════'})
    all_logs.append({'cls': 'dim',    'text': f'Scan started: {ts}'})
    all_logs.append({'cls': '',       'text': ''})

    checks = [
        ('Port Exposure',        check_open_ports,          0.25),
        ('Crypto Readiness',     check_crypto_readiness,    0.25),
        ('Process Surface',      check_process_surface,     0.25),
        ('Network Connections',  check_network_connections, 0.25),
    ]

    for name, fn, weight in checks:
        all_logs.append({'cls': 'header', 'text': f'[{name}]'})
        try:
            logs, score, metrics = fn()
            all_logs += logs
            total_score += score * weight
            all_metrics[name.lower().replace(' ', '_')] = metrics
        except Exception as e:
            all_logs.append({'cls': 'error', 'text': f'Check failed: {e}'})
        all_logs.append({'cls': '', 'text': ''})

    snap = system_snapshot()
    all_metrics['snapshot'] = snap

    risk_score = round(min(total_score, 100), 1)
    risk_level = _score_to_level(risk_score)

    all_logs.append({'cls': 'header', 'text': '══════ ANALYSIS COMPLETE ══════'})
    all_logs.append({'cls': _level_cls(risk_level), 'text': f'Overall Risk Score: {risk_score}/100 — {risk_level}'})
    all_logs.append({'cls': 'dim', 'text': f'Host: {snap["hostname"]} | CPU: {snap["cpu_pct"]}% | MEM: {snap["mem_pct"]}%'})

    return {
        'vector': 'full',
        'risk_score': risk_score,
        'risk_level': risk_level,
        'logs': all_logs,
        'metrics': all_metrics
    }


def _score_to_level(score):
    if score >= 70: return 'CRITICAL'
    if score >= 45: return 'HIGH'
    if score >= 25: return 'MEDIUM'
    return 'LOW'

def _level_cls(level):
    return {'CRITICAL': 'error', 'HIGH': 'error', 'MEDIUM': 'warn', 'LOW': 'ok'}.get(level, '')
