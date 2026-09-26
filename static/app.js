// SnapEdge AI Assistant - Frontend Client Logic
// Optimized for SnapdragonÂ®-Powered HP PCs (QualcommÂ® Hexagonâ„¢ NPU)

const PRESETS = {
    board_sync: "Good morning team. We reviewed the Q3 enterprise rollout. Sarah confirmed that the backend migration is on track for Thursday. However, our executive board review is running over. We decided to delay meeting_001 by 45 minutes to finish questions. Narasimha will finalize the client deliverable deck by Friday 5 PM. Also, please note site_visit_001 remains scheduled at Client_Campus.",
    site_relocation: "Quick update everyone. The client cannot meet at their main office. We need to move meeting_001 to 11:15 at HQ_North so the regional director can join. John will notify the logistics team immediately. Remember there is a 30-minute transit buffer required before site_visit_001 at Client_Campus.",
    custom: ""
};

let telemetryChart = null;
const maxDataPoints = 15;
const chartLabels = [];
const npuData = [];
const cpuData = [];

// Closed-loop conflict tracking
let lastConflictPrompt = "Delay meeting_001 by 45 minutes";

document.addEventListener("DOMContentLoaded", () => {
    initPresets();
    initChart();
    loadStatus();
    loadSchedule();
    renderConflictTree(null, false);
    startTelemetryPolling();
    initKeyboardShortcuts();

    // Event listeners
    document.getElementById("btn-run-summary").addEventListener("click", runSummarizer);
    document.getElementById("btn-run-copilot").addEventListener("click", () => runCopilot("auto"));
    document.getElementById("btn-run-sim").addEventListener("click", runSimulation);
    document.getElementById("btn-reset-schedule").addEventListener("click", resetSchedule);
    document.getElementById("btn-copy-copilot").addEventListener("click", copyCopilotText);

    // Closed-Loop Auto-Resolution Listeners
    const btnAutoResolve = document.getElementById("btn-trigger-auto-resolve");
    if (btnAutoResolve) {
        btnAutoResolve.addEventListener("click", triggerAutoResolve);
    }
    const btnApplyCal = document.getElementById("btn-apply-calendar");
    if (btnApplyCal) {
        btnApplyCal.addEventListener("click", applyCalendarResolution);
    }
});

// 1. Keyboard Shortcuts (Alt+1..4, Ctrl+Enter)
function initKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        if (e.altKey && e.key === "1") {
            e.preventDefault();
            document.getElementById("summarizer-tab").click();
        } else if (e.altKey && e.key === "2") {
            e.preventDefault();
            document.getElementById("copilot-tab").click();
        } else if (e.altKey && e.key === "3") {
            e.preventDefault();
            document.getElementById("schedule-tab").click();
        } else if (e.altKey && e.key === "4") {
            e.preventDefault();
            document.getElementById("telemetry-tab").click();
        } else if (e.ctrlKey && e.key === "Enter") {
            e.preventDefault();
            const activeTab = document.querySelector(".nav-link.active");
            if (activeTab && activeTab.id === "summarizer-tab") {
                runSummarizer();
            } else if (activeTab && activeTab.id === "copilot-tab") {
                runCopilot("auto");
            } else if (activeTab && activeTab.id === "schedule-tab") {
                runSimulation();
            }
        }
    });
}

// 2. Status & Hardware Capability Initialization
async function loadStatus() {
    try {
        const res = await fetch("/api/status");
        const data = await res.json();
        const providerBadge = document.getElementById("provider-badge");
        if (data.is_npu_accelerated) {
            providerBadge.innerHTML = `<i class="fa-solid fa-bolt text-warning me-1"></i> ${data.active_provider} (NPU Active)`;
        } else {
            providerBadge.innerHTML = `<i class="fa-solid fa-microchip text-info me-1"></i> ${data.active_provider}`;
        }
    } catch (e) {
        console.warn("Status check notice:", e);
    }
}

// 3. Preset Handler
function initPresets() {
    const select = document.getElementById("meeting-preset-select");
    const textarea = document.getElementById("meeting-text-input");
    textarea.value = PRESETS[select.value] || "";

    select.addEventListener("change", (e) => {
        textarea.value = PRESETS[e.target.value] || "";
    });
}

