import numpy as np
import onnxruntime as ort

def execute_optimized_inference(session, input_tensor: np.ndarray):
    "\""
    Executes an inference pass with custom run options targeting 
    maximum NPU throughput and minimum Time-to-First-Token (TTFT).
    "\""
    run_options = ort.RunOptions()
    
    # Force performance burst profile for low-latency copilot generation
    run_options.add_run_config_entry("qnn.perf_mode", "burst")
    run_options.add_run_config_entry("qnn.rpc_control_latency", "100")
    
    input_name = session.get_inputs()[0].name
    
    # Run forward pass entirely on the Hexagon NPU
    outputs = session.run(None, {input_name: input_tensor}, run_options)
    return outputs
