"""Sons de l'application bureau : alarme d'alerte + accusé de réception.

Les sons sont synthétisés en mémoire (aucun fichier binaire embarqué) et lus
via QSoundEffect. Repli sur QApplication.beep() si QtMultimedia est absent.
"""
import math
import os
import struct
import tempfile
import wave

_CACHE = {}


def _write_wav(name, segments, rate=44100):
    """segments = liste de (fréquence_Hz, durée_s, volume). Écrit un .wav."""
    if name in _CACHE and os.path.exists(_CACHE[name]):
        return _CACHE[name]
    path = os.path.join(tempfile.gettempdir(), name)
    frames = bytearray()
    for freq, dur, vol in segments:
        n = int(rate * dur)
        for i in range(n):
            env = min(1.0, i / 400.0, (n - i) / 400.0)  # anti-clic
            frames += struct.pack("<h", int(32767 * vol * env * math.sin(2 * math.pi * freq * i / rate)))
        frames += b"\x00\x00" * int(rate * 0.03)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(bytes(frames))
    _CACHE[name] = path
    return path


def _alarm_wav():
    # Alarme urgente : bips alternés graves/aigus.
    return _write_wav("safecity_alarm.wav",
                      [(660, 0.15, 0.35), (990, 0.15, 0.35)] * 2)


def _ack_wav():
    # Accusé de réception : courte tierce ascendante, douce.
    return _write_wav("safecity_ack.wav",
                      [(880, 0.10, 0.28), (1174, 0.14, 0.28)])


def _notify_wav():
    # Notification de message : double « ping » discret et clair.
    return _write_wav("safecity_notify.wav",
                      [(1318, 0.08, 0.22), (1568, 0.10, 0.22)])


class SoundPlayer:
    """Joue les sons de l'application ; robuste si QtMultimedia est indisponible."""

    def __init__(self):
        self._alarm = self._make(_alarm_wav(), 0.6)
        self._ack = self._make(_ack_wav(), 0.4)
        self._notify = self._make(_notify_wav(), 0.4)

    def _make(self, path, volume):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            eff = QSoundEffect()
            eff.setSource(QUrl.fromLocalFile(path))
            eff.setVolume(volume)
            return eff
        except Exception:
            return None

    def _play(self, effect):
        if effect is not None:
            try:
                effect.play()
                return
            except Exception:
                pass
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.beep()
        except Exception:
            pass

    def play(self):
        """Alarme d'alerte (nouvelle alerte reçue)."""
        self._play(self._alarm)

    def play_ack(self):
        """Accusé de réception (alerte prise en compte par l'opérateur)."""
        self._play(self._ack)

    def play_notify(self):
        """Notification discrète (message reçu)."""
        self._play(self._notify)


# Compatibilité ascendante.
AlarmPlayer = SoundPlayer