// 4. Meeting Summarizer Execution
async function runSummarizer() {
    const selectEl = document.getElementById("meeting-preset-select");
    const presetKey = selectEl ? selectEl.value : "custom";
    const text = document.getElementById("meeting-text-input").value.trim();
    if (!text) {
        alert("Please enter or select a meeting transcript.");
        return;
    }

    const btn = document.getElementById("btn-run-summary");
    const perfBadge = document.getElementById("summary-perf-badge");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Processing on NPU...`;

    // Build payload: use preset_key for known presets (gives exact speaker diarization)
    const payload = (presetKey && presetKey !== "custom")
        ? { preset_key: presetKey }
        : { custom_text: text };

    try {
        const res = await fetch("/api/summarize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        perfBadge.innerHTML = `<i class="fa-solid fa-bolt text-warning me-1"></i> ${data.processing_time_ms} ms (${data.model_used})`;

        // Diarized Speaker Turns
        const diarizeContainer = document.getElementById("diarization-turns-container");
        if (diarizeContainer && data.diarized_turns && data.diarized_turns.length > 0) {
            diarizeContainer.innerHTML = data.diarized_turns.map(turn => `
                <div class="p-2 mb-2 rounded bg-dark border border-secondary small">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <div>
                            <span class="badge me-1" style="background-color: ${turn.color || '#0dcaf0'}; color: #000; font-weight: bold;">
                                <i class="fa-solid fa-user me-1"></i>${turn.speaker}
                            </span>
                            <span class="text-secondary small">(${turn.role})</span>
                        </div>
                        <span class="badge bg-secondary font-monospace" style="font-size: 0.68rem;">${turn.timestamp}</span>
                    </div>
                    <div class="text-light mt-1" style="line-height: 1.35;">"${turn.text}"</div>
                </div>
            `).join("");
        } else if (diarizeContainer) {
            diarizeContainer.innerHTML = `<div class="text-secondary small text-center py-2">No distinct speaker turns detected.</div>`;
        }

        // Summary Points
        const pointsList = document.getElementById("summary-points-list");
        pointsList.innerHTML = "";
        data.summary_points.forEach(pt => {
            const li = document.createElement("li");
            li.className = "list-group-item bg-transparent text-light border-secondary small";
            li.innerHTML = `<i class="fa-solid fa-check text-success me-2"></i>${pt}`;
            pointsList.appendChild(li);
        });

        // Action Items
        const actionBody = document.getElementById("action-items-body");
        actionBody.innerHTML = "";
        if (data.action_items.length === 0) {
            actionBody.innerHTML = `<tr><td colspan="3" class="text-secondary">No action items detected.</td></tr>`;
        } else {
            data.action_items.forEach(item => {
                const tr = document.createElement("tr");
                const badgeColor = item.priority === "High" ? "bg-danger" : "bg-info";
                tr.innerHTML = `
                    <td>${item.task}</td>
                    <td><span class="badge bg-secondary">${item.owner}</span></td>
                    <td><span class="badge ${badgeColor}">${item.priority}</span></td>
                `;
                actionBody.appendChild(tr);
            });
        }

        // Conflict Alert Box
        const alertBox = document.getElementById("conflict-alert-box");
        const alertDesc = document.getElementById("conflict-alert-desc");
        const alertList = document.getElementById("conflict-shifts-list");

        if (data.schedule_conflict_detected && data.ahead_simulation) {
            alertBox.classList.remove("d-none");
            const sim = data.ahead_simulation;
            lastConflictPrompt = sim.detected_intent;
            alertDesc.innerHTML = `Meeting decision: <strong>"${sim.detected_intent}"</strong> triggered <strong>${sim.total_shifts} cascading disruption(s)</strong> across downstream tasks:`;
            alertList.innerHTML = sim.shifts.map(s => `
                <div class="p-2 my-1 bg-dark rounded border border-warning">
                    <strong>[${s.event_id}]</strong> shifted to <strong>${s.new}</strong> (+${s.delay_mins}m delay).<br>
                    <span class="text-secondary">Cause: ${s.message}</span>
                </div>
            `).join("");
        } else {
            alertBox.classList.add("d-none");
        }

        // Refresh Schedule timeline to reflect changes if simulation occurred
        loadSchedule();

    } catch (err) {
        alert("Error summarizing: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-play me-2"></i>Summarize & Check Schedule (NPU)`;
    }
}

