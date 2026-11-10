import sys
import html
import subprocess
import psutil
from collections import deque
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QLineEdit, QTextBrowser,
    QVBoxLayout, QHBoxLayout, QFrame,
    QProgressBar, QStackedWidget, QListWidget, QListWidgetItem,
    QCheckBox, QMenu, QSystemTrayIcon, QStyle, QMessageBox,
)

from core.app_info import APP_VERSION, GITHUB_REPOSITORY, resource_path
from core.brain import ask_capri
from core.github_updater import check_for_updates, download_and_install_update
from actions.app_catalog import get_catalog_apps, scan_installed_apps
from memory.database import list_memories
from memory.projects import get_projects
from routines.manager import (
    delete_routine,
    get_application_launch_triggers,
    list_routines,
    run_application_launch_routines,
    run_startup_routines,
    set_routine_enabled,
)
from routines.windows_startup import (
    is_windows_startup_enabled,
    set_windows_startup_enabled,
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


class UpdateWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, mode, update=None):
        super().__init__()
        self.mode = mode
        self.update = update

    def run(self):
        try:
            if self.mode == "check":
                result = check_for_updates()
            else:
                result = download_and_install_update(self.update)
            self.completed.emit(result)
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
        self.update_worker = None
        self.application_launch_triggers = {}
        self._active_trigger_processes = set()
        self._allow_close = False

        self.setup_ui()
        self.refresh_system()
        self.setup_tray_icon()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_system)
        self.timer.start(2000)

        self.application_launch_timer = QTimer(self)
        self.application_launch_timer.timeout.connect(
            self.check_application_launches
        )
        self.application_launch_timer.start(2500)

        self.thinking_timer = QTimer(self)
        self.thinking_timer.timeout.connect(self.animate_thinking_label)
        self.thinking_dots = 0

    def setup_ui(self):
        icon_path = resource_path(Path("assets") / "icons" / "capri.png")
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

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

        logo_path = resource_path(Path("assets") / "images" / "capri-logo.png")
        logo = QLabel("C A P R I")
        logo.setObjectName("Title")
        if logo_path.is_file():
            logo.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    175,
                    60,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            logo.setStyleSheet("color:#F4F7FC;font-size:23px;")

        subtitle = QLabel("PERSONAL AI SYSTEM")
        subtitle.setObjectName("Muted")
        subtitle.setStyleSheet("color:#8593A7;font-size:10px;")

        side_layout.addWidget(logo)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(30)

        self.nav_buttons = []

        for name in [
            "Chat",
            "Mémoire",
            "Projets",
            "Routines",
            "Mises à jour",
        ]:
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

        version = QLabel(f"CAPRI v{APP_VERSION}\nLOCAL SYSTEM")
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
        self.updates_page = self.create_updates_page()
        self.pages.addWidget(self.chat_page)
        self.pages.addWidget(self.memory_page)
        self.pages.addWidget(self.projects_page)
        self.pages.addWidget(self.routines_page)
        self.pages.addWidget(self.updates_page)

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
            "Crée des routines au démarrage de CAPRI ou lorsqu'une "
            "application se lance. Exemple : « Quand CAPRI démarre, ouvre "
            "Spotify et Riot Client » ou « Quand je lance osu, passe la "
            "résolution en natif »."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.windows_startup_checkbox = QCheckBox(
            "Démarrer CAPRI avec Windows (en arrière-plan)"
        )
        self.windows_startup_checkbox.setChecked(
            is_windows_startup_enabled()
        )
        self.windows_startup_checkbox.toggled.connect(
            self.toggle_windows_startup
        )
        layout.addWidget(self.windows_startup_checkbox)

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

    def create_updates_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("Mises à jour")
        title.setObjectName("Title")
        layout.addWidget(title)

        version = QLabel(f"Version installée : CAPRI {APP_VERSION}")
        version.setObjectName("Section")
        layout.addWidget(version)

        description = QLabel(
            "CAPRI vérifie les versions publiées sur GitHub. Les mises à "
            "jour de la version Windows installée sont téléchargées et "
            "vérifiées avant installation."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        self.update_status = QLabel("Aucune vérification effectuée.")
        self.update_status.setWordWrap(True)
        layout.addWidget(self.update_status)

        self.update_button = QPushButton("Vérifier les mises à jour")
        self.update_button.clicked.connect(self.check_for_updates)
        layout.addWidget(self.update_button)

        releases_button = QPushButton("Ouvrir les releases GitHub")
        releases_button.clicked.connect(self.open_releases_page)
        layout.addWidget(releases_button)
        layout.addStretch()
        return page

    def refresh_routines(self):
        if not hasattr(self, "routine_list"):
            return

        if hasattr(self, "windows_startup_checkbox"):
            self.windows_startup_checkbox.blockSignals(True)
            self.windows_startup_checkbox.setChecked(
                is_windows_startup_enabled()
            )
            self.windows_startup_checkbox.blockSignals(False)

        try:
            self.application_launch_triggers = (
                get_application_launch_triggers()
            )
        except Exception as error:
            self.application_launch_triggers = {}
            self.routine_status.setText(
                f"Impossible de surveiller une application : {error}"
            )

        self._active_trigger_processes = (
            self.get_active_trigger_processes()
        )

        self.routine_list.clear()
        apps_by_id = {
            app["app_id"]: app["name"]
            for app in get_catalog_apps()
        }

        for routine in list_routines():
            state = "Activée" if routine["enabled"] else "Désactivée"
            if routine["trigger_type"] == "application_launch":
                trigger_name = apps_by_id.get(
                    routine["trigger_app_id"],
                    "Application indisponible",
                )
                action_name = (
                    "Résolution native"
                    if routine["action_type"] == "native_resolution"
                    else routine["action_type"]
                )
                description = f"Quand {trigger_name} démarre — {action_name}"
            else:
                app_names = [
                    apps_by_id.get(app_id, "Application indisponible")
                    for app_id in routine["app_ids"]
                ]
                description = ", ".join(app_names)
            item = QListWidgetItem(
                f"{routine['name']} — {description} ({state})"
            )
            item.setData(Qt.ItemDataRole.UserRole, routine["id"])
            self.routine_list.addItem(item)

    def create_routine(self):
        text = self.routine_input.text().strip()
        if not text:
            return

        from actions.command_router import (
            create_application_launch_routine_command,
            create_startup_routine_command,
        )

        result = create_application_launch_routine_command(text)
        if result is None:
            result = create_startup_routine_command(text)
        if result is None:
            result = create_startup_routine_command(
                "Au démarrage, ouvre " + text
            )

        self.routine_status.setText(
            result or "Impossible de comprendre cette routine."
        )
        if result and (
            result.startswith("✅")
            or result.startswith("⚠️ Routine ")
        ):
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

    def toggle_windows_startup(self, enabled):
        try:
            set_windows_startup_enabled(enabled)
            state = "activé" if enabled else "désactivé"
            self.routine_status.setText(
                f"Le démarrage automatique de CAPRI avec Windows est {state}."
            )
        except Exception as error:
            self.windows_startup_checkbox.blockSignals(True)
            self.windows_startup_checkbox.setChecked(not enabled)
            self.windows_startup_checkbox.blockSignals(False)
            self.routine_status.setText(
                f"Impossible de configurer le démarrage Windows : {error}"
            )

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("CAPRI — routines actives")
        icon_path = resource_path(Path("assets") / "icons" / "capri.png")
        if icon_path.is_file():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self.tray_icon.setIcon(
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_ComputerIcon
                )
            )

        menu = QMenu(self)
        open_action = QAction("Ouvrir CAPRI", self)
        open_action.triggered.connect(self.restore_from_tray)
        quit_action = QAction("Quitter CAPRI", self)
        quit_action.triggered.connect(self.quit_from_tray)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
        elif "--background" in sys.argv:
            self.chat.append(
                "<p>La zone de notification Windows est indisponible ; "
                "CAPRI reste visible pour éviter de perdre l'accès à la "
                "fenêtre.</p>"
            )

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        self._allow_close = True
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self._allow_close or not self.tray_icon.isVisible():
            event.accept()
            return

        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "CAPRI fonctionne en arrière-plan",
            "Les routines restent actives. Cliquez sur l'icône CAPRI "
            "pour rouvrir la fenêtre.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def check_application_launches(self):
        if not self.application_launch_triggers:
            return

        running = set()
        triggered_app_ids = set()
        try:
            processes = psutil.process_iter(
                ["pid", "name", "create_time"]
            )
            for process in processes:
                try:
                    name = str(
                        process.info.get("name") or ""
                    ).casefold()
                    app_ids = self.application_launch_triggers.get(name)
                    if not app_ids:
                        continue
                    identity = (
                        process.info["pid"],
                        process.info.get("create_time"),
                    )
                    running.add(identity)
                    if identity not in self._active_trigger_processes:
                        triggered_app_ids.update(app_ids)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as error:
            self.chat.append(
                f"<p style='color:#D94B4B'>"
                f"Erreur de surveillance des applications : "
                f"{to_html(error)}</p>"
            )
            return

        self._active_trigger_processes = running
        if not triggered_app_ids:
            return

        try:
            results = run_application_launch_routines(triggered_app_ids)
        except Exception as error:
            self.chat.append(
                f"<p style='color:#D94B4B'>"
                f"Erreur de routine au lancement : {to_html(error)}</p>"
            )
            return

        for result in results:
            if result["status"] == "success":
                message = (
                    f"✅ Routine « {result['name']} » exécutée."
                )
            else:
                message = (
                    f"⚠️ Routine « {result['name']} » : "
                    f"{result['message'] or result['status']}"
                )
            self.chat.append(f"<p>{to_html(message)}</p>")

    def get_active_trigger_processes(self):
        active = set()
        for process in psutil.process_iter(
            ["pid", "name", "create_time"]
        ):
            try:
                name = str(process.info.get("name") or "").casefold()
                if name in self.application_launch_triggers:
                    active.add((
                        process.info["pid"],
                        process.info.get("create_time"),
                    ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return active

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

    def open_releases_page(self, _checked=False):
        QDesktopServices.openUrl(
            QUrl(f"https://github.com/{GITHUB_REPOSITORY}/releases")
        )

    def check_for_updates(self, _checked=False):
        if self.update_worker is not None:
            return

        self.update_status.setText("Vérification de GitHub en cours…")
        self.update_button.setEnabled(False)
        self.update_button.setText("Vérification…")
        self.update_worker = UpdateWorker("check")
        self.update_worker.completed.connect(self.update_check_completed)
        self.update_worker.failed.connect(self.update_check_failed)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_worker.finished.connect(self.clear_update_worker)
        self.update_worker.start()

    def update_check_completed(self, update):
        self.update_button.setEnabled(True)
        self.update_button.setText("Vérifier les mises à jour")

        if update["status"] == "up_to_date":
            self.update_status.setText(
                f"CAPRI {APP_VERSION} est à jour "
                f"(dernière version : {update['latest_version']})."
            )
            return

        self.update_status.setText(
            f"CAPRI {update['latest_version']} est disponible "
            f"(version installée : {APP_VERSION})."
        )
        assets = update.get("assets", {})
        has_windows_package = (
            "CAPRI-windows-x64.zip" in assets
            and "CAPRI-windows-x64.zip.sha256" in assets
        )
        if not getattr(sys, "frozen", False) or not has_windows_package:
            self.update_status.setText(
                self.update_status.text()
                + " Télécharge le paquet Windows depuis GitHub."
            )
            if QMessageBox.question(
                self,
                "Mise à jour de CAPRI",
                "Une nouvelle version est disponible. Ouvrir la page "
                "GitHub pour la télécharger ?",
            ) == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(update["release_url"]))
            return

        if QMessageBox.question(
            self,
            "Mise à jour de CAPRI",
            f"Télécharger CAPRI {update['latest_version']} et "
            "redémarrer l'application ?",
        ) == QMessageBox.StandardButton.Yes:
            self.start_update_install(update)

    def update_check_failed(self, error):
        self.update_button.setEnabled(True)
        self.update_button.setText("Vérifier les mises à jour")
        self.update_status.setText(
            f"Impossible de vérifier les mises à jour : {error}"
        )

    def start_update_install(self, update):
        self.update_button.setEnabled(False)
        self.update_button.setText("Téléchargement…")
        self.update_status.setText(
            f"Téléchargement sécurisé de CAPRI {update['latest_version']}…"
        )
        self.update_worker = UpdateWorker("install", update)
        self.update_worker.completed.connect(self.update_install_completed)
        self.update_worker.failed.connect(self.update_install_failed)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_worker.finished.connect(self.clear_update_worker)
        self.update_worker.start()

    def update_install_completed(self, result):
        self.update_button.setText("Fermeture de CAPRI…")
        self.update_status.setText(
            f"CAPRI {result['version']} est téléchargée. "
            "L'application va se fermer pour terminer la mise à jour."
        )
        self.tray_icon.hide()
        QTimer.singleShot(500, QApplication.quit)

    def update_install_failed(self, error):
        self.update_button.setEnabled(True)
        self.update_button.setText("Vérifier les mises à jour")
        self.update_status.setText(f"Mise à jour annulée : {error}")

    def clear_update_worker(self):
        self.update_worker = None

    def show_page(self, name):
        page_indexes = {
            "Chat": 0,
            "Mémoire": 1,
            "Projets": 2,
            "Routines": 3,
            "Mises à jour": 4,
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


def launch(background=False):

    scan_installed_apps()
    if background:
        sys.argv = [
            argument for argument in sys.argv
            if argument != "--background"
        ]
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    window = CapriWindow()
    if background and QSystemTrayIcon.isSystemTrayAvailable():
        window.hide()
    else:
        window.show()
    QTimer.singleShot(800, window.start_enabled_routines)

    sys.exit(app.exec())


if __name__ == "__main__":
    launch()