"""
speech/vad.py — Silero VAD with PyTorch, graceful RMS fallback.

Silero VAD is the recommended approach:
  - Single-forward-pass ONNX/Torch model, ~1ms per 30ms chunk at 16 kHz.
  - If torch / silero are not installed, falls back to RMS energy detection
    so the rest of the pipeline keeps running in degraded mode.
"""
import math
import struct
from typing import List, Optional
from observability.logger import logger

# ── Silero VAD loader (optional dependency) ───────────────────────────────────
_silero_model = None
_torch         = None

def _load_silero() -> bool:
    global _silero_model, _torch
    if _silero_model is not None:
        return True
    try:
        import torch
        _torch = torch
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
        )
        model.eval()
        _silero_model = model
        logger.info("[SileroVAD] Silero VAD model loaded via torch.hub.")
        return True
    except Exception as exc:
        logger.warning(f"[SileroVAD] Silero torch model unavailable ({exc}). Using RMS fallback.")
        return False


def _pcm16_to_float_tensor(pcm_bytes: bytes):
    """Convert raw 16-bit LE PCM bytes to a normalised float32 torch tensor."""
    n_samples = len(pcm_bytes) // 2
    samples = struct.unpack_from(f"<{n_samples}h", pcm_bytes, 0)
    tensor = _torch.tensor(samples, dtype=_torch.float32) / 32768.0
    return tensor


# ── Silero VAD ─────────────────────────────────────────────────────────────────
class SileroVAD:
    """
    Voice Activity Detection.

    Uses Silero VAD (PyTorch) when available; falls back to RMS energy
    thresholding when torch is not installed.

    Expected audio: 16-bit signed LE PCM @ 16 kHz.
    """

    # Silero expects exactly 512 samples (32 ms) at 16 kHz
    SILERO_CHUNK_SAMPLES = 512
    SILERO_SAMPLE_RATE   = 16_000

    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16_000):
        self.threshold     = threshold
        self.sampling_rate = sampling_rate
        self._use_silero   = _load_silero()
        self._h: Optional[object] = None   # hidden state for stateful Silero
        self._c: Optional[object] = None

    # ── Public API ─────────────────────────────────────────────────────────────
    def is_speech(self, pcm_data: bytes) -> bool:
        """Return True if the audio chunk contains speech."""
        if not pcm_data or len(pcm_data) < 2:
            return False
        if self._use_silero:
            return self._silero_is_speech(pcm_data)
        return self._rms_is_speech(pcm_data)

    def reset_states(self) -> None:
        """Reset Silero internal GRU states (call between utterances)."""
        if self._use_silero and _silero_model is not None:
            _silero_model.reset_states()
        self._h = None
        self._c = None

    def extract_speech_segments(self, pcm_data: bytes, chunk_size: int = 1024) -> List[bytes]:
        """Return only the sub-chunks that contain speech."""
        speech_chunks: List[bytes] = []
        if not pcm_data:
            return speech_chunks
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i : i + chunk_size]
            if self.is_speech(chunk):
                speech_chunks.append(chunk)
        return speech_chunks

    # ── Internal helpers ───────────────────────────────────────────────────────
    def _silero_is_speech(self, pcm_data: bytes) -> bool:
        try:
            tensor = _pcm16_to_float_tensor(pcm_data)
            # Silero requires exactly SILERO_CHUNK_SAMPLES; pad / trim as needed
            target = self.SILERO_CHUNK_SAMPLES
            if tensor.shape[0] < target:
                pad = _torch.zeros(target - tensor.shape[0])
                tensor = _torch.cat([tensor, pad])
            else:
                tensor = tensor[:target]
            tensor = tensor.unsqueeze(0)  # [1, 512]
            with _torch.no_grad():
                prob = _silero_model(tensor, self.SILERO_SAMPLE_RATE).item()
            return prob >= self.threshold
        except Exception as exc:
            logger.debug(f"[SileroVAD] Silero inference error ({exc}), falling back to RMS.")
            return self._rms_is_speech(pcm_data)

    def _rms_is_speech(self, pcm_data: bytes) -> bool:
        n = len(pcm_data) // 2
        if n == 0:
            return False
        samples = struct.unpack_from(f"<{n}h", pcm_data, 0)
        rms = math.sqrt(sum(s * s for s in samples) / n)
        return rms > (self.threshold * 500.0)
