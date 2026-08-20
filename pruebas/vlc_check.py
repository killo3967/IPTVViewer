import vlc
import os
import sys

def get_vlc_info():
    try:
        # Intentar obtener la versión de la instancia
        instance = vlc.Instance()
        version = vlc.libvlc_get_version().decode('utf-8')
        
        # Intentar encontrar la ruta de la DLL que se está cargando
        # El módulo vlc de python carga la DLL dinámicamente.
        # En Windows suele guardarse en la variable _libvlc
        lib_path = "Desconocida"
        if hasattr(vlc, 'dll'):
             lib_path = vlc.dll._name
        
        print(f"Versión de libVLC detectada: {version}")
        print(f"Ruta de la librería cargada: {lib_path}")
        print(f"Plataforma: {sys.platform}")
        
    except Exception as e:
        print(f"Error detectando info de VLC: {e}")

if __name__ == "__main__":
    get_vlc_info()
