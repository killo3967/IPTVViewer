import vlc
instance = vlc.Instance()
print(f"Has log_get: {hasattr(instance, 'log_get')}")
