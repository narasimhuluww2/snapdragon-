from datetime import datetime, timedelta

from engine.models import Event, TravelBuffer
from engine.simulator import simulate_ripple_cascade


def test_linear_cascading_shifts():
    """
    Test a 3-tier cascade: A -> B -> C
    A is moved later, forcing B to shift, which in turn forces C to shift.
    """
    event_a = Event(
        id="task_a",
        start=datetime(2026, 9, 11, 9, 0),
        end=datetime(2026, 9, 11, 10, 30),  # Extended to 10:30
    )
    event_b = Event(
        id="task_b",
        start=datetime(2026, 9, 11, 10, 0),  # Was 10:00 - 11:00 (overlaps with new A)
        end=datetime(2026, 9, 11, 11, 0),
    )
    event_c = Event(
        id="task_c",
        start=datetime(2026, 9, 11, 11, 0),  # Was 11:00 - 12:00 (will collide once B shifts)
        end=datetime(2026, 9, 11, 12, 0),
    )

    events = {
        "task_a": event_a,
        "task_b": event_b,
        "task_c": event_c,
    }

    deps = {
        "task_a": ["task_b"],
        "task_b": ["task_c"],
    }

    result = simulate_ripple_cascade(event_a, deps, events)

    # Both task_b and task_c should be shifted
    assert result.total_shifts == 2
    assert not result.has_cycles

    # Inspect shift for B
    shift_b = result.shifts[0]
    assert shift_b.event_id == "task_b"
    assert shift_b.caused_by_id == "task_a"
    assert shift_b.new_start == datetime(2026, 9, 11, 10, 30)
    assert shift_b.new_end == datetime(2026, 9, 11, 11, 30)
    assert shift_b.delay == timedelta(minutes=30)
    assert shift_b.path == ["task_a", "task_b"]

    # Inspect shift for C
    shift_c = result.shifts[1]
    assert shift_c.event_id == "task_c"
    assert shift_c.caused_by_id == "task_b"
    assert shift_c.new_start == datetime(2026, 9, 11, 11, 30)
    assert shift_c.new_end == datetime(2026, 9, 11, 12, 30)
    assert shift_c.delay == timedelta(minutes=30)
    assert shift_c.path == ["task_a", "task_b", "task_c"]

    # Verify final schedule state
    assert result.final_events["task_b"].start == datetime(2026, 9, 11, 10, 30)
    assert result.final_events["task_c"].start == datetime(2026, 9, 11, 11, 30)


def test_cascading_with_travel_buffers():
    """
    Test cascade where travel buffers compound the downstream shifts:
    Task A (Site 1) -> Task B (Site 2) with 20 min travel.
    """
    event_a = Event(
        id="meeting_a",
        start=datetime(2026, 9, 11, 14, 0),
        end=datetime(2026, 9, 11, 15, 0),
        location="HQ",
    )
    event_b = Event(
        id="site_b",
        start=datetime(2026, 9, 11, 15, 5),  # 5 min gap, but 25 min needed
        end=datetime(2026, 9, 11, 16, 0),
        location="Client",
    )

    tb = TravelBuffer(
        id="tb_hq_client",
        from_location="HQ",
        to_location="Client",
        travel_duration=timedelta(minutes=20),
        safety_buffer=timedelta(minutes=5),  # Required: 25 mins
    )

    events = {"meeting_a": event_a, "site_b": event_b}
    deps = {"meeting_a": ["site_b"]}

    result = simulate_ripple_cascade(event_a, deps, events, travel_buffers=[tb])

    assert result.total_shifts == 1
    shift_b = result.shifts[0]
    assert shift_b.impact_type == "travel_conflict"
    # New start should be meeting_a.end (15:00) + 25 mins = 15:25
    assert shift_b.new_start == datetime(2026, 9, 11, 15, 25)
    # Original duration was 55 mins (15:05 to 16:00), so new end = 15:25 + 55 min = 16:20
    assert shift_b.new_end == datetime(2026, 9, 11, 16, 20)


def test_cycle_prevention():
    """
    Test circular dependency: Task A -> Task B -> Task A.
    Must not cause infinite recursion and must report cycle.
    """
    event_a = Event(
        id="node_a",
        start=datetime(2026, 9, 11, 8, 0),
        end=datetime(2026, 9, 11, 9, 30),
    )
    event_b = Event(
        id="node_b",
        start=datetime(2026, 9, 11, 9, 0),
        end=datetime(2026, 9, 11, 10, 0),
    )

    events = {"node_a": event_a, "node_b": event_b}
    deps = {
        "node_a": ["node_b"],
        "node_b": ["node_a"],  # Cycle back to node_a
    }

    result = simulate_ripple_cascade(event_a, deps, events)

    assert result.has_cycles
    assert ["node_a", "node_b", "node_a"] in result.detected_cycles

    # Check that cycle detection record is present in shifts
    cycle_shifts = [s for s in result.shifts if s.impact_type == "cycle_detected"]
    assert len(cycle_shifts) == 1
    assert cycle_shifts[0].path == ["node_a", "node_b", "node_a"]


def test_diamond_dependency_resolution():
    r"""
    Test diamond dependency:
         A
       /   \
      B     C
       \   /
         D
    D should be shifted without false cycle detection.
    """
    event_a = Event(
        id="task_a",
        start=datetime(2026, 9, 11, 9, 0),
        end=datetime(2026, 9, 11, 10, 0),
    )
    event_b = Event(
        id="task_b",
        start=datetime(2026, 9, 11, 9, 30),  # Shifts to 10:00 - 11:00
        end=datetime(2026, 9, 11, 10, 30),
    )
    event_c = Event(
        id="task_c",
        start=datetime(2026, 9, 11, 9, 45),  # Shifts to 10:00 - 11:45
        end=datetime(2026, 9, 11, 11, 30),
    )
    event_d = Event(
        id="task_d",
        start=datetime(2026, 9, 11, 10, 30),  # Must accommodate both B (ends 11:00) and C (ends 11:45)
        end=datetime(2026, 9, 11, 11, 30),
    )

    events = {
        "task_a": event_a,
        "task_b": event_b,
        "task_c": event_c,
        "task_d": event_d,
    }
    deps = {
        "task_a": ["task_b", "task_c"],
        "task_b": ["task_d"],
        "task_c": ["task_d"],
    }

    result = simulate_ripple_cascade(event_a, deps, events)

    assert not result.has_cycles
    # D must end up starting at or after C's new end (11:45)
    assert result.final_events["task_d"].start >= datetime(2026, 9, 11, 11, 45)
