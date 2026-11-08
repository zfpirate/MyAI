import sys

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QLineEdit,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QGridLayout,
)


STYLE = """
QMainWindow, QWidget {
    background-color: #F4F7FC;
    color: #172B4D;
    font-family: Segoe UI;
    font-size: 14px;
}

QFrame#Sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #DFE7F2;
}

QLabel#Logo {
    color: #1677D2;
    font-size: 25px;
    font-weight: bold;
}

QLabel#Title {
    font-size: 26px;
    font-weight: bold;
    color: #17365D;
}

QLabel#Subtitle {
    color: #71839D;
    font-size: 13px;
}

QFrame#Panel {
    background-color: #FFFFFF;
    border: 1px solid #E1E9F3;
    border-radius: 12px;
}

QPushButton {
    background-color: transparent;
    color: #405675;
    border: none;
    border-radius: 8px;
    padding: 12px;
    text-align: left;
}

QPushButton:hover {
    background-color: #EAF3FF;
    color: #1677D2;
}

QPushButton#Active {
    background-color: #E5F1FF;
    color: #1677D2;
    font-weight: bold;
}

QPushButton#Primary {
    background-color: #1677D2;
    color: white;
    font-weight: bold;
    text-align: center;
}

QPushButton#Primary:hover {
    background-color: #0863B7;
}

QPushButton:disabled {
    background-color: #A9C6E3;
    color: white;
}

QLineEdit {
    background-color: #F7F9FC;
    border: 1px solid #DCE5F0;
    border-radius: 8px;
    padding: 11px;
}

QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E1E9F3;
    border-radius: 10px;
    padding: 8px;
    outline: none;
}

QCheckBox {
    spacing: 10px;
    padding: 8px;
}
"""


class ChatWorker(QThread):
    """Exécute la réponse de CAPRI sans bloquer l'interface graphique."""

    answer_ready = Signal(str)

    def __init__(self, message):
        super().__init__()
        self.message = message

    def run(self):
        try:
            # On réutilise le moteur CAPRI déjà présent dans core/brain.py.
            from core.brain import ask_capri

            answer = ask_capri(self.message)
            self.answer_ready.emit(str(answer))
        except Exception as error:
            self.answer_ready.emit(f"Erreur : {error}")


class CapriWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CAPRI - Assistant personnel")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 700)

        self.pages = QStackedWidget()
        self.nav_buttons = []
        self.chat_worker = None

        self.build_interface()

    def build_interface(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # MENU LATÉRAL
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(245)

        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 25, 18, 20)
        side_layout.setSpacing(12)

        logo = QLabel("◈ CAPRI")
        logo.setObjectName("Logo")
        side_layout.addWidget(logo)

        subtitle = QLabel("PERSONAL AI SYSTEM")
        subtitle.setObjectName("Subtitle")
        side_layout.addWidget(subtitle)

        side_layout.addSpacing(25)

        menu = [
            ("⌂   Tableau de bord", 0),
            ("☑   Gestionnaire de tâches", 1),
            ("⬡   Permissions", 2),
            ("▣   Applications Windows", 3),
            ("◉   Assistant CAPRI", 4),
        ]

        for label, index in menu:
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, i=index: self.change_page(i)
            )
            self.nav_buttons.append(button)
            side_layout.addWidget(button)

        side_layout.addStretch()

        system_label = QLabel("SYSTÈME")
        system_label.setObjectName("Subtitle")
        side_layout.addWidget(system_label)

        side_layout.addWidget(QLabel("●  IA locale"))
        side_layout.addWidget(QLabel("●  Mémoire SQLite"))

        # CONTENU PRINCIPAL
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(35, 28, 35, 25)

        self.pages.addWidget(self.create_dashboard())
        self.pages.addWidget(self.create_tasks_page())
        self.pages.addWidget(self.create_permissions_page())
        self.pages.addWidget(self.create_apps_page())
        self.pages.addWidget(self.create_chat_page())

        content_layout.addWidget(self.pages)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(content, 1)

        self.setCentralWidget(central)
        self.change_page(0)

    def make_panel(self, title, description):
        panel = QFrame()
        panel.setObjectName("Panel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet(
            "font-size: 17px; font-weight: bold; color: #17365D;"
        )

        detail = QLabel(description)
        detail.setObjectName("Subtitle")
        detail.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(detail)

        return panel, layout

    def create_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)

        title = QLabel("Tableau de bord")
        title.setObjectName("Title")

        subtitle = QLabel(
            "Bienvenue dans votre centre de contrôle CAPRI."
        )
        subtitle.setObjectName("Subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(16)

        cards = [
            ("Gestionnaire de tâches", "Organiser et suivre tes tâches."),
            ("Permissions", "Gérer les autorisations de CAPRI."),
            ("Applications Windows", "Contrôler les applications."),
            ("Assistant IA", "Discuter avec ton assistant local."),
        ]

        for i, (name, description) in enumerate(cards):
            panel, panel_layout = self.make_panel(name, description)
            panel_layout.addStretch()
            grid.addWidget(panel, i // 2, i % 2)

        layout.addLayout(grid)

        activity, activity_layout = self.make_panel(
            "Activité du système",
            "État actuel des différents modules."
        )

        for status in [
            "✓  Moteur IA : prêt",
            "✓  Mémoire permanente : prête",
            "○  Gestionnaire de tâches : interface en construction",
            "○  Contrôle Windows : non connecté",
        ]:
            activity_layout.addWidget(QLabel(status))

        layout.addWidget(activity)
        layout.addStretch()

        return page

    def create_tasks_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Gestionnaire de tâches")
        title.setObjectName("Title")
        layout.addWidget(title)

        description = QLabel(
            "Ajoute et organise les tâches de CAPRI."
        )
        description.setObjectName("Subtitle")
        layout.addWidget(description)

        input_layout = QHBoxLayout()

        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Nouvelle tâche...")

        add_button = QPushButton("Ajouter")
        add_button.setObjectName("Primary")
        add_button.clicked.connect(self.add_task)
        self.task_input.returnPressed.connect(self.add_task)

        input_layout.addWidget(self.task_input, 1)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        self.task_list = QListWidget()
        layout.addWidget(self.task_list)

        return page

    def add_task(self):
        text = self.task_input.text().strip()

        if not text:
            return

        item = QListWidgetItem()
        checkbox = QCheckBox(text)

        self.task_list.addItem(item)
        self.task_list.setItemWidget(item, checkbox)

        self.task_input.clear()

    def create_permissions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Permissions")
        title.setObjectName("Title")
        layout.addWidget(title)

        description = QLabel(
            "Configuration des autorisations de CAPRI. "
            "Ces options sont visuelles pour le moment."
        )
        description.setObjectName("Subtitle")
        layout.addWidget(description)

        permissions = [
            "Autoriser l'ouverture des applications",
            "Autoriser la fermeture des applications",
            "Autoriser la lecture des informations système",
            "Demander confirmation avant toute suppression",
            "Demander confirmation avant toute action sensible",
        ]

        panel, panel_layout = self.make_panel(
            "Autorisations",
            "Les permissions réelles seront gérées par le moteur de sécurité."
        )

        for permission in permissions:
            panel_layout.addWidget(QCheckBox(permission))

        layout.addWidget(panel)
        layout.addStretch()

        return page

    def create_apps_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("Applications Windows")
        title.setObjectName("Title")
        layout.addWidget(title)

        description = QLabel(
            "Les contrôles réels seront ajoutés après la mise en place "
            "du système de permissions."
        )
        description.setObjectName("Subtitle")
        layout.addWidget(description)

        for name in [
            "Calculatrice",
            "Bloc-notes",
            "Explorateur de fichiers"
        ]:
            panel, panel_layout = self.make_panel(
                name,
                "Application Windows — intégration à venir."
            )
            layout.addWidget(panel)

        layout.addStretch()
        return page

    def create_chat_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("Assistant CAPRI")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Discute avec ton assistant local. "
            "Les réponses utilisent ton moteur CAPRI et sa mémoire."
        )
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        self.chat_history = QListWidget()
        self.chat_history.setWordWrap(True)
        self.chat_history.addItem(
            "CAPRI : Salut ! Je suis prêt. Que veux-tu faire ?"
        )
        layout.addWidget(self.chat_history, 1)

        input_layout = QHBoxLayout()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Écris un message à CAPRI...")
        self.chat_input.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Envoyer")
        self.send_button.setObjectName("Primary")
        self.send_button.clicked.connect(self.send_message)

        input_layout.addWidget(self.chat_input, 1)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)

        self.chat_status = QLabel("CAPRI est prêt.")
        self.chat_status.setObjectName("Subtitle")
        layout.addWidget(self.chat_status)

        return page

    def send_message(self):
        message = self.chat_input.text().strip()

        if not message:
            return

        # Évite de lancer plusieurs réponses en même temps.
        if self.chat_worker is not None and self.chat_worker.isRunning():
            return

        self.chat_history.addItem(f"Toi : {message}")
        self.chat_input.clear()
        self.chat_history.scrollToBottom()

        self.chat_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.chat_status.setText("CAPRI réfléchit...")

        self.chat_worker = ChatWorker(message)
        self.chat_worker.answer_ready.connect(self.show_answer)
        self.chat_worker.finished.connect(self.worker_finished)
        self.chat_worker.start()

    def show_answer(self, answer):
        self.chat_history.addItem(f"CAPRI : {answer}")
        self.chat_history.scrollToBottom()

    def worker_finished(self):
        self.chat_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.chat_status.setText("CAPRI est prêt.")
        self.chat_input.setFocus()
        self.chat_worker = None

    def change_page(self, index):
        self.pages.setCurrentIndex(index)

        for i, button in enumerate(self.nav_buttons):
            button.setObjectName("Active" if i == index else "")
            button.style().unpolish(button)
            button.style().polish(button)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    window = CapriWindow()
    window.show()

    sys.exit(app.exec())
