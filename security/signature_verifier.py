
"""Vérification des signatures numériques des applications."""

import os
import subprocess
from pathlib import Path


def verify_authenticode(executable_path, app_name="Application inconnue"):
    """Accepte les exécutables possédant une signature numérique valide."""

    path = Path(executable_path).resolve(strict=True)

    if not path.is_file() or path.suffix.lower() != ".exe":
        raise PermissionError("Exécutable invalide.")

    script = r"""
$sig = Get-AuthenticodeSignature -LiteralPath $env:CAPRI_SIGNATURE_PATH
$subject = ""

if ($sig.SignerCertificate) {
    $subject = $sig.SignerCertificate.Subject
}

[Console]::Out.WriteLine([string]$sig.Status)
[Console]::Out.WriteLine($subject)
"""

    env = os.environ.copy()
    env["CAPRI_SIGNATURE_PATH"] = str(path)

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            creationflags=getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            ),
            check=False,
        )

    except subprocess.TimeoutExpired:
        raise PermissionError(
            "Délai de vérification dépassé."
        )

    except OSError as error:
        raise PermissionError(
            f"Impossible de vérifier la signature : {error}"
        )

    if result.returncode != 0:
        raise PermissionError(
            "La vérification de signature a échoué."
        )

    lines = result.stdout.splitlines()

    status = lines[0].strip() if lines else ""
    publisher = lines[1].strip() if len(lines) > 1 else ""

    if status != "Valid":
        raise PermissionError(
            f"Signature numérique invalide : {status or 'inconnue'}."
        )

    if not publisher:
        raise PermissionError(
            "Aucun éditeur vérifiable."
        )

    return {
        "status": status,
        "publisher": publisher,
        "application": app_name,
    }
