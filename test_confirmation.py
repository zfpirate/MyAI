
import sys

from PySide6.QtWidgets import QApplication
from security.confirmation import create_confirmation_request
from interface.confirmation_dialog import ConfirmationDialog

app = QApplication(sys.argv)

request = create_confirmation_request(
    "apps.close",
    "Fermeture de Notepad"
)

if request is None:
    print("Impossible de créer la demande.")
    sys.exit(1)

dialog = ConfirmationDialog(request)

result = dialog.exec()

print("Autorisation :", dialog.approved)
print("Fenêtre fermée :", result)

sys.exit(0)
