
import subprocess

processes = [
    subprocess.Popen(["python", "game_save_monitor.py"]),
    subprocess.Popen(["python", "start_vignette_service.py"]),
    subprocess.Popen(["python", "web_server.py"])
]

try:
    for p in processes:
        p.wait()
except KeyboardInterrupt:
    for p in processes:
        p.terminate()