"""
tests/test_api_sse.py - Flask API Endpoints & SSE Stream Tests.
"""

from api.web_server import create_app
from core.event_bus import global_event_bus


def test_flask_app_routes():
    app = create_app()
    client = app.test_client()

    # GET / (dashboard)
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert b"Void Edge Core" in res_index.data

    # GET /api/status
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    json_data = res_status.get_json()
    assert "ram_rss_mb" in json_data
    assert "battery" in json_data

    # POST /api/chat
    res_chat = client.post("/api/chat", json={"message": "battery level"})
    assert res_chat.status_code == 200
    chat_data = res_chat.get_json()
    assert "reasoning" in chat_data


def test_event_bus_pub_sub():
    q = global_event_bus.subscribe()
    global_event_bus.publish("test_event", {"val": 42})

    item = q.get_nowait()
    assert item["event"] == "test_event"
    assert item["data"]["val"] == 42

    global_event_bus.unsubscribe(q)


def test_sse_stream_pep3333_compliance():
    """Verifies that /api/stream returns SSE headers compliant with PEP 3333 (no hop-by-hop Connection header)."""
    app = create_app()
    client = app.test_client()

    prohibited_hop_by_hop = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}

    res = client.get("/api/stream")
    assert res.status_code == 200
    assert res.mimetype == "text/event-stream"
    assert res.headers.get("Cache-Control") == "no-cache"

    for header in res.headers.keys():
        assert header.lower() not in prohibited_hop_by_hop, f"Prohibited hop-by-hop header found: {header}"
