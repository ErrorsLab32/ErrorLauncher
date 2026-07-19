from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RegisterView(QWidget):
    registration_requested = Signal()
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")

        title = QLabel("Создание аккаунта")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Заполните данные для регистрации")
        subtitle.setObjectName("mutedLabel")

        fields = [
            ("Логин", QLineEdit.EchoMode.Normal),
            ("Пароль", QLineEdit.EchoMode.Password),
            ("Повторите пароль", QLineEdit.EchoMode.Password),
            ("Код приглашения", QLineEdit.EchoMode.Normal),
        ]

        form = QFrame()
        form.setObjectName("authForm")
        form.setMinimumWidth(350)
        form.setMaximumWidth(410)
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)
        form_layout.addWidget(title)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(20)

        for placeholder, echo_mode in fields:
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setEchoMode(echo_mode)
            form_layout.addWidget(field)

        register_button = QPushButton("Зарегистрироваться")
        register_button.setObjectName("primaryButton")
        register_button.clicked.connect(self.registration_requested)
        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.back_requested)
        form_layout.addSpacing(4)
        form_layout.addWidget(register_button)
        form_layout.addWidget(back_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch()
        layout.addWidget(form, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
