"""
SnapEdge AI Assistant - FastAPI Backend Server
Snapdragon® AI Lab Build & Present Challenge
"""

from datetime import datetime, timedelta
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import (
    Event,
    QualcommAIHubParser,
    TravelBuffer,
    apply_parsed_intent_and_simulate,
    simulate_ripple_cascade,
)
from snapedge.services.copilot import (
    generate_closed_loop_resolution,
    process_clipboard_query,
)
from snapedge.services.summarizer import (
    SAMPLE_MEETINGS,
    process_meeting_transcript,
)
from snapedge.services.telemetry import (
    get_hardware_telemetry,
    set_governor_mode,
)

app = FastAPI(
    title="SnapEdge AI Assistant",
    description="Localized, Privacy-First Productivity Copilot Optimized for Snapdragon-Powered HP PCs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory working schedule state
def get_default_schedule():
    meeting_1 = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        location="HQ_North",
    )
    site_visit = Event(
        id="site_visit_001",
        start=datetime(2026, 9, 11, 11, 30),
        end=datetime(2026, 9, 11, 12, 45),
        location="Client_Campus",
    )
    deliverable = Event(
        id="deliverable_001",
        start=datetime(2026, 9, 11, 13, 0),
        end=datetime(2026, 9, 11, 14, 0),
        location="Client_Campus",
    )

    tb = TravelBuffer(
        id="tb_hq_client",
        from_location="HQ_North",
        to_location="Client_Campus",
        travel_duration=timedelta(minutes=20),
        safety_buffer=timedelta(minutes=10),  # 30 min required
    )

    events = {
        "meeting_001": meeting_1,
        "site_visit_001": site_visit,
        "deliverable_001": deliverable,
    }

    dependency_graph = {
        "meeting_001": ["site_visit_001"],
        "site_visit_001": ["deliverable_001"],
    }

    travel_buffers = [tb]

    return events, dependency_graph, travel_buffers


current_events, current_dependencies, current_travel_buffers = get_default_schedule()


# Request Models
class SummarizeRequest(BaseModel):
    preset_key: Optional[str] = None
    custom_text: Optional[str] = None
    title: Optional[str] = None


class CopilotRequest(BaseModel):
    text: str
    mode: str = "auto"


class SimulateRequest(BaseModel):
    prompt: str


class GovernorRequest(BaseModel):
    mode: str = "auto"


@app.get("/api/status")
def get_status():
    parser = QualcommAIHubParser()
    return {
        "app_name": "SnapEdge AI Assistant",
        "device_profile": "Snapdragon-Powered HP PC (HP OmniBook Series)",
        "active_provider": parser.provider,
        "is_npu_accelerated": parser.provider == "QNNExecutionProvider",
        "npu_hardware": "Qualcomm® Hexagon™ NPU (45 TOPS)",
        "privacy_mode": "100% On-Device Offline (Zero Cloud Data Leakage)",
        "offline_guarantee": True,
        "models_integrated": [
            {
                "name": "Whisper-tiny-ONNX",
                "hub_source": "Qualcomm AI Hub (Audio)",
                "purpose": "Speech-to-Text & Meeting Ingestion (Tab 1)",
                "format": "ONNX (QNN EP - Hexagon NPU)",
            },
            {
                "name": "TitaNet-ONNX",
                "hub_source": "Qualcomm AI Hub (Audio / Speaker Embedding)",
                "purpose": "Acoustic Speaker Diarization & HVX Voice Clustering (Tab 1)",
                "format": "INT8 ONNX (QNN EP - HVX Fast Clustering)",
            },
            {
                "name": "Phi-3-mini-4k-instruct-ONNX",
                "hub_source": "Qualcomm AI Hub (Generative AI)",
                "purpose": "Contextual Copilot & Closed-Loop Auto-Resolution (Tab 2 & 3)",
                "format": "INT4 ONNX (QNN EP - Hexagon NPU)",
            },
            {
                "name": "All-MiniLM-L6-v2-ONNX",
                "hub_source": "Qualcomm AI Hub (Embeddings & Intent)",
                "purpose": "AHEAD Natural Language Schedule Parsing (Tab 3)",
                "format": "INT8 ONNX (QNN EP - Hexagon NPU)",
            },
        ],
    }


@app.get("/api/metrics")
def get_metrics():
    return get_hardware_telemetry()


@app.get("/api/governor")
def get_governor():
    data = get_hardware_telemetry()
    return data["governor"]


@app.post("/api/governor")
def set_governor(req: GovernorRequest):
    active_mode = set_governor_mode(req.mode)
    data = get_hardware_telemetry()
    return {
        "status": "success",
        "requested_mode": req.mode,
        "active_mode": active_mode,
        "governor": data["governor"],
    }


