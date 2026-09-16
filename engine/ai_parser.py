from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple

import onnxruntime as ort

from engine.models import Event, TravelBuffer
from engine.simulator import SimulationResult, simulate_ripple_cascade


@dataclass
class ParsedScheduleIntent:
    """
    Structured schedule modification extracted from natural language input.
    """

    raw_text: str
    target_event_id: str
    new_start: Optional[datetime] = None
    new_end: Optional[datetime] = None
    time_delta: Optional[timedelta] = None
    new_location: Optional[str] = None
    intent_type: str = "reschedule"  # "delay" | "advance" | "reschedule" | "relocate"
    confidence: float = 1.0


@dataclass
class AISimulationResponse:
    """
    Combined result of natural language extraction and downstream simulation.
    """

    intent: ParsedScheduleIntent
    original_event: Event
    modified_event: Event
    simulation_result: SimulationResult
    provider_used: str

    @property
    def total_downstream_shifts(self) -> int:
        return self.simulation_result.total_shifts

    @property
    def has_detected_cycles(self) -> bool:
        return self.simulation_result.has_cycles


class QualcommAIHubParser:
    """
    Interface for Qualcomm AI Hub ONNX models running on Snapdragon NPUs.

    Features:
    - Automatic Execution Provider selection prioritizing Qualcomm QNN (Hexagon NPU)
      on Snapdragon devices, with graceful CPU fallback.
    - Zero-dependency regex/pattern entity extractor providing robust parsing
      and testability, ready to receive ONNX token classification weights.
    - Direct integration with AHEAD simulator for what-if ripple analysis.
    """

    PREFERRED_PROVIDERS = [
        "QNNExecutionProvider",       # Qualcomm Hexagon NPU (Snapdragon X Elite / Plus)
        "DirectMLExecutionProvider",  # Windows DirectML accelerator
        "CPUExecutionProvider",       # Portable fallback
    ]

    def __init__(
        self,
        model_path: Optional[str] = None,
        preferred_provider: Optional[str] = None,
    ):
        self.model_path = model_path
        self.session: Optional[ort.InferenceSession] = None
        self.available_providers = ort.get_available_providers()

        # Select execution provider
        if preferred_provider and preferred_provider in self.available_providers:
            self.provider = preferred_provider
        else:
            self.provider = "CPUExecutionProvider"
            for p in self.PREFERRED_PROVIDERS:
                if p in self.available_providers:
                    self.provider = p
                    break

        if model_path:
            self._load_onnx_session(model_path)

    def _load_onnx_session(self, path: str) -> None:
        """Loads the ONNX model targeting the active execution provider."""
        try:
            self.session = ort.InferenceSession(path, providers=[self.provider])
        except Exception:
            # Fallback to CPU if provider initialization fails
            self.provider = "CPUExecutionProvider"
            self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])

    def parse(
        self,
        text: str,
        reference_date: Optional[datetime] = None,
    ) -> ParsedScheduleIntent:
        """
        Parses natural language requests to reschedule, shift, or relocate events.

        Examples:
        - "Push meeting_001 by 30 minutes"
        - "Delay task_b by 1 hour due to traffic"
        - "Move site_visit_001 to 16:45 at Client_South"
        - "Advance project_review by 15 minutes"
        """
        ref = reference_date or datetime(2026, 9, 11, 16, 0)
        clean_text = text.strip()

        # 1. Extract Location Updates first so location tokens aren't confused with event IDs
        new_location: Optional[str] = None
        loc_match = re.search(
            r"\b(?:at|in|location:)\s+([A-Z][a-zA-Z0-9_-]+)\b",
            clean_text,
        )
        if loc_match:
            candidate = loc_match.group(1)
            if candidate.lower() not in {"the", "am", "pm", "utc", "gmt"} and not re.match(r"^\d{1,2}(?::\d{2})?$", candidate):
                new_location = candidate

        # 2. Extract Event ID
        event_id: str = "unknown_event"
        # Priority A: Directly following an action verb (e.g., "move site_visit_001", "delay meeting_001")
        action_match = re.search(
            r"\b(?:move|delay|push|reschedule|advance|shift)\s+([a-zA-Z0-9_-]+)\b",
            clean_text,
            re.I,
        )
        if action_match:
            event_id = action_match.group(1)
        else:
            # Priority B: Tokens containing underscores/hyphens with digits (e.g., meeting_001, task-2)
            id_candidates = re.findall(r"\b([a-zA-Z0-9]+(?:[_-][a-zA-Z0-9]+)+)\b", clean_text)
            valid_candidates = [c for c in id_candidates if c != new_location]
            if valid_candidates:
                event_id = valid_candidates[0]
            else:
                # Priority C: Phrases like "meeting 1" -> "meeting_001"
                phrase_match = re.search(r"\b(meeting|task|event|assignment)\s*(\d+)\b", clean_text, re.I)
                if phrase_match:
                    event_id = f"{phrase_match.group(1).lower()}_{int(phrase_match.group(2)):03d}"

        # 3. Extract Relative Shifts (e.g., "by 30 minutes", "by 1 hour")
        time_delta: Optional[timedelta] = None
        intent_type = "reschedule"

        delta_match = re.search(
            r"(?:by|delay(?:ed)?\s*by|push(?:ed)?\s*by|advance(?:d)?\s*by)\s*(\d+)\s*(min|minute|minutes|hr|hour|hours|h|m)\b",
            clean_text,
            re.I,
        )
        if delta_match:
            value = int(delta_match.group(1))
            unit = delta_match.group(2).lower()
            if "h" in unit:
                time_delta = timedelta(hours=value)
            else:
                time_delta = timedelta(minutes=value)

            if "advance" in clean_text.lower():
                time_delta = -time_delta
                intent_type = "advance"
            else:
                intent_type = "delay"

        # 3. Extract Absolute Time (e.g., "to 16:45", "at 10:30")
        new_start: Optional[datetime] = None
        time_match = re.search(
            r"\b(?:to|at|starting\s*at)\s*(\d{1,2}):(\d{2})\b",
            clean_text,
            re.I,
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            new_start = datetime(ref.year, ref.month, ref.day, hour, minute)
            intent_type = "reschedule"

        if new_location and not time_delta and not new_start:
            intent_type = "relocate"

        return ParsedScheduleIntent(
            raw_text=text,
            target_event_id=event_id,
            new_start=new_start,
            new_end=None,
            time_delta=time_delta,
            new_location=new_location,
            intent_type=intent_type,
            confidence=0.95,
        )


def apply_parsed_intent_and_simulate(
    intent_or_text: ParsedScheduleIntent | str,
    events: Dict[str, Event],
    dependency_graph: Dict[str, List[str]],
    travel_buffers: Optional[Dict[Tuple[str, str], TravelBuffer] | List[TravelBuffer]] = None,
    parser: Optional[QualcommAIHubParser] = None,
) -> AISimulationResponse:
    """
    End-to-End Engine Hook:
    Parses natural language (or takes a parsed intent), applies the schedule mutation,
    and runs the recursive cascading simulator to identify ripple effects.
    """
    ai_parser = parser or QualcommAIHubParser()

    if isinstance(intent_or_text, str):
        intent = ai_parser.parse(intent_or_text)
    else:
        intent = intent_or_text

    if intent.target_event_id not in events:
        raise KeyError(
            f"Target event '{intent.target_event_id}' not found in current schedule."
        )

    orig_event = events[intent.target_event_id]
    orig_duration = orig_event.end - orig_event.start

    # Determine modified time window
    if intent.new_start:
        updated_start = intent.new_start
        updated_end = updated_start + orig_duration
    elif intent.time_delta:
        updated_start = orig_event.start + intent.time_delta
        updated_end = orig_event.end + intent.time_delta
    else:
        updated_start = orig_event.start
        updated_end = orig_event.end

    updated_location = intent.new_location or orig_event.location

    modified_event = Event(
        id=orig_event.id,
        start=updated_start,
        end=updated_end,
        dependent_task_ids=list(orig_event.dependent_task_ids),
        location=updated_location,
    )

    # Run cascading ripple simulation
    sim_result = simulate_ripple_cascade(
        modified_event=modified_event,
        dependency_graph=dependency_graph,
        events=events,
        travel_buffers=travel_buffers,
    )

    return AISimulationResponse(
        intent=intent,
        original_event=orig_event,
        modified_event=modified_event,
        simulation_result=sim_result,
        provider_used=ai_parser.provider,
    )
