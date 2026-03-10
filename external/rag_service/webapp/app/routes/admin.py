from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import aiosqlite

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs", response_class=HTMLResponse)
async def view_logs(request: Request):
    """Simple HTML dashboard for viewing chat logs."""
    db_path = request.app.state.web_settings.artifacts_dir / "chatlogs.sqlite3"
    
    if not db_path.exists():
        return HTMLResponse("<h1>No database found</h1><p>Start chatting first to create logs.</p>")
    
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        
        # Fetch data
        sessions = await (await db.execute(
            "SELECT * FROM sessions ORDER BY last_seen_at DESC LIMIT 20"
        )).fetchall()
        
        messages = await (await db.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT 50"
        )).fetchall()
        
        requests_data = await (await db.execute(
            "SELECT * FROM requests ORDER BY created_at DESC LIMIT 30"
        )).fetchall()
        
        # Stats
        stats = await (await db.execute("""
            SELECT 
                (SELECT COUNT(*) FROM sessions) as total_sessions,
                (SELECT COUNT(*) FROM messages WHERE role='user') as total_user_msgs,
                (SELECT COUNT(*) FROM messages WHERE role='assistant') as total_assistant_msgs,
                (SELECT COUNT(*) FROM requests WHERE status='ok') as successful_requests,
                (SELECT COUNT(*) FROM requests WHERE status='error') as failed_requests,
                (SELECT AVG(latency_ms) FROM requests WHERE latency_ms IS NOT NULL) as avg_latency_ms
        """)).fetchone()
    
    html = _build_dashboard_html(sessions, messages, requests_data, stats)
    return HTMLResponse(content=html)


@router.get("/logs/json")
async def logs_json(request: Request):
    """JSON API for logs."""
    db_path = request.app.state.web_settings.artifacts_dir / "chatlogs.sqlite3"
    
    if not db_path.exists():
        return {"sessions": [], "messages": [], "requests": []}
    
    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        
        sessions = [dict(row) for row in await (await db.execute(
            "SELECT * FROM sessions ORDER BY last_seen_at DESC LIMIT 100"
        )).fetchall()]
        
        messages = [dict(row) for row in await (await db.execute(
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT 200"
        )).fetchall()]
        
        requests_data = [dict(row) for row in await (await db.execute(
            "SELECT * FROM requests ORDER BY created_at DESC LIMIT 100"
        )).fetchall()]
    
    return {"sessions": sessions, "messages": messages, "requests": requests_data}