@app.get("/api/schedule")
def get_schedule():
    events_list = [
        {
            "id": ev.id,
            "start": ev.start.strftime("%H:%M"),
            "end": ev.end.strftime("%H:%M"),
            "duration_mins": int((ev.end - ev.start).total_seconds() // 60),
            "location": ev.location or "Unassigned",
            "dependents": current_dependencies.get(ev.id, []),
        }
        for ev in sorted(current_events.values(), key=lambda e: e.start)
    ]

    buffers_list = [
        {
            "id": tb.id,
            "from_location": tb.from_location,
            "to_location": tb.to_location,
            "travel_mins": int(tb.travel_duration.total_seconds() // 60),
            "safety_mins": int(tb.safety_buffer.total_seconds() // 60),
            "total_required_mins": int(tb.required_time.total_seconds() // 60),
        }
        for tb in current_travel_buffers
    ]

    return {
        "events": events_list,
        "dependency_graph": current_dependencies,
        "travel_buffers": buffers_list,
    }


@app.post("/api/reset_schedule")
def reset_schedule():
    global current_events, current_dependencies, current_travel_buffers
    current_events, current_dependencies, current_travel_buffers = get_default_schedule()
    return {"status": "success", "message": "Schedule reset to default state"}


@app.post("/api/summarize")
def summarize_meeting(req: SummarizeRequest):
    if req.preset_key and req.preset_key in SAMPLE_MEETINGS:
        preset = SAMPLE_MEETINGS[req.preset_key]
        text = preset["raw_text"]
        title = preset["title"]
    elif req.custom_text:
        text = req.custom_text
        title = req.title or "Custom Audio / Meeting Transcript"
    else:
        raise HTTPException(status_code=400, detail="Must provide either preset_key or custom_text")

    result = process_meeting_transcript(
        text=text,
        title=title,
        events=current_events,
        dependency_graph=current_dependencies,
        travel_buffers=current_travel_buffers,
    )

    return result


@app.post("/api/copilot")
def copilot_query(req: CopilotRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    resp = process_clipboard_query(
        text=req.text,
        mode=req.mode,
        events=current_events,
        dependency_graph=current_dependencies,
        travel_buffers=current_travel_buffers,
    )
    return resp


@app.post("/api/simulate")
def simulate_reschedule(req: SimulateRequest):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    try:
        parser = QualcommAIHubParser()
        resp = apply_parsed_intent_and_simulate(
            intent_or_text=req.prompt,
            events=current_events,
            dependency_graph=current_dependencies,
            travel_buffers=current_travel_buffers,
            parser=parser,
        )

        shifts_data = [
            {
                "event_id": s.event_id,
                "caused_by": s.caused_by_id,
                "impact_type": s.impact_type,
                "path": " -> ".join(s.path),
                "original_window": f"{s.original_start.strftime('%H:%M')} - {s.original_end.strftime('%H:%M')}",
                "new_window": f"{s.new_start.strftime('%H:%M')} - {s.new_end.strftime('%H:%M')}",
                "delay_mins": int(s.delay.total_seconds() // 60),
                "message": s.message,
            }
            for s in resp.simulation_result.shifts
        ]

        final_schedule = [
            {
                "id": ev.id,
                "start": ev.start.strftime("%H:%M"),
                "end": ev.end.strftime("%H:%M"),
                "location": ev.location or "Unassigned",
            }
            for ev in sorted(resp.simulation_result.final_events.values(), key=lambda e: e.start)
        ]

        return {
            "status": "success",
            "prompt": req.prompt,
            "target_event_id": resp.intent.target_event_id,
            "intent_type": resp.intent.intent_type,
            "modified_event": {
                "id": resp.modified_event.id,
                "start": resp.modified_event.start.strftime("%H:%M"),
                "end": resp.modified_event.end.strftime("%H:%M"),
                "location": resp.modified_event.location,
            },
            "total_shifts": resp.total_downstream_shifts,
            "has_cycles": resp.has_detected_cycles,
            "detected_cycles": resp.simulation_result.detected_cycles,
            "shifts": shifts_data,
            "final_schedule": final_schedule,
            "provider_used": resp.provider_used,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AutoResolveRequest(BaseModel):
    prompt: Optional[str] = "Delay meeting_001 by 45 minutes"


@app.post("/api/auto_resolve")
def auto_resolve_conflict(req: AutoResolveRequest):
    """
    Closed-Loop Automation Endpoint:
    Generates a full apology/reschedule email draft and structured calendar updates.
    """
    try:
        resolution = generate_closed_loop_resolution(
            prompt_or_shifts=req.prompt or "Delay meeting_001 by 45 minutes",
            events=current_events,
            dependency_graph=current_dependencies,
            travel_buffers=current_travel_buffers,
        )
        return resolution
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ApplyResolutionRequest(BaseModel):
    prompt: str


@app.post("/api/apply_schedule_resolution")
def apply_schedule_resolution(req: ApplyResolutionRequest):
    """
    One-Click Calendar Commit:
    Applies the simulated schedule modifications directly to the live calendar state.
    """
    global current_events
    try:
        parser = QualcommAIHubParser()
        resp = apply_parsed_intent_and_simulate(
            intent_or_text=req.prompt,
            events=current_events,
            dependency_graph=current_dependencies,
            travel_buffers=current_travel_buffers,
            parser=parser,
        )
        current_events = resp.simulation_result.final_events
        return {
            "status": "success",
            "message": f"Applied {resp.total_downstream_shifts} shifts to active calendar schedule.",
            "updated_events": [ev.id for ev in current_events.values()],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Mount static frontend directory
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
