
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt, QTimer

from security.confirmation import resolve_confirmation_request


class ConfirmationDialog(QDialog):

    def __init__(self, request, parent=None):
        super().__init__(parent)

        self.request = request
        self.approved = False
        self.resolved = False

        self.setWindowTitle("CAPRI - Autorisation")
        self.setFixedSize(460, 290)
        self.setModal(True)

        self.setStyleSheet("""
            QDialog {
                background-color: #f4f8ff;
                color: #142b4a;
            }

            QLabel#title {
                font-size: 21px;
                font-weight: bold;
                color: #1769aa;
            }

            QLabel#details {
                font-size: 14px;
                color: #344b68;
                background-color: white;
                border: 1px solid #d5e3f5;
                border-radius: 8px;
                padding: 12px;
            }

            QPushButton {
                padding: 11px;
                border-radius: 7px;
                font-weight: bold;
            }

            QPushButton#approve {
                background-color: #1769d2;
                color: white;
            }

            QPushButton#approve:hover {
                background-color: #0e55b5;
            }

            QPushButton#deny {
                background-color: #e34b59;
                color: white;
            }

            QPushButton#deny:hover {
                background-color: #c83240;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("🔐 CAPRI demande une autorisation")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "Une action nécessite ton accord avant de continuer."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)

        permission = QLabel(
            f"Permission : {request['permission_id']}"
        )

        details = QLabel(
            f"Action demandée :\n{request['details']}"
        )
        details.setObjectName("details")
        details.setWordWrap(True)

        self.timer_label = QLabel("Expiration dans 02:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QHBoxLayout()

        approve_button = QPushButton("Autoriser")
        approve_button.setObjectName("approve")
        approve_button.clicked.connect(self.approve)

        deny_button = QPushButton("Refuser")
        deny_button.setObjectName("deny")
        deny_button.clicked.connect(self.deny)

        buttons.addWidget(deny_button)
        buttons.addWidget(approve_button)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(permission)
        layout.addWidget(details)
        layout.addWidget(self.timer_label)
        layout.addLayout(buttons)

        self.remaining_seconds = 120

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def update_countdown(self):
        self.remaining_seconds -= 1

        if self.remaining_seconds <= 0:
            self.deny()
            return

        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60

        self.timer_label.setText(
            f"Expiration dans {minutes:02d}:{seconds:02d}"
        )

    def approve(self):
        if self.resolved:
            return

        success = resolve_confirmation_request(
            self.request["id"],
            True,
        )

        self.resolved = True
        self.approved = success

        self.timer.stop()
        self.accept()

    def deny(self):
        if self.resolved:
            return

        resolve_confirmation_request(
            self.request["id"],
            False,
        )

        self.resolved = True
        self.approved = False

        self.timer.stop()
        self.reject()

    def closeEvent(self, event):
        if not self.resolved:
            self.deny()

        event.accept()
