"""Actions d'affichage Windows autorisées par CAPRI."""

import os

from security.action_manager import register_action, list_actions


def validate_display_params(params):
    return isinstance(params, dict) and not params


def set_native_resolution(_params):
    """Applique le mode de plus haute résolution disponible à l'écran principal."""
    if os.name != "nt":
        raise OSError("Le changement de résolution est disponible sous Windows.")

    import win32api
    import win32con

    device_name = None
    current = win32api.EnumDisplaySettings(device_name, -1)
    modes = []
    mode_index = 0
    while True:
        try:
            mode = win32api.EnumDisplaySettings(device_name, mode_index)
        except win32api.error:
            break
        if mode.PelsWidth > 0 and mode.PelsHeight > 0:
            modes.append(mode)
        mode_index += 1

    if not modes:
        raise RuntimeError("Aucun mode de résolution disponible.")

    native = max(
        modes,
        key=lambda mode: (
            mode.PelsWidth * mode.PelsHeight,
            mode.PelsWidth,
            mode.PelsHeight,
            mode.DisplayFrequency,
        ),
    )
    if (
        current.PelsWidth == native.PelsWidth
        and current.PelsHeight == native.PelsHeight
    ):
        return {
            "status": "already_native",
            "width": current.PelsWidth,
            "height": current.PelsHeight,
        }

    test_result = win32api.ChangeDisplaySettingsEx(
        device_name,
        native,
        0,
        win32con.CDS_TEST,
        None,
    )
    if test_result != win32con.DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(
            f"Windows refuse le mode {native.PelsWidth}x{native.PelsHeight}."
        )

    result = win32api.ChangeDisplaySettingsEx(
        device_name,
        native,
        0,
        0,
        None,
    )
    if result != win32con.DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(
            f"Impossible d'appliquer le mode "
            f"{native.PelsWidth}x{native.PelsHeight}."
        )

    return {
        "status": "changed",
        "width": native.PelsWidth,
        "height": native.PelsHeight,
    }


def register_display_actions():
    existing = {action["id"] for action in list_actions()}
    if "display.set_native_resolution" not in existing:
        register_action(
            action_id="display.set_native_resolution",
            permission_id="display.change_resolution",
            handler=set_native_resolution,
            description="Rétablir la résolution maximale de l'écran principal.",
            validator=validate_display_params,
        )
