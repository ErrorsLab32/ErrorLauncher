from PySide6.QtWidgets import QStackedWidget, QWidget


class NavigationController:
    """Small route-to-widget adapter for the main stacked widget."""

    def __init__(self, stack: QStackedWidget) -> None:
        self._stack = stack
        self._views: dict[str, QWidget] = {}

    def add_view(self, route: str, view: QWidget) -> None:
        self._views[route] = view
        self._stack.addWidget(view)

    def show(self, route: str) -> None:
        self._stack.setCurrentWidget(self._views[route])
