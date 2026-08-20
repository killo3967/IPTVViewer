# pruebas/test_mpv.py
import os
import sys
from pathlib import Path

# Configuración del PATH para encontrar libmpv
bin_path = (Path(__file__).parent.parent / "bin").absolute()
if bin_path.exists():
    # Para Python 3.8+
    os.add_dll_directory(str(bin_path))
    # Para versiones que miran PATH o legacy (o ctypes que mira PATH)
    os.environ["PATH"] = str(bin_path) + os.pathsep + os.environ["PATH"]
    print(f"Directorio de DLLs añadido al PATH y os.add_dll_directory: {bin_path}")

try:
    import mpv
    print("Módulo python-mpv importado con éxito.")
    
    # Intentar instanciar el reproductor (esto cargará la DLL)
    player = mpv.MPV()
    print("Instancia de MPV creada con éxito. La DLL es compatible.")
    
    # Si quieres probar un stream real:
    # player.play("https://www.sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4")
    # import time; time.sleep(5)
    
except ImportError as e:
    print(f"Error: No se pudo importar python-mpv. Asegúrate de que 'pip install python-mpv' se ejecutó.")
except OSError as e:
    print(f"Error de sistema al cargar la DLL: {e}")
    print("Asegúrate de que 'mpv-1.dll' o 'libmpv-2.dll' están en la carpeta 'bin' y son de 64 bits.")
except Exception as e:
    print(f"Se produjo un error inesperado: {e}")