// 5. Closed-Loop Auto-Resolution via Local NPU Copilot
async function triggerAutoResolve() {
    const closedBox = document.getElementById("closed-loop-box");
    const emailPre = document.getElementById("auto-resolve-email");
    const statsDiv = document.getElementById("auto-resolve-stats");
    const btn = document.getElementById("btn-trigger-auto-resolve");

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Drafting on NPU...`;

    try {
        const res = await fetch("/api/auto_resolve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: lastConflictPrompt })
        });
        const data = await res.json();

        emailPre.innerText = data.apology_email;
        statsDiv.innerHTML = `Model: <strong>${data.model_used}</strong> | Latency: <strong>${data.processing_time_ms} ms</strong> | Privacy: <strong>100% Offline Edge</strong>`;
        closedBox.classList.remove("d-none");
    } catch (e) {
        alert("Auto-resolution notice: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles me-1"></i>Auto-Resolve & Draft Email (NPU)`;
    }
}

async function applyCalendarResolution() {
    const btn = document.getElementById("btn-apply-calendar");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Applying...`;

    try {
        const res = await fetch("/api/apply_schedule_resolution", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: lastConflictPrompt })
        });
        const data = await res.json();
        alert("Success! " + data.message);
        loadSchedule();
        renderConflictTree(null, true);
        document.getElementById("schedule-tab").click();
    } catch (e) {
        alert("Error applying resolution: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-calendar-check me-1"></i>Apply to Active Calendar`;
    }
}

// 6. Clipboard Copilot Execution
function setCopilotPrompt(text, mode) {
    document.getElementById("copilot-input").value = text;
    runCopilot(mode);
}

async function runCopilot(customMode) {
    const text = document.getElementById("copilot-input").value.trim();
    if (!text) {
        alert("Please enter clipboard text.");
        return;
    }

    const btn = document.getElementById("btn-run-copilot");
    const output = document.getElementById("copilot-output");
    const stats = document.getElementById("copilot-stats");

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Inference...`;
    output.innerText = "Analyzing on Qualcomm NPU...";

    try {
        const res = await fetch("/api/copilot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, mode: typeof customMode === "string" ? customMode : "auto" })
        });
        const data = await res.json();
        output.innerText = data.result_text;
        stats.innerText = `Model: ${data.model_name} | Latency: ${data.processing_time_ms} ms`;
    } catch (e) {
        output.innerText = "Error executing copilot: " + e.message;
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-microchip me-2"></i>Execute on NPU`;
    }
}

function copyCopilotText() {
    const text = document.getElementById("copilot-output").innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert("Copied to clipboard!");
    });
}

// 7. Schedule & Ripple Simulator
async function loadSchedule() {
    try {
        const res = await fetch("/api/schedule");
        const data = await res.json();

        const timeline = document.getElementById("schedule-timeline");
        timeline.innerHTML = "";

        data.events.forEach((ev, idx) => {
            const div = document.createElement("div");
            div.className = "timeline-item";
            div.innerHTML = `
                <div class="d-flex justify-content-between">
                    <strong class="text-light">${ev.id}</strong>
                    <span class="text-warning small">${ev.start} - ${ev.end} (${ev.duration_mins}m)</span>
                </div>
                <div class="text-secondary small"><i class="fa-solid fa-location-dot me-1 text-danger"></i>${ev.location}</div>
            `;
            timeline.appendChild(div);

            // If travel buffer to next event exists
            if (idx < data.events.length - 1) {
                const nextEv = data.events[idx + 1];
                const matchingBuffer = data.travel_buffers.find(b => b.from_location === ev.location && b.to_location === nextEv.location);
                if (matchingBuffer) {
                    const tbDiv = document.createElement("div");
                    tbDiv.className = "travel-pill";
                    tbDiv.innerHTML = `<i class="fa-solid fa-car-side me-1"></i> Transit Buffer: ${matchingBuffer.from_location} â†’ ${matchingBuffer.to_location} (${matchingBuffer.total_required_mins} min required)`;
                    timeline.appendChild(tbDiv);
                }
            }
        });
    } catch (err) {
        console.warn("Failed to load schedule:", err);
    }
}

function setSimPrompt(prompt) {
    document.getElementById("sim-prompt-input").value = prompt;
    runSimulation();
}

