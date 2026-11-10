"""Actions d'affichage Windows autorisées par CAPRI."""

import os

from security.action_manager import register_action, list_actions


def validate_display_params(params):
    return isinstance(params, dict) and not params


def validate_resolution_params(params):
    return (
        isinstance(params, dict)
        and set(params) == {"width", "height"}
        and all(
            isinstance(params[dimension], int)
            and not isinstance(params[dimension], bool)
            for dimension in ("width", "height")
        )
        and 320 <= params["width"] <= 16384
        and 200 <= params["height"] <= 8640
    )


def get_display_modes():
    """Retourne les modes pris en charge par l'écran principal."""
    if os.name != "nt":
        raise OSError("Le changement de résolution est disponible sous Windows.")

    import win32api

    device_name = None
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

    return win32api, device_name, modes


def apply_resolution(mode, width, height, win32api, device_name):
    """Teste puis applique un mode Windows précis."""
    import win32con

    current = win32api.EnumDisplaySettings(device_name, -1)
    if current.PelsWidth == width and current.PelsHeight == height:
        return {
            "status": "already_set",
            "width": width,
            "height": height,
        }

    test_result = win32api.ChangeDisplaySettingsEx(
        device_name,
        mode,
        win32con.CDS_TEST,
    )
    if test_result != win32con.DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(
            f"Windows refuse le mode {width}x{height}."
        )

    result = win32api.ChangeDisplaySettingsEx(
        device_name,
        mode,
        0,
    )
    if result != win32con.DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(
            f"Impossible d'appliquer le mode {width}x{height}."
        )

    return {
        "status": "changed",
        "width": width,
        "height": height,
    }


def set_native_resolution(_params):
    """Applique le mode de plus haute résolution disponible à l'écran principal."""
    win32api, device_name, modes = get_display_modes()
    native = max(
        modes,
        key=lambda mode: (
            mode.PelsWidth * mode.PelsHeight,
            mode.PelsWidth,
            mode.PelsHeight,
            mode.DisplayFrequency,
        ),
    )
    return apply_resolution(
        native,
        native.PelsWidth,
        native.PelsHeight,
        win32api,
        device_name,
    )


def set_resolution(params):
    """Applique une résolution exacte uniquement si l'écran la prend en charge."""
    if not validate_resolution_params(params):
        raise ValueError("Dimensions de résolution invalides.")

    width = params["width"]
    height = params["height"]
    win32api, device_name, modes = get_display_modes()
    matching_mode = next(
        (
            mode for mode in modes
            if mode.PelsWidth == width and mode.PelsHeight == height
        ),
        None,
    )
    if matching_mode is None:
        available = sorted({
            f"{mode.PelsWidth}x{mode.PelsHeight}"
            for mode in modes
        })
        raise ValueError(
            f"La résolution {width}x{height} n'est pas prise en charge "
            "par l'écran principal. Modes disponibles : "
            + ", ".join(available)
        )

    return apply_resolution(
        matching_mode,
        width,
        height,
        win32api,
        device_name,
    )


def register_display_actions():
    existing = {action["id"] for action in list_actions()}
    if "display.set_resolution" not in existing:
        register_action(
            action_id="display.set_resolution",
            permission_id="display.change_resolution",
            handler=set_resolution,
            description="Appliquer une résolution prise en charge par l'écran.",
            validator=validate_resolution_params,
        )
    if "display.set_native_resolution" not in existing:
        register_action(
            action_id="display.set_native_resolution",
            permission_id="display.change_resolution",
            handler=set_native_resolution,
            description="Rétablir la résolution maximale de l'écran principal.",
            validator=validate_display_params,
        )
