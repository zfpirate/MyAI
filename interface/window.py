import sys
import html
import subprocess
import psutil
from collections import deque

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QFrame,
    QProgressBar, QStackedWidget, QListWidget, QListWidgetItem
)

from core.brain import ask_capri
from actions.app_catalog import get_catalog_apps, scan_installed_apps
from memory.database import list_memories
from memory.projects import get_projects
from routines.manager import (
    delete_routine,
    list_routines,
    run_startup_routines,
    set_routine_enabled,
)


STYLE = """
QMainWindow {
    background-color: #F5F7FB;
}

QWidget {
    color: #202B3C;
    font-family: 'Segoe UI';
    font-size: 13px;
    background-color: transparent;
}

QWidget#Central {
    background-color: #F5F7FB;
}

QFrame#Sidebar {
    background-color: #111827;
    border-right: 1px solid #263244;
}

QFrame#Panel {
    background-color: #FFFFFF;
    border: 1px solid #E5EAF2;
    border-radius: 18px;
}

QLabel#Title {
    font-size: 25px;
    font-weight: bold;
    color: #17243A;
}

QLabel#Section {
    font-size: 16px;
    font-weight: bold;
    color: #243650;
}

QLabel#Muted {
    color: #718198;
    font-size: 11px;
}

QPushButton {
    background-color: #F0F4FA;
    color: #31445F;
    border: none;
    border-radius: 10px;
    padding: 12px;
    text-align: left;
}

QPushButton:hover {
    background-color: #E4ECF7;
}

QPushButton#NavItem {
    background-color: transparent;
    color: #AEB9C9;
    padding: 13px 15px;
    font-weight: 600;
}

QPushButton#NavItem:hover {
    background-color: #202B3B;
    color: #FFFFFF;
}

QPushButton#NavItem:checked {
    background-color: #293A55;
    color: #FFFFFF;
    border-left: 3px solid #68A7FF;
}

QPushButton#Send {
    background-color: #3978E5;
    color: white;
    font-weight: bold;
    padding: 13px 22px;
}

QPushButton#Send:hover {
    background-color: #2867D4;
}

QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #DCE3ED;
    border-radius: 12px;
    padding: 14px;
    color: #202B3C;
}

QLineEdit:focus {
    border: 1px solid #6B9AF0;
}

QTextBrowser, QListWidget {
    background-color: #FFFFFF;
    border: none;
    color: #202B3C;
    padding: 12px;
}

QFrame#ThinkingPanel {
    background-color: #F3F7FF;
    border: 1px solid #E3ECFC;
    border-radius: 12px;
}

QLabel#ThinkingText {
    color: #42669E;
    font-size: 12px;
    font-weight: 600;
}

QProgressBar#ThinkingProgress {
    background-color: #E4ECF8;
    border: none;
    border-radius: 2px;
    max-height: 4px;
}

QProgressBar#ThinkingProgress::chunk {
    background-color: #5B8DEF;
    border-radius: 2px;
}

QProgressBar {
    background-color: #E8EDF4;
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #6293E8;
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


class StartupRoutineWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.completed.emit(run_startup_routines())
        except Exception as error:
            self.failed.emit(str(error))


class CapriWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CAPRI | Personal AI")
        self.resize(1450, 900)
        self.setMinimumSize(1100, 700)

        self.worker = None
        self.pending_messages = deque()
        self.startup_worker = None

        self.setup_ui()
        self.refresh_system()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_system)
        self.timer.start(2000)

        self.thinking_timer = QTimer(self)
        self.thinking_timer.timeout.connect(self.animate_thinking_label)
        self.thinking_dots = 0

    def setup_ui(self):

        central = QWidget()
        central.setObjectName("Central")
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
        logo.setStyleSheet("color:#F4F7FC;font-size:23px;")

        subtitle = QLabel("PERSONAL AI SYSTEM")
        subtitle.setObjectName("Muted")
        subtitle.setStyleSheet("color:#8593A7;font-size:10px;")

        side_layout.addWidget(logo)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(30)

        self.nav_buttons = []

        for name in ["Chat", "Mémoire", "Projets", "Routines"]:
            button = QPushButton(name)
            button.setObjectName("NavItem")
            button.setCheckable(True)
            button.setChecked(name == "Chat")
            button.clicked.connect(
                lambda checked=False, n=name: self.show_page(n)
            )
            side_layout.addWidget(button)
            self.nav_buttons.append(button)

        side_layout.addStretch()

        version = QLabel("CAPRI v0.2\nLOCAL SYSTEM")
        version.setObjectName("Muted")
        version.setStyleSheet("color:#AEB9C9;")
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
        self.routines_page = self.create_routines_page()
        self.pages.addWidget(self.chat_page)
        self.pages.addWidget(self.memory_page)
        self.pages.addWidget(self.projects_page)
        self.pages.addWidget(self.routines_page)

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
        chat_layout.setContentsMargins(20, 20, 20, 18)
        chat_layout.setSpacing(14)

        title_row = QHBoxLayout()
        chat_title = QLabel("Conversation")
        chat_title.setObjectName("Section")

        chat_subtitle = QLabel("Ton assistante personnelle")
        chat_subtitle.setObjectName("Muted")
        title_column = QVBoxLayout()
        title_column.setSpacing(3)
        title_column.addWidget(chat_title)
        title_column.addWidget(chat_subtitle)
        title_row.addLayout(title_column)
        title_row.addStretch()
        self.chat_badge = QLabel("● PRÊTE")
        self.chat_badge.setStyleSheet(
            "color:#18866B;background:#EAF7F2;border-radius:9px;"
            "padding:6px 10px;font-size:10px;font-weight:bold;"
        )
        title_row.addWidget(self.chat_badge)

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)
        self.chat.setFrameShape(QFrame.Shape.NoFrame)
        self.chat.document().setDocumentMargin(12)

        self.chat.append(
            "<div style='padding:14px 18px;background:#F3F7FF;"
            "border-radius:14px;color:#31445F'>"
            "<b style='color:#3978E5;font-size:16px'>Bonjour !</b><br>"
            "CAPRI est prête. Que souhaites-tu faire ?"
            "</div>"
        )

        self.thinking_panel = QFrame()
        self.thinking_panel.setObjectName("ThinkingPanel")
        thinking_layout = QVBoxLayout(self.thinking_panel)
        thinking_layout.setContentsMargins(12, 8, 12, 8)
        thinking_layout.setSpacing(6)
        self.thinking_label = QLabel("CAPRI réfléchit")
        self.thinking_label.setObjectName("ThinkingText")
        self.thinking_progress = QProgressBar()
        self.thinking_progress.setObjectName("ThinkingProgress")
        self.thinking_progress.setRange(0, 0)
        self.thinking_progress.setTextVisible(False)
        thinking_layout.addWidget(self.thinking_label)
        thinking_layout.addWidget(self.thinking_progress)
        self.thinking_panel.hide()

        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

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

        title_container = QWidget()
        title_container.setLayout(title_row)
        chat_layout.addWidget(title_container)
        chat_layout.addWidget(self.chat, 1)
        chat_layout.addWidget(self.thinking_panel)
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

    def create_routines_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("Routines")
        title.setObjectName("Title")
        layout.addWidget(title)

        description = QLabel(
            "Crée des actions qui se déclenchent au démarrage de CAPRI. "
            "Exemple : « Quand CAPRI démarre, ouvre Spotify et Riot Client »."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        input_layout = QHBoxLayout()
        self.routine_input = QLineEdit()
        self.routine_input.setPlaceholderText(
            "Spotify et Riot Client"
        )
        self.routine_input.returnPressed.connect(self.create_routine)
        create_button = QPushButton("Créer la routine")
        create_button.clicked.connect(self.create_routine)
        input_layout.addWidget(self.routine_input, 1)
        input_layout.addWidget(create_button)
        layout.addLayout(input_layout)

        self.routine_status = QLabel("")
        self.routine_status.setWordWrap(True)
        layout.addWidget(self.routine_status)

        self.routine_list = QListWidget()
        layout.addWidget(self.routine_list, 1)

        action_layout = QHBoxLayout()
        self.routine_toggle_button = QPushButton("Activer / désactiver")
        self.routine_toggle_button.clicked.connect(
            self.toggle_selected_routine
        )
        delete_button = QPushButton("Supprimer")
        delete_button.clicked.connect(self.delete_selected_routine)
        action_layout.addWidget(self.routine_toggle_button)
        action_layout.addWidget(delete_button)
        layout.addLayout(action_layout)

        self.refresh_routines()
        return page

    def refresh_routines(self):
        if not hasattr(self, "routine_list"):
            return

        self.routine_list.clear()
        apps_by_id = {
            app["app_id"]: app["name"]
            for app in get_catalog_apps()
        }

        for routine in list_routines():
            app_names = [
                apps_by_id.get(app_id, "Application indisponible")
                for app_id in routine["app_ids"]
            ]
            state = "Activée" if routine["enabled"] else "Désactivée"
            item = QListWidgetItem(
                f"{routine['name']} — {', '.join(app_names)} ({state})"
            )
            item.setData(Qt.ItemDataRole.UserRole, routine["id"])
            self.routine_list.addItem(item)

    def create_routine(self):
        text = self.routine_input.text().strip()
        if not text:
            return

        from actions.command_router import create_startup_routine_command

        result = create_startup_routine_command(text)
        if result is None:
            result = create_startup_routine_command(
                "Au démarrage, ouvre " + text
            )

        self.routine_status.setText(
            result or "Impossible de comprendre cette routine."
        )
        if result and result.startswith("✅"):
            self.routine_input.clear()
            self.refresh_routines()

    def selected_routine(self):
        item = self.routine_list.currentItem()
        if item is None:
            self.routine_status.setText("Sélectionne d'abord une routine.")
            return None

        routine_id = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (
                routine for routine in list_routines()
                if routine["id"] == routine_id
            ),
            None,
        )

    def toggle_selected_routine(self):
        routine = self.selected_routine()
        if routine is None:
            return

        set_routine_enabled(routine["id"], not routine["enabled"])
        self.refresh_routines()
        self.routine_status.setText("État de la routine mis à jour.")

    def delete_selected_routine(self):
        routine = self.selected_routine()
        if routine is None:
            return

        delete_routine(routine["id"])
        self.refresh_routines()
        self.routine_status.setText("Routine supprimée.")

    def start_enabled_routines(self):
        if self.startup_worker is not None:
            return

        self.startup_worker = StartupRoutineWorker()
        self.startup_worker.completed.connect(
            self.show_startup_routine_results
        )
        self.startup_worker.failed.connect(
            self.show_startup_routine_error
        )
        self.startup_worker.finished.connect(
            self.startup_worker.deleteLater
        )
        self.startup_worker.finished.connect(
            self.clear_startup_worker
        )
        self.startup_worker.start()

    def show_startup_routine_results(self, results):
        apps_by_id = {
            app["app_id"]: app["name"]
            for app in get_catalog_apps()
        }
        for routine in results:
            for application in routine["applications"]:
                app_name = apps_by_id.get(
                    application["app_id"],
                    application["app_id"],
                )
                if application["status"] == "launched_not_tracked":
                    message = (
                        f"⚠️ Routine « {routine['name']} » : {app_name} "
                        "a été lancée, mais sa fenêtre n'a pas été vérifiée."
                    )
                elif application["status"] not in {
                    "launched_and_tracked",
                    "reused_and_tracked",
                    "opened",
                }:
                    message = (
                        f"⚠️ Routine « {routine['name']} » : "
                        f"{app_name} — {application['message']}"
                    )
                else:
                    message = (
                        f"✅ Routine « {routine['name']} » : "
                        f"{app_name} ouvert."
                    )
                self.chat.append(
                    f"<p>{to_html(message)}</p>"
                )

    def show_startup_routine_error(self, error):
        self.chat.append(
            f"<p style='color:#D94B4B'>"
            f"Erreur de routine au démarrage : {to_html(error)}</p>"
        )

    def clear_startup_worker(self):
        self.startup_worker = None

    def show_page(self, name):
        page_indexes = {
            "Chat": 0,
            "Mémoire": 1,
            "Projets": 2,
            "Routines": 3,
        }
        if name not in page_indexes:
            return

        self.pages.setCurrentIndex(page_indexes[name])
        for button in self.nav_buttons:
            button.setChecked(button.text() == name)

        if name == "Mémoire":
            self.refresh_memories()

        elif name == "Projets":
            self.refresh_projects()

        elif name == "Routines":
            self.refresh_routines()

    def set_thinking(self, active, queued=0):
        if active:
            suffix = (
                f" · {queued} message(s) en attente"
                if queued
                else ""
            )
            self.thinking_label.setText(
                f"CAPRI réfléchit{'.' * self.thinking_dots}{suffix}"
            )
            self.thinking_panel.show()
            self.chat_badge.setText("● EN COURS")
            self.chat_badge.setStyleSheet(
                "color:#396CC1;background:#EDF3FF;border-radius:9px;"
                "padding:6px 10px;font-size:10px;font-weight:bold;"
            )
            self.status.setText("● CAPRI RÉFLÉCHIT")
            self.status.setStyleSheet(
                "color:#396CC1;font-weight:bold;"
            )
            if not self.thinking_timer.isActive():
                self.thinking_timer.start(450)
        else:
            self.thinking_panel.hide()
            self.chat_badge.setText("● PRÊTE")
            self.chat_badge.setStyleSheet(
                "color:#18866B;background:#EAF7F2;border-radius:9px;"
                "padding:6px 10px;font-size:10px;font-weight:bold;"
            )
            self.status.setText("● CAPRI ONLINE")
            self.status.setStyleSheet(
                "color:#18866B;font-weight:bold;"
            )
            self.thinking_timer.stop()
            self.thinking_dots = 0

    def animate_thinking_label(self):
        self.thinking_dots = (self.thinking_dots + 1) % 4
        self.set_thinking(True, len(self.pending_messages))

    def send_message(self):

        message = self.message_input.text().strip()

        if not message:
            return

        self.chat.append(
            f"<p style='color:#267BC1'><b>VOUS :</b> "
            f"{to_html(message)}</p>"
        )

        self.message_input.clear()
        self.pending_messages.append(message)

        if self.worker is not None:
            self.set_thinking(True, len(self.pending_messages))
            return

        self.start_next_message()

    def start_next_message(self):
        if self.worker is not None or not self.pending_messages:
            return

        message = self.pending_messages.popleft()
        self.set_thinking(True, len(self.pending_messages))
        self.worker = AIWorker(message)
        self.worker.finished_response.connect(
            self.display_response
        )
        self.worker.failed.connect(self.display_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self):
        # Le worker terminé est remplacé seulement après la fin de son thread.
        self.worker = None

        if self.pending_messages:
            self.start_next_message()
            return

        self.set_thinking(False)

    def display_response(self, answer):

        self.chat.append(
            f"<p style='color:#193451'><b>CAPRI :</b> "
            f"{to_html(answer)}</p>"
        )

    def display_error(self, error):

        self.chat.append(
            f"<p style='color:#D94B4B'>Erreur : "
            f"{to_html(error)}</p>"
        )

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

    scan_installed_apps()
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    window = CapriWindow()
    window.show()
    QTimer.singleShot(800, window.start_enabled_routines)

    sys.exit(app.exec())


if __name__ == "__main__":
    launch()