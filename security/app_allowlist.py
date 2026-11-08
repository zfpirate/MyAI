
"""Liste blanche stricte des applications de CAPRI."""

ALLOWED_BUILTINS = {
    "notepad": "Bloc-notes",
    "calculator": "Calculatrice",
}

# Chaque application externe est identifiée par son raccourci exact.
# Les arguments sont définis ici, jamais récupérés librement.
ALLOWED_SHORTCUTS = {
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Discord.lnk": {
        "name": "Discord",
        "target": r"C:\Users\maxence\AppData\Local\Discord\Discord.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Discord\app-1.0.9267",
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Google Chrome.lnk": {
        "name": "Google Chrome",
        "target": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "arguments": ("--source-shortcut-location=start-menu",),
        "working_directory": r"C:\Program Files\Google\Chrome\Application",
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Steam\Steam.lnk": {
        "name": "Steam",
        "target": r"C:\Program Files (x86)\Steam\Steam.exe",
        "arguments": (),
        "working_directory": r"C:\Program Files (x86)\Steam",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Spotify.lnk": {
        "name": "Spotify",
        "target": r"C:\Users\maxence\AppData\Roaming\Spotify\Spotify.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Roaming\Spotify",
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Microsoft Edge.lnk": {
        "name": "Microsoft Edge",
        "target": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "arguments": ("--source-shortcut-location=start-menu",),
        "working_directory": r"C:\Program Files (x86)\Microsoft\Edge\Application",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Navigateur Opera GX.lnk": {
        "name": "Navigateur Opera GX",
        "target": r"C:\Users\maxence\AppData\Local\Programs\Opera GX\opera.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Programs\Opera GX",
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\OBS Studio.lnk": {
        "name": "OBS Studio",
        "target": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        "arguments": (),
        "working_directory": r"C:\Program Files\obs-studio\bin\64bit",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Visual Studio Code.lnk": {
        "name": "Visual Studio Code",
        "target": r"C:\Users\maxence\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Programs\Microsoft VS Code",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Cursor.lnk": {
        "name": "Cursor",
        "target": r"C:\Users\maxence\AppData\Local\Programs\cursor\Cursor.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Programs\cursor",
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\JetBrains\PyCharm 2025.2.2.lnk": {
        "name": "PyCharm 2025.2.2",
        "target": r"C:\Program Files\JetBrains\PyCharm 2025.2.2\bin\pycharm64.exe",
        "arguments": (),
        "working_directory": r"C:\Program Files\JetBrains\PyCharm 2025.2.2",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Windsurf\Windsurf.lnk": {
        "name": "Windsurf",
        "target": r"C:\Users\maxence\AppData\Local\Programs\Windsurf\Windsurf.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Programs\Windsurf",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Ollama.lnk": {
        "name": "Ollama",
        "target": r"C:\Users\maxence\AppData\Local\Programs\Ollama\ollama app.exe",
        "arguments": (),
        "working_directory": r"C:\Users\maxence\AppData\Local\Programs\Ollama",
    },
    r"C:\Users\maxence\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\CapCut\CapCut.lnk": {
        "name": "CapCut",
        "target": r"C:\Users\maxence\AppData\Local\CapCut\Apps\CapCut.exe",
        "arguments": ("--src3",),
        "working_directory": None,
    },
    r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Riot Games\Riot Client.lnk": {
        "name": "Riot Client",
        "target": r"C:\Riot Games\Riot Client\RiotClientServices.exe",
        "arguments": (),
        "working_directory": r"C:\Riot Games\Riot Client",
    },
}

