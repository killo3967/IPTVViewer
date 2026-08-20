import os
import sys
from pathlib import Path

# --- DLL Setup ANTES de import mpv ---
bin_path = Path(__file__).parent.parent / "bin"
if bin_path.exists():
    abs_bin_path = str(bin_path.absolute())
    if sys.version_info >= (3, 8):
        os.add_dll_directory(abs_bin_path)
    os.environ["PATH"] = abs_bin_path + os.pathsep + os.environ["PATH"]
# -------------------------------------

import mpv
import threading
import time

def test_logging():
    log_file = "logs/mpv_test.log"
    if os.path.exists(log_file): os.remove(log_file)
    
    player = mpv.MPV(loglevel='debug')
    
    @player.log_handler
    def my_log(level, prefix, text):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{level}: {prefix}: {text}\n")
    
    print("Iniciando reproducción para generar logs...")
    # Usar una URL que falle o que sea lenta para generar tráfico de logs
    player.play("http://invalid_stream_url_test")
    time.sleep(2)
    
    if os.path.exists(log_file):
        print(f"Éxito: Log creado en {log_file}")
        with open(log_file, "r") as f:
            print("Primeras líneas:")
            print("".join(f.readlines()[:5]))
    else:
        print("Error: No se creó el archivo de log.")

if __name__ == "__main__":
    test_logging()
