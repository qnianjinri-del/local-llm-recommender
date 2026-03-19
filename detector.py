import platform
import psutil
import subprocess


def detect_nvidia_gpu():
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits"
        ]
        output = subprocess.check_output(cmd, text=True, encoding="utf-8")
        gpus = []

        for line in output.strip().splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                gpus.append({
                    "vendor": "NVIDIA",
                    "name": parts[0],
                    "vram_gb": round(float(parts[1]) / 1024, 1),
                    "driver": parts[2],
                })

        return gpus
    except Exception:
        return []


def get_hardware_info():
    info = {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu": platform.processor(),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
        "gpus": detect_nvidia_gpu(),
    }
    return info


if __name__ == "__main__":
    hardware = get_hardware_info()
    print(hardware)