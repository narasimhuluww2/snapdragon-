import os
import onnxruntime as ort
try:
    import onnxruntime_qnn as qnn_ep
except ImportError:
    qnn_ep = None

def initialize_npu_session(model_path: str):
    "\""
    Initializes an ONNX Runtime inference session optimized for 
    the Qualcomm Hexagon NPU using the QNN Execution Provider.
    "\""
    print(f"Initializing QNN EP on Snapdragon NPU for model: {model_path}")
    
    if not qnn_ep:
        print("Warning: onnxruntime-qnn not installed. Falling back to CPU Execution Provider.")
        return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        
    print(f"Using onnxruntime-qnn version: {qnn_ep.__version__}")
    
    # 1. Register the QNN Plugin Execution Provider library dynamically
    ep_lib_path = qnn_ep.get_library_path()
    lib_registration_name = "QNNExecutionProvider"
    ort.register_execution_provider_library(lib_registration_name, ep_lib_path)
    
    # 2. Configure session options for HTP (Hexagon Tensor Processor)
    session_options = ort.SessionOptions()
    session_options.log_severity_level = 1
    
    # Disable CPU fallback to guarantee 100% NPU offloading (prevents silent regressions)
    session_options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
    
    # 3. Set QNN HTP Backend options
    ep_options = {
        "backend_path": qnn_ep.get_qnn_htp_path(),
        "session.enable_htp_fp16_precision": "1",
        "htp_performance_mode": "burst",  # Options: burst, high_performance, sustained_high_performance
    }
    
    # Select available QNN EP devices
    all_ep_devices = ort.get_ep_devices()
    selected_ep_devices = [
        device for device in all_ep_devices if device.ep_name == lib_registration_name
    ]
    
    if selected_ep_devices:
        session_options.add_provider_for_devices(selected_ep_devices, ep_options)
        session = ort.InferenceSession(model_path, sess_options=session_options)
        print("Success: Model successfully bound to Qualcomm Hexagon NPU via QNN EP.")
    else:
        print("Warning: QNN device not found. Falling back to CPU Execution Provider.")
        session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        
    return session
