from fastapi.testclient import TestClient

from snapedge.app import app

client = TestClient(app)


def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "SnapEdge AI Assistant"
    assert "Snapdragon" in data["device_profile"]
    assert "active_provider" in data
    assert data["npu_hardware"] == "Qualcomm® Hexagon™ NPU (45 TOPS)"
    assert data["offline_guarantee"] is True
    assert "100% On-Device" in data["privacy_mode"]
    assert len(data["models_integrated"]) == 4
    # Verify exact Qualcomm AI Hub citations
    model_names = [m["name"] for m in data["models_integrated"]]
    assert "Whisper-tiny-ONNX" in model_names
    assert "TitaNet-ONNX" in model_names
    assert "Phi-3-mini-4k-instruct-ONNX" in model_names
    assert "All-MiniLM-L6-v2-ONNX" in model_names


def test_api_metrics():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_percent" in data
    assert "ram_percent" in data
    assert data["npu_tops_rating"] == 45
    assert data["power_efficiency_multiplier"] == 6.8
    assert "total_inferences" in data
    assert "benchmarks" in data
    b = data["benchmarks"]
    assert b["npu"]["ttft_ms"] == 18.5
    assert b["npu"]["tokens_per_second"] == 48.2
    assert b["cpu_baseline"]["ttft_ms"] == 84.2


def test_api_schedule():
    response = client.get("/api/schedule")
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 3
    assert "meeting_001" in data["dependency_graph"]
    assert len(data["travel_buffers"]) >= 1


def test_api_summarize_preset():
    response = client.post("/api/summarize", json={"preset_key": "board_sync"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["summary_points"]) > 0
    assert len(data["action_items"]) > 0
    # Overrun in board sync triggers AHEAD conflict
    assert data["schedule_conflict_detected"] is True
    assert data["ahead_simulation"] is not None
    assert data["ahead_simulation"]["total_shifts"] == 2
    # Verify acoustic speaker diarization turns
    assert "diarized_turns" in data
    assert len(data["diarized_turns"]) == 3
    assert data["diarized_turns"][0]["speaker"] == "Sarah Jenkins"
    assert data["diarized_turns"][1]["speaker"] == "Marcus Vance"


def test_api_copilot_email():
    response = client.post(
        "/api/copilot",
        json={"text": "Review product milestones with client tomorrow", "mode": "email"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Subject: Follow-up & Next Steps" in data["result_text"]
    assert data["processing_time_ms"] > 0


def test_api_copilot_schedule():
    response = client.post(
        "/api/copilot",
        json={"text": "Delay meeting_001 by 45 minutes", "mode": "schedule"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "AHEAD Schedule Adjustment Detected" in data["result_text"]
    assert data["ahead_payload"] is not None
    assert data["ahead_payload"]["shifts_count"] == 2


def test_api_simulate_endpoint():
    response = client.post(
        "/api/simulate",
        json={"prompt": "Move meeting_001 to 11:15 at HQ_North"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_event_id"] == "meeting_001"
    assert data["total_shifts"] == 2
    assert len(data["final_schedule"]) == 3


def test_api_simulate_empty_error():
    response = client.post("/api/simulate", json={"prompt": "  "})
    assert response.status_code == 400


def test_api_auto_resolve_closed_loop():
    response = client.post(
        "/api/auto_resolve",
        json={"prompt": "Delay meeting_001 by 45 minutes"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Subject: Reschedule Notice & Updated Agenda" in data["apology_email"]
    assert "Cascading Downstream Adjustments" in data["apology_email"]
    assert data["total_shifts"] == 2
    assert len(data["calendar_actions"]) == 2
    assert data["calendar_actions"][0]["action"] == "AUTO_SHIFTED"


def test_api_apply_schedule_resolution():
    response = client.post(
        "/api/apply_schedule_resolution",
        json={"prompt": "Delay meeting_001 by 45 minutes"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Applied 2 shifts" in data["message"]

    # Verify schedule was updated in active state
    sched_resp = client.get("/api/schedule")
    events = {e["id"]: e for e in sched_resp.json()["events"]}
    assert events["meeting_001"]["start"] == "10:45"
    assert events["site_visit_001"]["start"] == "12:15"

    # Reset schedule back for subsequent tests
    client.post("/api/reset_schedule")


def test_static_frontend_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "SnapEdge AI Assistant" in response.text
    assert "Offline Mode: 100% On-Device" in response.text
    assert "Alt+1" in response.text

    js_response = client.get("/app.js")
    assert js_response.status_code == 200
    assert "triggerAutoResolve" in js_response.text


def test_api_governor_modes():
    # Test GET governor
    get_res = client.get("/api/governor")
    assert get_res.status_code == 200
    gov = get_res.json()
    assert "mode" in gov
    assert "display_name" in gov
    assert "watts_saved" in gov
    assert "thermal_status" in gov

    # Test POST override to eco
    post_res = client.post("/api/governor", json={"mode": "eco"})
    assert post_res.status_code == 200
    pdata = post_res.json()
    assert pdata["active_mode"] == "eco"
    assert pdata["governor"]["mode"] == "eco"
    assert pdata["governor"]["watts_saved"] == 1.4
    assert pdata["governor"]["throttle_interval_sec"] == 5

    # Test POST override to ultra_saver
    post_res2 = client.post("/api/governor", json={"mode": "ultra_saver"})
    assert post_res2.status_code == 200
    assert post_res2.json()["governor"]["battery_extension_hrs"] == 4.1
    assert post_res2.json()["governor"]["throttle_interval_sec"] == 10

    # Reset back to auto
    reset_res = client.post("/api/governor", json={"mode": "auto"})
    assert reset_res.status_code == 200
    assert reset_res.json()["active_mode"] == "auto"
