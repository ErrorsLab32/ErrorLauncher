from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoginView(QWidget):
    login_requested = Signal()
    register_requested = Signal()
    recovery_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")

        title = QLabel("ERRORLABS PLAYTEST")
        title.setObjectName("loginBrandTitle")
        subtitle = QLabel("Доступ к тестовым сборкам")
        subtitle.setObjectName("mutedLabel")

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин")
        self.login_input.setClearButtonEnabled(True)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        login_button = QPushButton("Войти")
        self.login_button = login_button
        self.login_button.setObjectName("primaryButton")
        login_button.clicked.connect(self.login_requested)

        register_button = QPushButton("Создать аккаунт")
        register_button.setObjectName("linkButton")
        register_button.clicked.connect(self.register_requested)

        recovery_button = QPushButton("Восстановить пароль")
        recovery_button.setObjectName("linkButton")
        recovery_button.clicked.connect(self.recovery_requested)

        self.error_label = QLabel()
        self.error_label.setObjectName("mutedLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QFrame()
        form.setObjectName("authForm")
        form.setMinimumWidth(320)
        form.setMaximumWidth(370)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        form_layout.addWidget(title)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(26)
        form_layout.addWidget(self.login_input)
        form_layout.addWidget(self.password_input)
        form_layout.addSpacing(4)
        form_layout.addWidget(login_button)
        form_layout.addWidget(self.error_label)
        form_layout.addSpacing(8)
        form_layout.addWidget(register_button)
        form_layout.addWidget(recovery_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()
        layout.addWidget(form, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def set_login_in_progress(self, in_progress: bool) -> None:
        self.login_button.setEnabled(not in_progress)

    def show_login_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def clear_login_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()
