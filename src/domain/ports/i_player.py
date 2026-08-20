from abc import ABC, abstractmethod

class IPlayer(ABC):
    """Puerto de salida (Driven Port) para el control del reproductor multimedia."""
    
    @abstractmethod
    def play(self, url: str):
        """Inicia la reproducción de una URL."""
        pass
    
    @abstractmethod
    def stop(self):
        """Detiene la reproducción."""
        pass
    
    @abstractmethod
    def set_output_window(self, window_id: int):
        """Asocia el reproductor a una ventana/widget específico."""
        pass

    @abstractmethod
    def set_hw_acceleration(self, enabled: bool):
        """Activa o desactiva la aceleración por hardware (requiere reinicio interno)."""
        pass

    @abstractmethod
    def update_engine_options(self, options: dict):
        """Actualiza la configuración técnica del motor (requiere reinicio interno)."""
        pass

    @abstractmethod
    def release(self):
        """Libera recursos del reproductor."""
        pass
