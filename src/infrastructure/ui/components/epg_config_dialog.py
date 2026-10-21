"""Diálogo de configuración de la EPG (columna "Programación")."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


class EPGConfigDialog(QDialog):
    """Ajustes de presentación de la guía en la tabla de canales."""

    def __init__(self, title_only: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de EPG")
        self.setMinimumWidth(430)

        self._title_only_check = QCheckBox("Mostrar solo título en programación")
        self._title_only_check.setChecked(bool(title_only))
        self._title_only_check.setToolTip(
            "Con la casilla marcada, la columna Programación muestra únicamente "
            "el título del programa."
        )

        hint = QLabel(
            "Con la casilla marcada, la columna Programación muestra solo el título "
            "del programa. Si la desmarcas, verás el título, la hora de inicio, una "
            "barra con el tiempo transcurrido, la hora de fin y la duración."
        )
        hint.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_only_check)
        layout.addWidget(hint)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def title_only(self) -> bool:
        """Estado elegido para "mostrar solo título"."""
        return self._title_only_check.isChecked()
