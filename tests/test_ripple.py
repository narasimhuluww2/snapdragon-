from datetime import datetime, timedelta

from engine.models import Event, TravelBuffer, check_ripple_effect


def test_direct_overlap():
    meeting = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 16, 0),
        end=datetime(2026, 9, 11, 17, 0),
        dependent_task_ids=["assignment_001"],
    )

    assignment = Event(
        id="assignment_001",
        start=datetime(2026, 9, 11, 16, 30),
        end=datetime(2026, 9, 11, 18, 0),
    )

    events = {
        "meeting_001": meeting,
        "assignment_001": assignment,
    }

    dependency_graph = {
        "meeting_001": ["assignment_001"]
    }

    impacts = check_ripple_effect(
        meeting,
        dependency_graph,
        events,
    )

    impacted_ids = [
        impact.impacted_id
        for impact in impacts
    ]

    assert "assignment_001" in impacted_ids
    assert impacts[0].impact_type == "overlap"


def test_travel_conflict_insufficient_time():
    meeting = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        dependent_task_ids=["site_visit_001"],
        location="HQ_North",
    )

    site_visit = Event(
        id="site_visit_001",
        start=datetime(2026, 9, 11, 11, 15),
        end=datetime(2026, 9, 11, 12, 30),
        location="Client_South",
    )

    travel_buffer = TravelBuffer(
        id="tb_hq_client",
        from_location="HQ_North",
        to_location="Client_South",
        travel_duration=timedelta(minutes=20),
        safety_buffer=timedelta(minutes=5),  # Total required: 25 mins
    )

    events = {
        "meeting_001": meeting,
        "site_visit_001": site_visit,
    }

    dependency_graph = {
        "meeting_001": ["site_visit_001"]
    }

    impacts = check_ripple_effect(
        meeting,
        dependency_graph,
        events,
        travel_buffers=[travel_buffer],
    )

    assert len(impacts) == 1
    assert impacts[0].impacted_id == "site_visit_001"
    assert impacts[0].impact_type == "travel_conflict"
    assert "Insufficient travel time" in impacts[0].message


def test_travel_sufficient_time():
    meeting = Event(
        id="meeting_001",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        dependent_task_ids=["site_visit_001"],
        location="HQ_North",
    )

    site_visit = Event(
        id="site_visit_001",
        start=datetime(2026, 9, 11, 11, 30),  # 30 min transition available
        end=datetime(2026, 9, 11, 12, 30),
        location="Client_South",
    )

    travel_buffer = TravelBuffer(
        id="tb_hq_client",
        from_location="HQ_North",
        to_location="Client_South",
        travel_duration=timedelta(minutes=20),
        safety_buffer=timedelta(minutes=5),  # Total required: 25 mins
    )

    events = {
        "meeting_001": meeting,
        "site_visit_001": site_visit,
    }

    dependency_graph = {
        "meeting_001": ["site_visit_001"]
    }

    impacts = check_ripple_effect(
        meeting,
        dependency_graph,
        events,
        travel_buffers=[travel_buffer],
    )

    assert len(impacts) == 0


def test_same_location_no_travel_conflict():
    event_a = Event(
        id="event_a",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        dependent_task_ids=["event_b"],
        location="Conference_Room_1",
    )

    event_b = Event(
        id="event_b",
        start=datetime(2026, 9, 11, 11, 5),  # 5 min gap in same room
        end=datetime(2026, 9, 11, 12, 0),
        location="Conference_Room_1",
    )

    events = {
        "event_a": event_a,
        "event_b": event_b,
    }

    dependency_graph = {
        "event_a": ["event_b"]
    }

    impacts = check_ripple_effect(
        event_a,
        dependency_graph,
        events,
        travel_buffers=[],
    )

    assert len(impacts) == 0


def test_touching_boundaries_triggers_travel_conflict():
    event_a = Event(
        id="event_a",
        start=datetime(2026, 9, 11, 10, 0),
        end=datetime(2026, 9, 11, 11, 0),
        dependent_task_ids=["event_b"],
        location="HQ",
    )

    event_b = Event(
        id="event_b",
        start=datetime(2026, 9, 11, 11, 0),  # Touching boundary (0 gap)
        end=datetime(2026, 9, 11, 12, 0),
        location="Branch",
    )

    travel_buffer = TravelBuffer(
        id="tb_hq_branch",
        from_location="HQ",
        to_location="Branch",
        travel_duration=timedelta(minutes=15),
        safety_buffer=timedelta(minutes=0),
    )

    events = {
        "event_a": event_a,
        "event_b": event_b,
    }

    dependency_graph = {
        "event_a": ["event_b"]
    }

    impacts = check_ripple_effect(
        event_a,
        dependency_graph,
        events,
        travel_buffers=[travel_buffer],
    )

    assert len(impacts) == 1
    assert impacts[0].impact_type == "travel_conflict"
