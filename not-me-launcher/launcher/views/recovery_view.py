from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RecoveryView(QWidget):
    password_change_requested = Signal()
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")

        title = QLabel("Восстановление пароля")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Используйте шестизначный код восстановления")
        subtitle.setObjectName("mutedLabel")

        form = QFrame()
        form.setObjectName("authForm")
        form.setMinimumWidth(360)
        form.setMaximumWidth(420)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        form_layout.addWidget(title)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(20)

        login_input = QLineEdit()
        login_input.setPlaceholderText("Логин")
        code_input = QLineEdit()
        code_input.setPlaceholderText("Шестизначный код")
        code_input.setMaxLength(6)
        new_password_input = QLineEdit()
        new_password_input.setPlaceholderText("Новый пароль")
        new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        repeat_password_input = QLineEdit()
        repeat_password_input.setPlaceholderText("Повторите пароль")
        repeat_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        for field in (
            login_input,
            code_input,
            new_password_input,
            repeat_password_input,
        ):
            form_layout.addWidget(field)

        change_button = QPushButton("Сменить пароль")
        change_button.setObjectName("primaryButton")
        change_button.clicked.connect(self.password_change_requested)
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.back_requested)
        form_layout.addSpacing(4)
        form_layout.addWidget(change_button)
        form_layout.addWidget(back_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()
        layout.addWidget(form, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
