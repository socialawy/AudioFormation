import torch

print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device name: {torch.cuda.get_device_name(0)}")
    print(
        f"Memory total: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB"
    )