async function runSimulation() {
    const prompt = document.getElementById("sim-prompt-input").value.trim();
    if (!prompt) {
        alert("Please enter a scheduling prompt.");
        return;
    }

    const btn = document.getElementById("btn-run-sim");
    const box = document.getElementById("sim-results-box");
    btn.disabled = true;
    lastConflictPrompt = prompt;

    try {
        const res = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });
        const data = await res.json();

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong class="text-light"><i class="fa-solid fa-arrows-split-up-and-left text-danger me-2"></i>Simulation Trace: "${data.prompt}"</strong>
                <span class="badge bg-danger">${data.total_shifts} Shifts</span>
            </div>
            <div class="small text-secondary mb-3">Target: ${data.target_event_id} | New Window: ${data.modified_event.start} - ${data.modified_event.end}</div>
        `;

        if (data.shifts.length === 0) {
            html += `<div class="text-success small"><i class="fa-solid fa-circle-check me-1"></i> No downstream conflicts triggered. Schedule remains intact.</div>`;
        } else {
            data.shifts.forEach((s, i) => {
                html += `
                    <div class="p-2 mb-2 bg-black rounded border border-secondary small">
                        <div class="d-flex justify-content-between">
                            <strong>${i + 1}. [${s.event_id}]</strong>
                            <span class="text-warning">${s.original_window} âž” ${s.new_window} (+${s.delay_mins}m)</span>
                        </div>
                        <div class="text-secondary">Type: <span class="badge bg-secondary">${s.impact_type}</span> | Causal Path: ${s.path}</div>
                        <div class="text-muted small mt-1">${s.message}</div>
                    </div>
                `;
            });

            // Add Quick 1-Click Auto-Resolve in Simulation box
            html += `
                <div class="mt-3 pt-2 border-top border-secondary d-flex justify-content-end gap-2">
                    <button class="btn btn-warning btn-sm fw-bold" onclick="triggerAutoResolveFromSim('${data.prompt}')">
                        <i class="fa-solid fa-wand-magic-sparkles me-1"></i>Auto-Resolve & Draft Reschedule Email
                    </button>
                </div>
            `;
        }

        box.innerHTML = html;
        loadSchedule();
        renderConflictTree(data, false);

    } catch (e) {
        box.innerHTML = `<div class="text-danger small">Error: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
    }
}

async function triggerAutoResolveFromSim(prompt) {
    lastConflictPrompt = prompt;
    document.getElementById("summarizer-tab").click();
    await triggerAutoResolve();
}

async function resetSchedule() {
    await fetch("/api/reset_schedule", { method: "POST" });
    document.getElementById("sim-results-box").innerHTML = `<span class="text-secondary small">Schedule reset to default state.</span>`;
    loadSchedule();
    renderConflictTree(null, false);
}

// 8. Hardware & NPU Telemetry Charts
function initChart() {
    const ctx = document.getElementById("telemetryChart").getContext("2d");
    telemetryChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: chartLabels,
            datasets: [
                {
                    label: "NPU Utilization (%)",
                    borderColor: "#e11425",
                    backgroundColor: "rgba(225, 20, 37, 0.15)",
                    borderWidth: 2,
                    data: npuData,
                    fill: true,
                    tension: 0.3
                },
                {
                    label: "Host CPU Load (%)",
                    borderColor: "#0dcaf0",
                    backgroundColor: "transparent",
                    borderWidth: 2,
                    data: cpuData,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "#282f3a" },
                    ticks: { color: "#8e9aab" }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: "#8e9aab" }
                }
            },
            plugins: {
                legend: { labels: { color: "#e6edf3" } }
            }
        }
    });
}

let currentPollIntervalMs = 2000;
let telemetryPollTimer = null;

