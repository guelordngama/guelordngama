"""Génération et lecture du son d'alarme (sans fichier binaire embarqué).

Un court signal deux tons est synthétisé en mémoire et écrit dans un .wav
temporaire, lu via QSoundEffect. Repli sur QApplication.beep() si le module
multimédia n'est pas disponible.
"""
import math
import os
import struct
import tempfile
import wave

_ALARM_PATH = None


def _generate_alarm_wav():
    """Crée un .wav d'alarme (deux tons alternés) et renvoie son chemin."""
    global _ALARM_PATH
    if _ALARM_PATH and os.path.exists(_ALARM_PATH):
        return _ALARM_PATH

    rate = 44100
    path = os.path.join(tempfile.gettempdir(), "safecity_alarm.wav")
    frames = bytearray()
    # 3 bips montants (440 Hz puis 880 Hz), 0.15 s chacun.
    for freq in (660, 990, 660, 990):
        for i in range(int(rate * 0.15)):
            # Enveloppe pour éviter les clics.
            env = min(1.0, i / 400.0, (rate * 0.15 - i) / 400.0)
            sample = int(32767 * 0.35 * env * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", sample)
        frames += b"\x00\x00" * int(rate * 0.05)  # court silence

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(bytes(frames))
    _ALARM_PATH = path
    return path


class AlarmPlayer:
    """Joue le son d'alarme ; robuste si QtMultimedia est absent."""

    def __init__(self):
        self._effect = None
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            self._effect = QSoundEffect()
            self._effect.setSource(QUrl.fromLocalFile(_generate_alarm_wav()))
            self._effect.setVolume(0.6)
        except Exception:
            self._effect = None

    def play(self):
        if self._effect is not None:
            try:
                self._effect.play()
                return
            except Exception:
                pass
        # Repli : bip système.
        try:
            from PySide6.QtWidgets import QApplication

            QApplication.beep()
        except Exception:
            pass
