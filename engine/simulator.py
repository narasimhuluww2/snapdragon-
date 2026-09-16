from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from engine.models import Event, TravelBuffer


@dataclass
class CascadingShift:
    """
    Represents a schedule shift forced on an event by an upstream conflict.
    """

    event_id: str
    caused_by_id: str
    impact_type: str  # "overlap" | "travel_conflict" | "cycle_detected"
    original_start: datetime
    original_end: datetime
    new_start: datetime
    new_end: datetime
    delay: timedelta
    path: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class SimulationResult:
    """
    Comprehensive outcome of a cascading ripple simulation.
    """

    shifts: List[CascadingShift] = field(default_factory=list)
    final_events: Dict[str, Event] = field(default_factory=dict)
    detected_cycles: List[List[str]] = field(default_factory=list)

    @property
    def total_shifts(self) -> int:
        return len(self.shifts)

    @property
    def has_cycles(self) -> bool:
        return len(self.detected_cycles) > 0


def simulate_ripple_cascade(
    modified_event: Event,
    dependency_graph: Dict[str, List[str]],
    events: Dict[str, Event],
    travel_buffers: Optional[Dict[Tuple[str, str], TravelBuffer] | List[TravelBuffer]] = None,
) -> SimulationResult:
    """
    Simulates transitive cascading impacts of a modified event.

    Features:
    - Cycle Prevention: Detects and stops circular dependencies using active call stack tracking.
    - Cascading Shift Calculation: Computes new event time windows incorporating duration and travel buffers.
    - Detailed Trace Output: Produces structured CascadingShift entries showing the exact causal path.
    """
    # Normalize travel buffers into a lookup dictionary
    buffer_map: Dict[Tuple[str, str], TravelBuffer] = {}
    if travel_buffers:
        if isinstance(travel_buffers, list):
            buffer_map = {
                (tb.from_location, tb.to_location): tb for tb in travel_buffers
            }
        elif isinstance(travel_buffers, dict):
            buffer_map = travel_buffers

    # Work with an isolated copy of events so inputs are not mutated
    simulated_events: Dict[str, Event] = {
        event_id: Event(
            id=ev.id,
            start=ev.start,
            end=ev.end,
            dependent_task_ids=list(ev.dependent_task_ids),
            location=ev.location,
        )
        for event_id, ev in events.items()
    }
    # Update with the new state of the root modified event
    simulated_events[modified_event.id] = Event(
        id=modified_event.id,
        start=modified_event.start,
        end=modified_event.end,
        dependent_task_ids=list(modified_event.dependent_task_ids),
        location=modified_event.location,
    )

    shifts: List[CascadingShift] = []
    detected_cycles: List[List[str]] = []

    def _get_required_travel(from_loc: Optional[str], to_loc: Optional[str]) -> timedelta:
        if from_loc and to_loc and from_loc != to_loc:
            tb = buffer_map.get((from_loc, to_loc))
            if tb:
                return tb.required_time
        return timedelta(0)

    def _cascade(current_event: Event, active_branch: Set[str], current_path: List[str]) -> None:
        dependent_ids = dependency_graph.get(current_event.id, [])

        for dep_id in dependent_ids:
            # Cycle detection: check if dependent node is already in the current ancestor chain
            if dep_id in active_branch:
                cycle_chain = current_path + [dep_id]
                detected_cycles.append(cycle_chain)
                shifts.append(
                    CascadingShift(
                        event_id=dep_id,
                        caused_by_id=current_event.id,
                        impact_type="cycle_detected",
                        original_start=simulated_events[dep_id].start if dep_id in simulated_events else current_event.start,
                        original_end=simulated_events[dep_id].end if dep_id in simulated_events else current_event.end,
                        new_start=simulated_events[dep_id].start if dep_id in simulated_events else current_event.start,
                        new_end=simulated_events[dep_id].end if dep_id in simulated_events else current_event.end,
                        delay=timedelta(0),
                        path=cycle_chain,
                        message=f"Cycle detected: {' -> '.join(cycle_chain)}",
                    )
                )
                continue

            dep_event = simulated_events.get(dep_id)
            if dep_event is None:
                continue

            # Calculate earliest allowable start time after current_event ends + travel buffer
            travel_time = _get_required_travel(current_event.location, dep_event.location)
            earliest_allowed_start = current_event.end + travel_time

            # Check if dependent event conflicts and needs to be pushed forward
            if dep_event.start < earliest_allowed_start:
                duration = dep_event.end - dep_event.start
                new_start = earliest_allowed_start
                new_end = new_start + duration
                delay = new_start - dep_event.start

                # Identify impact type
                if current_event.overlaps(dep_event):
                    impact_type = "overlap"
                    msg = (
                        f"{current_event.id} overlaps with {dep_event.id}. "
                        f"Shifted by {delay} to {new_start.strftime('%H:%M')} - {new_end.strftime('%H:%M')}"
                    )
                else:
                    impact_type = "travel_conflict"
                    msg = (
                        f"Insufficient travel time from {current_event.location} to {dep_event.location} "
                        f"between {current_event.id} and {dep_event.id}. "
                        f"Shifted by {delay} to {new_start.strftime('%H:%M')} - {new_end.strftime('%H:%M')}"
                    )

                causal_path = current_path + [dep_id]

                shift_record = CascadingShift(
                    event_id=dep_id,
                    caused_by_id=current_event.id,
                    impact_type=impact_type,
                    original_start=dep_event.start,
                    original_end=dep_event.end,
                    new_start=new_start,
                    new_end=new_end,
                    delay=delay,
                    path=causal_path,
                    message=msg,
                )
                shifts.append(shift_record)

                # Update the simulated event in the schedule
                shifted_dep = Event(
                    id=dep_event.id,
                    start=new_start,
                    end=new_end,
                    dependent_task_ids=list(dep_event.dependent_task_ids),
                    location=dep_event.location,
                )
                simulated_events[dep_id] = shifted_dep

                # Recurse downstream along this branch
                active_branch.add(dep_id)
                _cascade(shifted_dep, active_branch, causal_path)
                active_branch.remove(dep_id)

    initial_branch = {modified_event.id}
    initial_path = [modified_event.id]
    _cascade(simulated_events[modified_event.id], initial_branch, initial_path)

    return SimulationResult(
        shifts=shifts,
        final_events=simulated_events,
        detected_cycles=detected_cycles,
    )