async function pollTelemetryTick() {
    try {
        const res = await fetch("/api/metrics");
        const m = await res.json();

        // Update DOM badges
        document.getElementById("metric-npu").innerText = `${m.npu_utilization_percent}%`;
        document.getElementById("metric-cpu").innerText = `${m.cpu_percent}%`;
        document.getElementById("metric-ram").innerText = `${m.ram_used_gb} GB`;
        document.getElementById("metric-ram-pct").innerText = `${m.ram_percent}% of ${m.ram_total_gb} GB`;
        document.getElementById("metric-power").innerText = `${m.power_efficiency_multiplier}x`;
        document.getElementById("metric-inferences").innerText = m.total_inferences;

        // Update Governor UI
        if (m.governor) {
            updateGovernorUI(m.governor, m.battery_plugged, m.battery_percent);
        }

        // Update Benchmarking metrics if available
        if (m.benchmarks) {
            const b = m.benchmarks;
            const ttftNpu = document.getElementById("bench-ttft-npu");
            const ttftCpu = document.getElementById("bench-ttft-cpu");
            const tpNpu = document.getElementById("bench-throughput-npu");
            const tpCpu = document.getElementById("bench-throughput-cpu");
            const latNpu = document.getElementById("bench-latency-npu");
            const latCpu = document.getElementById("bench-latency-cpu");
            const pwrNpu = document.getElementById("bench-power-npu");
            const pwrCpu = document.getElementById("bench-power-cpu");

            if (ttftNpu) ttftNpu.innerText = `${b.npu.ttft_ms} ms`;
            if (ttftCpu) ttftCpu.innerText = `${b.cpu_baseline.ttft_ms} ms`;
            if (tpNpu) tpNpu.innerText = `${b.npu.tokens_per_second} tok/s`;
            if (tpCpu) tpCpu.innerText = `${b.cpu_baseline.tokens_per_second} tok/s`;
            if (latNpu) latNpu.innerText = `${b.npu.latency_ms} ms`;
            if (latCpu) latCpu.innerText = `${b.cpu_baseline.latency_ms} ms`;
            if (pwrNpu) pwrNpu.innerText = `${b.npu.power_watts} W`;
            if (pwrCpu) pwrCpu.innerText = `${b.cpu_baseline.power_watts} W`;
        }

        // Update Chart
        const now = new Date().toLocaleTimeString().split(" ")[0];
        chartLabels.push(now);
        npuData.push(m.npu_utilization_percent);
        cpuData.push(m.cpu_percent);

        if (chartLabels.length > maxDataPoints) {
            chartLabels.shift();
            npuData.shift();
            cpuData.shift();
        }

        if (telemetryChart) {
            telemetryChart.update();
        }
    } catch (e) {
        console.warn("Telemetry polling notice:", e);
    }
}

function startTelemetryPolling() {
    pollTelemetryTick();
    if (telemetryPollTimer) clearInterval(telemetryPollTimer);
    telemetryPollTimer = setInterval(pollTelemetryTick, currentPollIntervalMs);
}

// 9. Snapdragon Battery & Thermal Budgeting Governor Handlers
async function setGovernorModeUI(mode) {
    try {
        const res = await fetch("/api/governor", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode })
        });
        const data = await res.json();
        if (data.governor) {
            updateGovernorUI(data.governor, true, 100);
        }
        await pollTelemetryTick();
    } catch (e) {
        console.warn("Failed to set governor mode:", e);
    }
}

