"""Enregistrement de messages vocaux pour la messagerie du poste opérateur.

S'appuie sur QtMultimedia (QMediaCaptureSession + QAudioInput + QMediaRecorder).
Le module se dégrade proprement : si QtMultimedia est absent ou qu'aucun
périphérique d'entrée audio n'est disponible, ``available()`` renvoie ``False``
et l'interface masque le bouton d'enregistrement.

Le fichier produit est encodé en base64 dans une *data URL* (``data:audio/…``)
compatible avec le backend et relisible côté web (portail agents / appli
citoyenne) comme côté bureau.
"""
import base64
import mimetypes
import os
import tempfile

try:
    from PySide6.QtCore import QObject, QUrl, Signal
    from PySide6.QtMultimedia import (
        QAudioInput,
        QMediaCaptureSession,
        QMediaDevices,
        QMediaFormat,
        QMediaRecorder,
    )

    _IMPORT_OK = True
except Exception:  # pragma: no cover - environnement sans QtMultimedia
    _IMPORT_OK = False
    QObject = object

    def Signal(*_a, **_k):  # type: ignore
        return None


def available():
    """Vrai si l'enregistrement audio est possible sur cette machine."""
    if not _IMPORT_OK:
        return False
    try:
        dev = QMediaDevices.defaultAudioInput()
        return dev is not None and not dev.isNull()
    except Exception:
        return False


class VoiceRecorder(QObject):
    """Enregistre un message vocal et émet ``finished(data_url)`` à l'arrêt."""

    finished = Signal(str)   # data URL prête à envoyer
    failed = Signal(str)     # message d'erreur lisible

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session = QMediaCaptureSession()
        self._audio_in = QAudioInput()
        self._session.setAudioInput(self._audio_in)
        self._recorder = QMediaRecorder()
        self._session.setRecorder(self._recorder)

        # Conteneur MPEG-4 + AAC : largement lisible (web et bureau).
        try:
            fmt = QMediaFormat(QMediaFormat.FileFormat.MPEG4)
            fmt.setAudioCodec(QMediaFormat.AudioCodec.AAC)
            self._recorder.setMediaFormat(fmt)
            self._ext = "m4a"
        except Exception:
            self._ext = "m4a"

        self._recorder.errorOccurred.connect(self._on_error)
        self._recorder.recorderStateChanged.connect(self._on_state)
        self._out_path = None
        self._stopping = False

    # ---- Contrôle ----
    def start(self):
        self._stopping = False
        self._out_path = os.path.join(
            tempfile.gettempdir(), f"safecity_voice_{os.getpid()}_{id(self) & 0xffff}.{self._ext}")
        self._recorder.setOutputLocation(QUrl.fromLocalFile(self._out_path))
        self._recorder.record()

    def stop(self):
        self._stopping = True
        self._recorder.stop()

    def is_recording(self):
        try:
            return self._recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState
        except Exception:
            return False

    # ---- Événements ----
    def _on_state(self, state):
        try:
            stopped = state == QMediaRecorder.RecorderState.StoppedState
        except Exception:
            stopped = False
        if stopped and self._stopping:
            self._stopping = False
            self._emit_result()

    def _on_error(self, *_):
        try:
            msg = self._recorder.errorString() or "Erreur d'enregistrement audio."
        except Exception:
            msg = "Erreur d'enregistrement audio."
        self.failed.emit(msg)

    def _emit_result(self):
        # Qt peut adapter l'extension au format réel : on relit l'emplacement réel.
        path = None
        try:
            loc = self._recorder.actualLocation().toLocalFile()
            if loc:
                path = loc
        except Exception:
            pass
        path = path or self._out_path
        if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
            self.failed.emit("Enregistrement vide.")
            return
        mime = mimetypes.guess_type(path)[0] or "audio/mp4"
        if not mime.startswith("audio/"):
            mime = "audio/mp4"
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        try:
            os.remove(path)
        except OSError:
            pass
        self.finished.emit(f"data:{mime};base64,{data}")
