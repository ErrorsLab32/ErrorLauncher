from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QLabel


class AccessCodeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Код доступа к тестовой сборке")
        layout = QFormLayout(self)
        layout.addRow(QLabel("Введите код доступа к тестовой сборке."))
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setMinimumWidth(300)
        layout.addRow("Код доступа", self.token_input)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def token(self) -> str:
        return self.token_input.text()