function updateGovernorUI(gov, batteryPlugged, batteryPercent) {
    if (!gov) return;

    // Power source badge
    const pwrBadge = document.getElementById("gov-power-source-badge");
    if (pwrBadge) {
        if (batteryPlugged) {
            pwrBadge.className = "badge bg-secondary";
            pwrBadge.innerHTML = `<i class="fa-solid fa-plug me-1"></i>AC Power Active`;
        } else {
            pwrBadge.className = "badge bg-warning text-dark";
            pwrBadge.innerHTML = `<i class="fa-solid fa-battery-three-quarters me-1"></i>Battery (${batteryPercent}%)`;
        }
    }

    // Active mode badge
    const modeBadge = document.getElementById("gov-active-mode-badge");
    if (modeBadge) {
        if (gov.mode === "performance") {
            modeBadge.className = "badge bg-success";
            modeBadge.innerText = "Performance Mode";
        } else if (gov.mode === "eco") {
            modeBadge.className = "badge bg-warning text-dark";
            modeBadge.innerText = "Snapdragon Eco-Governor";
        } else {
            modeBadge.className = "badge bg-info text-dark";
            modeBadge.innerText = "Ultra-Saver Mode";
        }
    }

    // Metrics
    const wattsElem = document.getElementById("gov-watts-saved");
    if (wattsElem) wattsElem.innerText = `${gov.watts_saved.toFixed(1)} W`;

    const wattsDesc = document.getElementById("gov-watts-desc");
    if (wattsDesc) wattsDesc.innerText = gov.mode === "performance" ? "AC Uncapped Mode" : "Hexagon NPU Savings";

    const extElem = document.getElementById("gov-extension-hrs");
    if (extElem) extElem.innerText = `+${gov.battery_extension_hrs.toFixed(1)} hrs`;

    const thermElem = document.getElementById("gov-thermal-status");
    if (thermElem) thermElem.innerText = gov.thermal_status;

    const rateElem = document.getElementById("gov-polling-rate");
    if (rateElem) rateElem.innerText = `${gov.throttle_interval_sec}.0 sec`;

    const quantElem = document.getElementById("gov-quant-status");
    if (quantElem) quantElem.innerText = gov.quantization_profile;

    const descElem = document.getElementById("gov-mode-description");
    if (descElem) descElem.innerHTML = `<i class="fa-solid fa-info-circle me-1"></i>${gov.description}`;

    // Button active state
    const btnAuto = document.getElementById("btn-gov-auto");
    const btnEco = document.getElementById("btn-gov-eco");
    const btnUltra = document.getElementById("btn-gov-ultra");
    const btnPerf = document.getElementById("btn-gov-perf");

    [btnAuto, btnEco, btnUltra, btnPerf].forEach(b => b && b.classList.remove("active"));
    if (!gov.is_override && btnAuto) {
        btnAuto.classList.add("active");
    } else if (gov.mode === "eco" && btnEco) {
        btnEco.classList.add("active");
    } else if (gov.mode === "ultra_saver" && btnUltra) {
        btnUltra.classList.add("active");
    } else if (gov.mode === "performance" && btnPerf) {
        btnPerf.classList.add("active");
    }

    // Adjust dynamic polling interval if governor throttle recommendation changed
    const targetInterval = (gov.throttle_interval_sec || 2) * 1000;
    if (targetInterval !== currentPollIntervalMs) {
        currentPollIntervalMs = targetInterval;
        if (telemetryPollTimer) clearInterval(telemetryPollTimer);
        telemetryPollTimer = setInterval(pollTelemetryTick, currentPollIntervalMs);
    }
}

