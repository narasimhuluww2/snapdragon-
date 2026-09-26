# Hardware-Software Co-Design & NPU Acceleration

### 1. Zero CPU Host Load
By enforcing session.disable_cpu_ep_fallback = "1", workloads are strictly bound to the Qualcomm Hexagon NPU (45 TOPS), ensuring zero CPU resource contention during background executions. This strictly guarantees that heavy games and applications on the Oryon CPU are never throttled by the AI.

### 2. INT8/INT4 Precision Pipeline
Audio transcription (Whisper-tiny), acoustic diarization (TitaNet), and intent extraction (All-MiniLM) run natively on quantized INT8/INT4 weights through the QNN execution provider backend (QnnHtp.dll). This minimizes memory bandwidth overhead on Snapdragon-powered HP OmniBook laptops while maximizing raw token output speed.

### 3. Dynamic QNN Burst Telemetry
By utilizing the onnxruntime-qnn library, we dynamically inject qnn.perf_mode="burst" and qnn.rpc_control_latency="100" run options during inference passes. This allows the Hexagon Tensor Processor (HTP) to achieve minimum Time-to-First-Token (TTFT) when auto-resolving meeting schedule ripples, without wasting continuous power.
