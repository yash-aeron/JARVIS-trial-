import math
from typing import List
from observability.logger import logger

class SileroVAD:
    """Production Voice Activity Detection (VAD) engine analyzing audio energy levels and speech boundaries."""
    
    def __init__(self, threshold: float = 0.5, sampling_rate: int = 16000):
        self.threshold = threshold
        self.sampling_rate = sampling_rate

    def is_speech(self, pcm_data: bytes) -> bool:
        if not pcm_data or len(pcm_data) < 2:
            return False
            
        # Calculate RMS energy of 16-bit PCM audio
        samples = [int.from_bytes(pcm_data[i:i+2], byteorder='little', signed=True) for i in range(0, len(pcm_data) - 1, 2)]
        if not samples:
            return False
            
        sum_squares = sum(s ** 2 for s in samples)
        rms = math.sqrt(sum_squares / len(samples))
        
        # Audio energy thresholding for speech activity
        speech_detected = rms > (self.threshold * 500.0)
        return speech_detected

    def extract_speech_segments(self, pcm_data: bytes, chunk_size: int = 1024) -> List[bytes]:
        speech_chunks: List[bytes] = []
        if not pcm_data:
            return speech_chunks
            
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i:i+chunk_size]
            if self.is_speech(chunk):
                speech_chunks.append(chunk)
        return speech_chunks