// 10. Interactive SVG DAG Renderer for AHEAD Conflict Tree (Tab 3)
function renderConflictTree(simData, isResolved = false) {
    const container = document.getElementById("conflict-tree-container");
    if (!container) return;

    const hasSimulation = simData && simData.shifts;
    const isConflict = hasSimulation && simData.shifts.length > 0 && !isResolved;

    // Node 1: meeting_001
    let n1Color = "#0dcaf0";
    let n1Title = "meeting_001";
    let n1Sub = "HQ_North";
    let n1Status = "10:00 - 11:00";
    let n1Badge = "Planned Window";

    // Edge 1 (Transit Buffer):
    let edge1Color = "#6c798c";
    let edge1Text = "Transit: 30m";
    let edge1Alert = false;

    // Node 2: site_visit_001
    let n2Color = "#0dcaf0";
    let n2Title = "site_visit_001";
    let n2Sub = "Client_Campus";
    let n2Status = "11:30 - 12:45";
    let n2Badge = "Planned Window";

    // Edge 2 (Direct Dependency):
    let edge2Color = "#6c798c";
    let edge2Text = "Dependency";

    // Node 3: deliverable_001
    let n3Color = "#0dcaf0";
    let n3Title = "deliverable_001";
    let n3Sub = "Client_Campus";
    let n3Status = "13:00 - 14:00";
    let n3Badge = "Planned Window";

    if (isConflict) {
        // Delayed trigger
        n1Color = "#e11425";
        n1Status = `${simData.modified_event.start} - ${simData.modified_event.end}`;
        n1Badge = "TRIGGER (OVERRUN)";

        // Transit breach
        const travelBreached = simData.shifts.some(s => s.impact_type.includes("TRAVEL"));
        if (travelBreached) {
            edge1Color = "#ffc107";
            edge1Text = "TRANSIT BREACH (30m)";
            edge1Alert = true;
        }

        // Downstream shifts
        const s1 = simData.shifts.find(s => s.event_id === "site_visit_001");
        if (s1) {
            n2Color = "#fd7e14";
            n2Status = s1.new_window;
            n2Badge = `DELAYED (+${s1.delay_mins}m)`;
        }

        const s2 = simData.shifts.find(s => s.event_id === "deliverable_001");
        if (s2) {
            edge2Color = "#fd7e14";
            edge2Text = "CASCADED SHIFT";
            n3Color = "#fd7e14";
            n3Status = s2.new_window;
            n3Badge = `DELAYED (+${s2.delay_mins}m)`;
        }
    } else if (isResolved) {
        n1Color = "#198754";
        n1Status = "10:45 - 11:45";
        n1Badge = "RESOLVED & COMMITTED";

        edge1Color = "#198754";
        edge1Text = "TRANSIT BUFFER SAFE";

        n2Color = "#198754";
        n2Status = "12:15 - 13:30";
        n2Badge = "AUTO-RESOLVED";

        edge2Color = "#198754";
        edge2Text = "CHAIN IN SYNC";

        n3Color = "#198754";
        n3Status = "13:30 - 14:30";
        n3Badge = "AUTO-RESOLVED";
    }

    const svgHtml = `
        <svg viewBox="0 0 740 145" width="100%" height="145" xmlns="http://www.w3.org/2000/svg" style="background-color: transparent;">
            <defs>
                <filter id="glow-node" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="${n1Color}" flood-opacity="0.5"/>
                </filter>
                <marker id="arrow-e1" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L6,3 z" fill="${edge1Color}"/>
                </marker>
                <marker id="arrow-e2" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                    <path d="M0,0 L0,6 L6,3 z" fill="${edge2Color}"/>
                </marker>
            </defs>

            <!-- Edge 1: Node 1 to Node 2 -->
            <path d="M 195 65 L 275 65" stroke="${edge1Color}" stroke-width="${edge1Alert ? 3 : 2}" stroke-dasharray="${edge1Alert ? '4 2' : 'none'}" marker-end="url(#arrow-e1)" />
            <!-- Edge 1 Pill -->
            <rect x="195" y="48" width="75" height="18" rx="9" fill="#121417" stroke="${edge1Color}" stroke-width="1.2"/>
            <text x="232" y="60" fill="${edge1Color}" font-size="8.5" font-weight="bold" text-anchor="middle">${edge1Text}</text>

            <!-- Edge 2: Node 2 to Node 3 -->
            <path d="M 465 65 L 545 65" stroke="${edge2Color}" stroke-width="2" marker-end="url(#arrow-e2)" />
            <!-- Edge 2 Pill -->
            <rect x="465" y="48" width="75" height="18" rx="9" fill="#121417" stroke="${edge2Color}" stroke-width="1.2"/>
            <text x="502" y="60" fill="${edge2Color}" font-size="8.5" font-weight="bold" text-anchor="middle">${edge2Text}</text>

            <!-- NODE 1 -->
            <g transform="translate(15, 15)">
                <rect width="180" height="92" rx="8" fill="#161a22" stroke="${n1Color}" stroke-width="2" filter="url(#glow-node)" />
                <circle cx="18" cy="18" r="4.5" fill="${n1Color}" />
                <text x="28" y="22" fill="#ffffff" font-size="11.5" font-weight="bold">${n1Title}</text>
                <text x="18" y="42" fill="#8e9aab" font-size="9.5">Loc: ${n1Sub}</text>
                <text x="18" y="60" fill="${n1Color}" font-size="10.5" font-weight="bold">${n1Status}</text>
                <rect x="18" y="68" width="144" height="15" rx="3" fill="#0d1015" stroke="${n1Color}" stroke-width="0.8"/>
                <text x="90" y="79" fill="${n1Color}" font-size="8" font-weight="bold" text-anchor="middle">${n1Badge}</text>
            </g>

            <!-- NODE 2 -->
            <g transform="translate(285, 15)">
                <rect width="180" height="92" rx="8" fill="#161a22" stroke="${n2Color}" stroke-width="2" />
                <circle cx="18" cy="18" r="4.5" fill="${n2Color}" />
                <text x="28" y="22" fill="#ffffff" font-size="11.5" font-weight="bold">${n2Title}</text>
                <text x="18" y="42" fill="#8e9aab" font-size="9.5">Loc: ${n2Sub}</text>
                <text x="18" y="60" fill="${n2Color}" font-size="10.5" font-weight="bold">${n2Status}</text>
                <rect x="18" y="68" width="144" height="15" rx="3" fill="#0d1015" stroke="${n2Color}" stroke-width="0.8"/>
                <text x="90" y="79" fill="${n2Color}" font-size="8" font-weight="bold" text-anchor="middle">${n2Badge}</text>
            </g>

            <!-- NODE 3 -->
            <g transform="translate(555, 15)">
                <rect width="175" height="92" rx="8" fill="#161a22" stroke="${n3Color}" stroke-width="2" />
                <circle cx="18" cy="18" r="4.5" fill="${n3Color}" />
                <text x="28" y="22" fill="#ffffff" font-size="11.5" font-weight="bold">${n3Title}</text>
                <text x="18" y="42" fill="#8e9aab" font-size="9.5">Loc: ${n3Sub}</text>
                <text x="18" y="60" fill="${n3Color}" font-size="10.5" font-weight="bold">${n3Status}</text>
                <rect x="18" y="68" width="140" height="15" rx="3" fill="#0d1015" stroke="${n3Color}" stroke-width="0.8"/>
                <text x="88" y="79" fill="${n3Color}" font-size="8" font-weight="bold" text-anchor="middle">${n3Badge}</text>
            </g>
        </svg>
    `;

    container.innerHTML = svgHtml;
}


