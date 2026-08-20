import vlc
import ctypes

def test_log():
    try:
        instance = vlc.Instance("--verbose=2")
        
        @vlc.CallbackDecorators.LogCb
        def log_cb(data, level, ctx, fmt, args):
            print(f"VLC LOG: {level}")
            
        # En algunas versiones de python-vlc esto funciona:
        # instance.log_set(log_cb, None)
        # En otras hay que usar libvlc directamente
        
        print("Log callback definido.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_log()