def _build_dashboard_html(sessions, messages, requests_data, stats) -> str:
    """Build the HTML dashboard."""
    
    # Stats section
    stats_html = ""
    if stats:
        avg_latency = f"{stats['avg_latency_ms']:.0f}ms" if stats['avg_latency_ms'] else "N/A"
        stats_html = f"""
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value">{stats['total_sessions'] or 0}</div><div class="stat-label">Sessions</div></div>
            <div class="stat-card"><div class="stat-value">{stats['total_user_msgs'] or 0}</div><div class="stat-label">User Messages</div></div>
            <div class="stat-card"><div class="stat-value">{stats['total_assistant_msgs'] or 0}</div><div class="stat-label">Assistant Messages</div></div>
            <div class="stat-card"><div class="stat-value">{stats['successful_requests'] or 0}</div><div class="stat-label">Successful</div></div>
            <div class="stat-card"><div class="stat-value">{stats['failed_requests'] or 0}</div><div class="stat-label">Failed</div></div>
            <div class="stat-card"><div class="stat-value">{avg_latency}</div><div class="stat-label">Avg Latency</div></div>
        </div>
        """
    
    # Sessions table
    sessions_rows = ""
    for s in sessions:
        ua = (s['user_agent'] or '')[:40] + ('...' if len(s['user_agent'] or '') > 40 else '')
        sessions_rows += f"""<tr>
            <td class="mono">{s['session_id'][:12]}...</td>
            <td>{_fmt_time(s['created_at'])}</td>
            <td>{_fmt_time(s['last_seen_at'])}</td>
            <td>{s['ip'] or '-'}</td>
            <td title="{_esc(s['user_agent'] or '')}">{_esc(ua) or '-'}</td>
        </tr>"""
    
    # Messages table
    messages_rows = ""
    for m in messages:
        content = (m['content'] or '')[:80] + ('...' if len(m['content'] or '') > 80 else '')
        messages_rows += f"""<tr>
            <td>{m['id']}</td>
            <td class="mono">{m['session_id'][:8]}...</td>
            <td class="role-{m['role']}">{m['role']}</td>
            <td title="{_esc(m['content'] or '')}">{_esc(content)}</td>
            <td>{_fmt_time(m['created_at'])}</td>
        </tr>"""
    
    # Requests table
    requests_rows = ""
    for r in requests_data:
        query = (r['query'] or '')[:40] + ('...' if len(r['query'] or '') > 40 else '')
        latency = f"{r['latency_ms']}ms" if r['latency_ms'] else '-'
        requests_rows += f"""<tr>
            <td class="mono">{r['request_id'][:8]}...</td>
            <td title="{_esc(r['query'] or '')}">{_esc(query)}</td>
            <td>{r['mode_requested']}</td>
            <td>{r['mode_used'] or '-'}</td>
            <td class="status-{r['status']}">{r['status']}</td>
            <td>{latency}</td>
            <td>{_fmt_time(r['created_at'])}</td>
        </tr>"""
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Chat Logs Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #e0e0e0; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #64ffda; margin-bottom: 20px; }}
        h2 {{ color: #bb86fc; margin: 30px 0 15px; font-size: 1.3rem; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: #64ffda; }}
        .stat-label {{ font-size: 0.85rem; color: #a0a0a0; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; background: rgba(0,0,0,0.2); border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        th {{ background: rgba(0,0,0,0.3); color: #64ffda; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
        tr:hover {{ background: rgba(255,255,255,0.03); }}
        .mono {{ font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; }}
        .role-user {{ color: #64b5f6; font-weight: 600; }}
        .role-assistant {{ color: #81c784; font-weight: 600; }}
        .status-ok {{ color: #4caf50; font-weight: 600; }}
        .status-error {{ color: #f44336; font-weight: 600; }}
        .status-started {{ color: #ff9800; font-weight: 600; }}
        .header {{ display: flex; align-items: center; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }}
        .nav-links {{ display: flex; gap: 15px; }}
        .nav-links a {{ color: #bb86fc; text-decoration: none; }}
        .nav-links a:hover {{ text-decoration: underline; }}
        .refresh-btn {{ background: #64ffda; color: #1a1a2e; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: 600; margin-left: auto; }}
        .refresh-btn:hover {{ background: #4cdfba; }}
        .empty {{ text-align: center; opacity: 0.6; padding: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Chat Logs Dashboard</h1>
            <div class="nav-links">
                <a href="/admin/logs/json" target="_blank">📥 JSON Export</a>
                <a href="/">💬 Back to Chat</a>
            </div>
            <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        </div>
        
        {stats_html}
        
        <h2>🗓️ Recent Sessions</h2>
        <table>
            <thead><tr><th>Session ID</th><th>Created</th><th>Last Seen</th><th>IP</th><th>User Agent</th></tr></thead>
            <tbody>{sessions_rows if sessions_rows else '<tr><td colspan="5" class="empty">No sessions yet</td></tr>'}</tbody>
        </table>
        
        <h2>💬 Recent Messages</h2>
        <table>
            <thead><tr><th>ID</th><th>Session</th><th>Role</th><th>Content</th><th>Time</th></tr></thead>
            <tbody>{messages_rows if messages_rows else '<tr><td colspan="5" class="empty">No messages yet</td></tr>'}</tbody>
        </table>
        
        <h2>📡 Recent Requests</h2>
        <table>
            <thead><tr><th>Request ID</th><th>Query</th><th>Mode Req</th><th>Mode Used</th><th>Status</th><th>Latency</th><th>Time</th></tr></thead>
            <tbody>{requests_rows if requests_rows else '<tr><td colspan="7" class="empty">No requests yet</td></tr>'}</tbody>
        </table>
    </div>
    <script>setTimeout(() => location.reload(), 30000);</script>
</body>
</html>"""


def _fmt_time(iso_time: str | None) -> str:
    """Format ISO timestamp for display."""
    if not iso_time:
        return "-"
    try:
        return iso_time[11:19]  # HH:MM:SS
    except (IndexError, TypeError):
        return str(iso_time)[:19]


def _esc(text: str | None) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )