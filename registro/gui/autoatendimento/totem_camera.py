# ----------------------------------------------------------------------------
# Arquivo: registro/gui/autoatendimento/totem_camera.py (Captura e QR do Totem)
# ----------------------------------------------------------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 Mateus G Pereira <mateus.pereira@ifsp.edu.br>

"""Isola dependências opcionais de câmera (OpenCV / NumPy / pyzbar) do Totem."""

import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)

cv2: Any = None
np: Any = None
ZBarSymbol: Any = None
decode: Any = None

try:
    import cv2 as _cv2
    import numpy as _np

    if sys.platform == "win32":
        import pyzbar

        os.add_dll_directory(os.path.dirname(pyzbar.__file__))

    from pyzbar.pyzbar import ZBarSymbol as _ZBarSymbol
    from pyzbar.pyzbar import decode as _decode

    cv2 = _cv2
    np = _np
    ZBarSymbol = _ZBarSymbol
    decode = _decode
    OPENCV_DISPONIVEL = True
except (ImportError, OSError) as e:
    logger.warning("Bibliotecas de câmera não disponíveis: %s", e)
    OPENCV_DISPONIVEL = False


def decodificar_primeiro_qr(frame: Any) -> Optional[str]:
    """Decodifica o primeiro QR Code válido no frame e desenha seu contorno."""
    if not OPENCV_DISPONIVEL or decode is None:
        return None
    decoded_objects = decode(frame, symbols=[ZBarSymbol.QRCODE])
    for obj in decoded_objects:
        codigo = obj.data.decode("utf-8").strip()
        if codigo:
            pts = obj.polygon
            if len(pts) == 4:
                pts_arr = np.array(pts, np.int32).reshape((-1, 1, 2))
                cv2.polylines(frame, [pts_arr], True, (0, 255, 0), 3)
            return codigo
    return None
