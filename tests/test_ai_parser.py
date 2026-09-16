from datetime import datetime, timedelta

from engine.ai_parser import (
    QualcommAIHubParser,
    apply_parsed_intent_and_simulate,
)
from engine.models import Event, TravelBuffer


def test_parse_relative_delay():
    parser = QualcommAIHubParser()
    intent = parser.parse("Push meeting_001 by 30 minutes because of traffic")

    assert intent.target_event_id == "meeting_001"
    assert intent.time_delta == timedelta(minutes=30)
    assert intent.intent_type == "delay"
    assert intent.new_location is None


def test_parse_absolute_reschedule_with_location():
    parser = QualcommAIHubParser()
    intent = parser.parse("Move site_visit_001 to 16:45 at Client_South")

    assert intent.target_event_id == "site_visit_001"
    assert intent.new_start == datetime(2026, 9, 11, 16, 45)
    assert intent.new_location == "Client_South"
    assert intent.intent_type == "reschedule"


def test_end_to_end_nlp_to_ripple_cascade():
    """
    Test the full pipeline:
    Natural language string -> Qualcomm AI Parser -> Event mutation -> Ripple cascade.
    """
    meeting = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 16, 0),
        end=datetime(2026, 9, 11, 17, 0),
        dependent_task_ids=["assignment_001"],
    )

    assignment = Event(
        id="assignment_001",
        start=datetime(2026, 9, 11, 17, 0),
        end=datetime(2026, 9, 11, 18, 0),
    )

    events = {"meeting_001": meeting, "assignment_001": assignment}
    deps = {"meeting_001": ["assignment_001"]}

    # Natural language prompt that pushes meeting_001 by 45 minutes
    prompt = "Delay meeting_001 by 45 minutes due to executive board review"

    response = apply_parsed_intent_and_simulate(
        intent_or_text=prompt,
        events=events,
        dependency_graph=deps,
    )

    # Verify intent extraction
    assert response.intent.target_event_id == "meeting_001"
    assert response.intent.time_delta == timedelta(minutes=45)

    # Verify modified root event
    assert response.modified_event.start == datetime(2026, 9, 11, 16, 45)
    assert response.modified_event.end == datetime(2026, 9, 11, 17, 45)

    # Verify downstream ripple cascade: assignment_001 was pushed to 17:45
    assert response.total_downstream_shifts == 1
    shift = response.simulation_result.shifts[0]
    assert shift.event_id == "assignment_001"
    assert shift.new_start == datetime(2026, 9, 11, 17, 45)
    assert shift.new_end == datetime(2026, 9, 11, 18, 45)
    assert shift.delay == timedelta(minutes=45)
    assert shift.path == ["meeting_001", "assignment_001"]


def test_nlp_with_travel_buffer_cascade():
    """
    Test NLP input changing location and triggering a downstream TravelBuffer conflict.
    """
    meeting = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        location="Office_Old",
    )

    site_visit = Event(
        id="site_visit_001",
        start=datetime(2026, 9, 11, 11, 15),  # 15 min gap
        end=datetime(2026, 9, 11, 12, 0),
        location="Client_South",
    )

    tb = TravelBuffer(
        id="tb_hq_client",
        from_location="HQ_North",
        to_location="Client_South",
        travel_duration=timedelta(minutes=20),
        safety_buffer=timedelta(minutes=5),  # 25 min required
    )

    events = {"meeting_001": meeting, "site_visit_001": site_visit}
    deps = {"meeting_001": ["site_visit_001"]}

    # Relocate meeting to HQ_North
    prompt = "Move meeting_001 to 10:00 at HQ_North"

    response = apply_parsed_intent_and_simulate(
        intent_or_text=prompt,
        events=events,
        dependency_graph=deps,
        travel_buffers=[tb],
    )

    assert response.modified_event.location == "HQ_North"
    assert response.total_downstream_shifts == 1
    shift = response.simulation_result.shifts[0]
    assert shift.impact_type == "travel_conflict"
    # Meeting ends at 11:00 + 25 min travel = 11:25 new start
    assert shift.new_start == datetime(2026, 9, 11, 11, 25)


def test_provider_selection():
    """
    Verifies that Qualcomm parser picks a supported provider and gracefully falls back.
    """
    parser = QualcommAIHubParser(preferred_provider="NonExistentProvider")
    # Must fallback to CPUExecutionProvider
    assert parser.provider == "CPUExecutionProvider"
