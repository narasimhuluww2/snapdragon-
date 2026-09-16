from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class Event:
    """
    Represents a scheduled event.

    Example:
        Meeting from 10:00 to 11:00
        that affects assignment_001.
    """

    id: str
    start: datetime
    end: datetime
    dependent_task_ids: List[str] = field(default_factory=list)
    location: Optional[str] = None

    def overlaps(self, other: "Event") -> bool:
        """
        Returns True when two events actually overlap.

        Touching boundaries do NOT count as an overlap.
        Example:
            Event A: 10:00 - 11:00
            Event B: 11:00 - 12:00
            -> False
        """
        return self.start < other.end and other.start < self.end


@dataclass
class Task:
    """
    Represents a task that can be affected by an event.
    """

    id: str
    duration: timedelta
    deadline: datetime
    status: str = "pending"


@dataclass
class TravelBuffer:
    """
    Represents travel time required between two locations.
    """

    id: str
    from_location: str
    to_location: str
    travel_duration: timedelta
    safety_buffer: timedelta = timedelta(0)

    @property
    def required_time(self) -> timedelta:
        """
        Total time required for travel including safety margin.
        """
        return self.travel_duration + self.safety_buffer

    def has_sufficient_time(self, available_time: timedelta) -> bool:
        """
        Checks whether the available transition time is sufficient.
        """
        return available_time >= self.required_time


@dataclass
class Constraint:
    """
    Represents a scheduling constraint.

    type can be:
        - "travel"
        - "deadline"
        - "overlap"
    """

    type: str
    target_id: str
    limit: datetime | timedelta


@dataclass
class RippleImpact:
    """
    Represents one detected ripple effect.
    """

    source_id: str
    impacted_id: str
    impact_type: str
    message: str = ""


def check_ripple_effect(
    modified_event: Event,
    dependency_graph: dict[str, List[str]],
    events: dict[str, Event],
    travel_buffers: Optional[dict[tuple[str, str], TravelBuffer] | List[TravelBuffer]] = None,
) -> List[RippleImpact]:
    """
    Check direct dependencies of a modified event.

    Checks:
        1. Direct scheduling overlaps.
        2. Insufficient travel transition times between different locations.
    """

    impacts: List[RippleImpact] = []

    buffer_map: dict[tuple[str, str], TravelBuffer] = {}
    if travel_buffers:
        if isinstance(travel_buffers, list):
            buffer_map = {
                (tb.from_location, tb.to_location): tb for tb in travel_buffers
            }
        elif isinstance(travel_buffers, dict):
            buffer_map = travel_buffers

    dependent_ids = dependency_graph.get(
        modified_event.id,
        []
    )

    for dependent_id in dependent_ids:

        dependent_event = events.get(dependent_id)

        # Dependency may not have a scheduled event.
        if dependent_event is None:
            continue

        # 1. Check actual overlap.
        # Touching boundaries are NOT considered conflicts.
        if modified_event.overlaps(dependent_event):
            impacts.append(
                RippleImpact(
                    source_id=modified_event.id,
                    impacted_id=dependent_event.id,
                    impact_type="overlap",
                    message=(
                        f"{modified_event.id} overlaps "
                        f"with {dependent_event.id}"
                    ),
                )
            )
            continue

        # 2. Check travel buffer requirements when locations differ.
        if (
            buffer_map
            and modified_event.location
            and dependent_event.location
            and modified_event.location != dependent_event.location
        ):
            if modified_event.end <= dependent_event.start:
                transition = dependent_event.start - modified_event.end
                route = (modified_event.location, dependent_event.location)
                buffer = buffer_map.get(route)
                if buffer and not buffer.has_sufficient_time(transition):
                    impacts.append(
                        RippleImpact(
                            source_id=modified_event.id,
                            impacted_id=dependent_event.id,
                            impact_type="travel_conflict",
                            message=(
                                f"Insufficient travel time from {modified_event.location} "
                                f"to {dependent_event.location} between {modified_event.id} "
                                f"and {dependent_event.id}. "
                                f"Required: {buffer.required_time}, Available: {transition}"
                            ),
                        )
                    )
            elif dependent_event.end <= modified_event.start:
                transition = modified_event.start - dependent_event.end
                route = (dependent_event.location, modified_event.location)
                buffer = buffer_map.get(route)
                if buffer and not buffer.has_sufficient_time(transition):
                    impacts.append(
                        RippleImpact(
                            source_id=modified_event.id,
                            impacted_id=dependent_event.id,
                            impact_type="travel_conflict",
                            message=(
                                f"Insufficient travel time from {dependent_event.location} "
                                f"to {modified_event.location} between {dependent_event.id} "
                                f"and {modified_event.id}. "
                                f"Required: {buffer.required_time}, Available: {transition}"
                            ),
                        )
                    )

    return impacts