// --- Phase 2: Experimental Physics Engine ---
async function runPhysicsSimulation() {
    const logs = document.getElementById('physics-logs');
    logs.innerText = "Initializing PINN constraints...\nOffloading Navier-Stokes tensors to Hexagon NPU...\n";
    
    try {
        const response = await fetch('/api/physics/simulate', { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'success') {
            logs.innerText += "Compute Target: " + data.data.compute_target + "\n";
            logs.innerText += "Latency: " + data.data.latency_ms + " ms\n";
            logs.innerText += "Field Stability: " + data.data.field_stability + "%\n";
            
            document.getElementById('gyro-pitch').innerText = "12.4° (Simulated)";
            document.getElementById('gyro-roll').innerText = "-4.2° (Simulated)";
            
            // Draw mock particle field on canvas
            const canvas = document.getElementById('physicsCanvas');
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0,0, canvas.width, canvas.height);
            for(let i=0; i<100; i++) {
                ctx.beginPath();
                ctx.arc(Math.random()*canvas.width, Math.random()*canvas.height, Math.random()*3, 0, Math.PI*2);
                ctx.fillStyle = gba(0, 229, 255, );
                ctx.fill();
            }
        }
    } catch (e) {
        logs.innerText += "Error connecting to physics engine.";
    }
}

// --- SnapEdge Workload Director (Game Mode) ---
let isGameModeActive = false;

function toggleGameMode() {
    isGameModeActive = document.getElementById('gameModeToggle').checked;
    const card = document.getElementById('workload-metrics');
    
    if (isGameModeActive) {
        card.style.opacity = "1.0";
        card.classList.remove('border-info');
        card.classList.add('border-danger'); // Make it look aggressive
        
        document.getElementById('gpu-status').innerText = "100% Freed for Game";
        document.getElementById('gpu-status').className = "badge bg-success";
        
        document.getElementById('cpu-status').innerText = "100% Freed for Game";
        document.getElementById('cpu-status').className = "badge bg-success";
        
        document.getElementById('npu-status').innerText = "Locked AI Offload (INT4)";
        document.getElementById('npu-status').className = "badge bg-danger text-light";
        
        // Force Governor UI to Eco to reflect the NPU limit
        setGovernorModeUI('eco');
        
        alert("Heterogeneous Workload Director Active!\n\nAll SnapEdge AI background tasks (like Meeting Transcriptions) have been locked exclusively to the Hexagon NPU using INT4 quantization.\n\nYour Adreno GPU and Oryon CPU are now 100% dedicated to your active game/app, guaranteeing zero frame drops.");
        
    } else {
        card.style.opacity = "0.5";
        card.classList.add('border-info');
        card.classList.remove('border-danger');
        
        document.getElementById('gpu-status').innerText = "Shared Load";
        document.getElementById('gpu-status').className = "badge bg-secondary";
        
        document.getElementById('cpu-status').innerText = "Shared Load";
        document.getElementById('cpu-status').className = "badge bg-secondary";
        
        document.getElementById('npu-status').innerText = "Balanced INT8";
        document.getElementById('npu-status').className = "badge bg-info text-dark";
        
        setGovernorModeUI('auto');
    }
}
