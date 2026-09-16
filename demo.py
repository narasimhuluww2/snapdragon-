"""
AHEAD-AI CLI Demonstration
Snapdragon® AI Lab Build & Present Challenge
Target Platform: Snapdragon-powered HP PCs (Hexagon NPU Acceleration)
"""

import argparse
from datetime import datetime, timedelta
import sys

from engine import (
    Event,
    ParsedScheduleIntent,
    QualcommAIHubParser,
    TravelBuffer,
    apply_parsed_intent_and_simulate,
)


def print_banner(active_provider: str):
    print("=" * 75)
    print("  AHEAD-AI : Autonomous Schedule Intelligence & Ripple Conflict Resolver")
    print("  Qualcomm AI Hub Model Integration | Snapdragon®-Powered HP PCs")
    print("=" * 75)
    print(f"  [AI Runtime Provider] : {active_provider}")
    if active_provider == "QNNExecutionProvider":
        print("  [Hardware Target]     : Qualcomm® Hexagon™ NPU (45 TOPS Accelerated)")
    else:
        print("  [Hardware Target]     : Host Emulation / CPU Fallback (Testbed Mode)")
    print("=" * 75)
    print()


def print_schedule(title: str, events: dict[str, Event]):
    print(f"--- {title} ---")
    print(f"{'Event ID':<18} {'Location':<16} {'Start':<8} {'End':<8} {'Duration':<10}")
    print("-" * 65)
    for ev in sorted(events.values(), key=lambda e: e.start):
        dur = ev.end - ev.start
        mins = int(dur.total_seconds() // 60)
        loc = ev.location or "Unassigned"
        print(
            f"{ev.id:<18} {loc:<16} {ev.start.strftime('%H:%M'):<8} {ev.end.strftime('%H:%M'):<8} {f'{mins} mins':<10}"
        )
    print()


def print_simulation_trace(response):
    print(f">> Natural Language Input : \"{response.intent.raw_text}\"")
    print(f"   [NPU Entity Extraction]: Target='{response.intent.target_event_id}', "
          f"Intent='{response.intent.intent_type}', "
          f"Delta={response.intent.time_delta or 'N/A'}, "
          f"Location={response.intent.new_location or 'Unchanged'}")
    print()

    sim = response.simulation_result
    if sim.has_cycles:
        print("  [!] WARNING: Circular dependency cycle detected and neutralized:")
        for cycle in sim.detected_cycles:
            print(f"      Cycle Chain: {' -> '.join(cycle)}")
        print()

    if not sim.shifts:
        print("  [OK] No downstream ripple conflicts detected. Schedule remains intact.")
    else:
        print(f"  [>] Cascading Disruption Trace ({len(sim.shifts)} downstream shifts triggered):")
        for idx, shift in enumerate(sim.shifts, 1):
            if shift.impact_type == "cycle_detected":
                continue
            orig_win = f"{shift.original_start.strftime('%H:%M')} - {shift.original_end.strftime('%H:%M')}"
            new_win = f"{shift.new_start.strftime('%H:%M')} - {shift.new_end.strftime('%H:%M')}"
            path_str = " -> ".join(shift.path)
            print(f"    {idx}. Impacted: [{shift.event_id}] (caused by {shift.caused_by_id})")
            print(f"       Type       : {shift.impact_type.upper()}")
            print(f"       Causal Path: {path_str}")
            print(f"       Window     : {orig_win}  ==>  {new_win} (+{int(shift.delay.total_seconds() // 60)}m delay)")
    print()


def setup_sample_schedule():
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
        safety_buffer=timedelta(minutes=10),  # Total required transit: 30 mins
    )

    events = {
        "meeting_001": meeting_1,
        "site_visit_001": site_visit,
        "deliverable_001": deliverable,
    }

    deps = {
        "meeting_001": ["site_visit_001"],
        "site_visit_001": ["deliverable_001"],
    }

    buffers = [tb]

    return events, deps, buffers


def run_demo():
    parser = QualcommAIHubParser()
    print_banner(parser.provider)

    events, deps, buffers = setup_sample_schedule()
    print_schedule("Initial Scheduled Workday", events)

    # Demo Prompt 1: Overlap & Multi-Hop Ripple Cascade
    prompt_1 = "Delay meeting_001 by 45 minutes due to executive board review"
    print("=" * 75)
    print("DEMO SCENARIO 1: Voice/Text Reschedule with Multi-Hop Cascading Ripple")
    print("=" * 75)
    resp_1 = apply_parsed_intent_and_simulate(prompt_1, events, deps, buffers, parser=parser)
    print_simulation_trace(resp_1)
    print_schedule("Updated Schedule (Scenario 1 Resolved)", resp_1.simulation_result.final_events)

    # Demo Prompt 2: Travel Buffer & Physical Transit Violation
    events2, deps2, buffers2 = setup_sample_schedule()
    prompt_2 = "Move meeting_001 to 11:15 at HQ_North"
    print("=" * 75)
    print("DEMO SCENARIO 2: Travel Buffer Transit Conflict (Zero-Overlap Delay)")
    print("=" * 75)
    resp_2 = apply_parsed_intent_and_simulate(prompt_2, events2, deps2, buffers2, parser=parser)
    print_simulation_trace(resp_2)
    print_schedule("Updated Schedule (Scenario 2 Resolved)", resp_2.simulation_result.final_events)

    # Demo Scenario 3: Cycle Protection
    events3, _, _ = setup_sample_schedule()
    deps3 = {
        "meeting_001": ["site_visit_001"],
        "site_visit_001": ["meeting_001"],  # Circular dependency
    }
    prompt_3 = "Delay meeting_001 by 45 minutes"
    print("=" * 75)
    print("DEMO SCENARIO 3: Automatic Cycle Prevention in Recursive Traversal")
    print("=" * 75)
    resp_3 = apply_parsed_intent_and_simulate(prompt_3, events3, deps3, parser=parser)
    print_simulation_trace(resp_3)


if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser(description="AHEAD-AI Snapdragon Demonstration CLI")
    parser_arg.add_argument("prompt", nargs="?", help="Optional natural language scheduling prompt to test")
    args = parser_arg.parse_args()

    if args.prompt:
        ai_parser = QualcommAIHubParser()
        print_banner(ai_parser.provider)
        evs, dps, bufs = setup_sample_schedule()
        print_schedule("Initial Workday Schedule", evs)
        resp = apply_parsed_intent_and_simulate(args.prompt, evs, dps, bufs, parser=ai_parser)
        print_simulation_trace(resp)
        print_schedule("Final Resolved Schedule", resp.simulation_result.final_events)
    else:
        run_demo()
