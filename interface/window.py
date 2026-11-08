import sys
import html
import subprocess
import psutil

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QFrame,
    QProgressBar, QStackedWidget, QListWidget
)

from core.brain import ask_capri
from memory.database import list_memories
from memory.projects import get_projects


STYLE = """
QMainWindow, QWidget {
    background-color: #F3F7FC;
    color: #193451;
    font-family: 'Segoe UI';
    font-size: 13px;
}

QFrame#Sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #DCE7F2;
}

QFrame#Panel {
    background-color: #FFFFFF;
    border: 1px solid #DCE7F2;
    border-radius: 14px;
}

QLabel#Title {
    font-size: 23px;
    font-weight: bold;
    color: #173C63;
}

QLabel#Section {
    font-size: 15px;
    font-weight: bold;
    color: #244E77;
}

QLabel#Muted {
    color: #8297AB;
    font-size: 11px;
}

QPushButton {
    background-color: #EAF3FC;
    color: #275B89;
    border: none;
    border-radius: 9px;
    padding: 11px;
    text-align: left;
}

QPushButton:hover {
    background-color: #D9EAFB;
}

QPushButton#Send {
    background-color: #267BC1;
    color: white;
    font-weight: bold;
    padding: 12px 20px;
}

QPushButton#Send:hover {
    background-color: #1768AC;
}

QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #D3E2F0;
    border-radius: 10px;
    padding: 13px;
    color: #193451;
}

QTextBrowser, QListWidget {
    background-color: #FFFFFF;
    border: none;
    color: #193451;
    padding: 8px;
}

QProgressBar {
    background-color: #E8F0F8;
    border: none;
    border-radius: 5px;
    height: 9px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #3695DC;
    border-radius: 5px;
}
"""


def to_html(text):
    """Échappe le texte et convertit les retours à la ligne."""
    return html.escape(str(text)).replace("\n", "<br>")


class AIWorker(QThread):
    finished_response = Signal(str)
    failed = Signal(str)

    def __init__(self, message):
        super().__init__()
        self.message = message

    def run(self):
        try:
            answer = ask_capri(self.message)
            self.finished_response.emit(answer)
        except Exception as error:
            self.failed.emit(str(error))


class CapriWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CAPRI | Personal AI")
        self.resize(1450, 900)
        self.setMinimumSize(1100, 700)

        self.worker = None

        self.setup_ui()
        self.refresh_system()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_system)
        self.timer.start(2000)

    def setup_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # SIDEBAR
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(215)

        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 25, 18, 20)
        side_layout.setSpacing(14)

        logo = QLabel("C A P R I")
        logo.setObjectName("Title")

        subtitle = QLabel("PERSONAL AI SYSTEM")
        subtitle.setObjectName("Muted")

        side_layout.addWidget(logo)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(30)

        self.nav_buttons = []

        for name in ["Chat", "Mémoire", "Projets"]:
            button = QPushButton(name)
            button.clicked.connect(
                lambda checked=False, n=name: self.show_page(n)
            )
            side_layout.addWidget(button)
            self.nav_buttons.append(button)

        side_layout.addStretch()

        version = QLabel("CAPRI v0.2\nLOCAL SYSTEM")
        version.setObjectName("Muted")
        side_layout.addWidget(version)

        # CONTENT
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(25, 20, 25, 20)
        content_layout.setSpacing(18)

        # HEADER
        header = QHBoxLayout()

        title = QLabel("Command Center")
        title.setObjectName("Title")

        self.status = QLabel("● CAPRI ONLINE")
        self.status.setStyleSheet(
            "color: #219A70; font-weight: bold;"
        )

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status)

        content_layout.addLayout(header)

        # PAGES
        self.pages = QStackedWidget()

        self.chat_page = self.create_chat_page()
        self.memory_page = self.create_list_page("memory_list")
        self.projects_page = self.create_list_page("project_list")
        self.pages.addWidget(self.chat_page)
        self.pages.addWidget(self.memory_page)
        self.pages.addWidget(self.projects_page)

        content_layout.addWidget(self.pages)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content, 1)

    def create_chat_page(self):

        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(16)

        # CHAT PANEL
        chat_panel = QFrame()
        chat_panel.setObjectName("Panel")

        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(18, 18, 18, 18)

        chat_title = QLabel("Conversation avec CAPRI")
        chat_title.setObjectName("Section")

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)

        self.chat.append(
            "<h2 style='color:#267BC1'>Bonjour !</h2>"
            "<p>CAPRI est opérationnel. "
            "Comment puis-je vous aider ?</p>"
        )

        input_layout = QHBoxLayout()

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(
            "Écris un message à CAPRI..."
        )
        self.message_input.returnPressed.connect(
            self.send_message
        )

        self.send_button = QPushButton("Envoyer")
        self.send_button.setObjectName("Send")
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.message_input, 1)
        input_layout.addWidget(self.send_button)

        chat_layout.addWidget(chat_title)
        chat_layout.addWidget(self.chat, 1)
        chat_layout.addLayout(input_layout)

        # SYSTEM PANEL
        system_panel = QFrame()
        system_panel.setObjectName("Panel")
        system_panel.setFixedWidth(245)

        system_layout = QVBoxLayout(system_panel)
        system_layout.setContentsMargins(16, 18, 16, 18)
        system_layout.setSpacing(12)

        system_title = QLabel("SYSTEM MONITOR")
        system_title.setObjectName("Section")
        system_layout.addWidget(system_title)

        self.cpu_label = QLabel("CPU : 0 %")
        self.cpu_bar = QProgressBar()

        self.ram_label = QLabel("RAM : 0 %")
        self.ram_bar = QProgressBar()

        self.gpu_label = QLabel("GPU : Non détecté")
        self.gpu_temp = QLabel("Température : --")

        for widget in [
            self.cpu_label, self.cpu_bar,
            self.ram_label, self.ram_bar,
            self.gpu_label, self.gpu_temp
        ]:
            system_layout.addWidget(widget)

        system_layout.addStretch()

        model = QLabel("ACTIVE MODEL")
        model.setObjectName("Section")

        model_name = QLabel("Qwen3 8B")
        model_name.setStyleSheet(
            "color:#267BC1;font-weight:bold;"
        )

        system_layout.addWidget(model)
        system_layout.addWidget(model_name)

        layout.addWidget(chat_panel, 1)
        layout.addWidget(system_panel)

        return page

    def create_list_page(self, attribute):

        page = QWidget()
        layout = QVBoxLayout(page)

        panel = QFrame()
        panel.setObjectName("Panel")

        panel_layout = QVBoxLayout(panel)

        widget = QListWidget()
        setattr(self, attribute, widget)

        panel_layout.addWidget(widget)
        layout.addWidget(panel)

        return page

    def show_page(self, name):

        if name == "Chat":
            self.pages.setCurrentIndex(0)

        elif name == "Mémoire":
            self.pages.setCurrentIndex(1)
            self.refresh_memories()

        elif name == "Projets":
            self.pages.setCurrentIndex(2)
            self.refresh_projects()

    def send_message(self):

        message = self.message_input.text().strip()

        if not message:
            return

        if self.worker is not None and self.worker.isRunning():
            return

        self.chat.append(
            f"<p style='color:#267BC1'><b>VOUS :</b> "
            f"{to_html(message)}</p>"
        )

        self.message_input.clear()
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.status.setText("● CAPRI RÉFLÉCHIT")

        self.worker = AIWorker(message)
        self.worker.finished_response.connect(
            self.display_response
        )
        self.worker.failed.connect(self.display_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self):
        # Évite de garder une référence vers un objet déjà détruit
        self.worker = None

    def display_response(self, answer):

        self.chat.append(
            f"<p style='color:#193451'><b>CAPRI :</b> "
            f"{to_html(answer)}</p>"
        )

        self.finish_request()

    def display_error(self, error):

        self.chat.append(
            f"<p style='color:#D94B4B'>Erreur : "
            f"{to_html(error)}</p>"
        )

        self.finish_request()

    def finish_request(self):

        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.status.setText("● CAPRI ONLINE")
        self.message_input.setFocus()

    def refresh_system(self):

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent

        self.cpu_label.setText(f"CPU : {cpu:.1f} %")
        self.cpu_bar.setValue(int(cpu))

        self.ram_label.setText(f"RAM : {ram:.1f} %")
        self.ram_bar.setValue(int(ram))

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                # Première GPU uniquement (si plusieurs lignes)
                first_line = result.stdout.strip().splitlines()[0]
                values = first_line.split(",")
                self.gpu_label.setText(
                    f"GPU : {values[0].strip()} %"
                )
                self.gpu_temp.setText(
                    f"Température : {values[1].strip()} °C"
                )
            else:
                self.gpu_label.setText("GPU : Indisponible")

        except Exception:
            self.gpu_label.setText("GPU : Indisponible")

    def refresh_memories(self):

        self.memory_list.clear()

        for memory in list_memories():
            self.memory_list.addItem(
                f"[{memory['id']}] {memory['content']}"
            )

    def refresh_projects(self):

        self.project_list.clear()

        for project in get_projects():
            self.project_list.addItem(
                f"{project['name']} — {project['description']}"
            )


def launch():

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    window = CapriWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    launch()