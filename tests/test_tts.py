"""Tests for TTS module: sentence splitting and WAV-to-PCM16 conversion."""

import struct

import pytest

from src.voice.tts import split_sentences, wav_to_pcm16


class TestSplitSentences:
    """Test Korean sentence splitting for chunked TTS."""

    def test_single_sentence_ending_yo(self):
        result = split_sentences("예약 도와드릴까요.")
        assert result == ["예약 도와드릴까요."]

    def test_multiple_sentences(self):
        result = split_sentences("안녕하세요. 예약 도와드릴까요?")
        assert result == ["안녕하세요.", "예약 도와드릴까요?"]

    def test_korean_polite_endings(self):
        result = split_sentences("네 확인했습니다. 다음 주에 뵙겠습니다!")
        assert result == ["네 확인했습니다.", "다음 주에 뵙겠습니다!"]

    def test_empty_string(self):
        result = split_sentences("")
        assert result == []

    def test_no_sentence_ender(self):
        result = split_sentences("예약 확인")
        assert result == ["예약 확인"]

    def test_whitespace_only(self):
        result = split_sentences("   ")
        assert result == []

    def test_three_sentences(self):
        text = "안녕하세요. 예약 가능합니다. 몇 분이세요?"
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0] == "안녕하세요."
        assert result[1] == "예약 가능합니다."
        assert result[2] == "몇 분이세요?"

    def test_question_exclamation(self):
        result = split_sentences("감사합니다! 다시 전화해주세요.")
        assert result == ["감사합니다!", "다시 전화해주세요."]


def _make_wav(samples: list[int], sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Helper to create a minimal WAV file from PCM16 samples."""
    bits_per_sample = 16
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data = struct.pack(f"<{len(samples)}h", *samples)
    data_size = len(data)

    wav = b"RIFF"
    wav += struct.pack("<I", 36 + data_size)
    wav += b"WAVE"
    # fmt chunk
    wav += b"fmt "
    wav += struct.pack("<I", 16)  # chunk size
    wav += struct.pack("<H", 1)  # PCM format
    wav += struct.pack("<H", channels)
    wav += struct.pack("<I", sample_rate)
    wav += struct.pack("<I", byte_rate)
    wav += struct.pack("<H", block_align)
    wav += struct.pack("<H", bits_per_sample)
    # data chunk
    wav += b"data"
    wav += struct.pack("<I", data_size)
    wav += data
    return wav


class TestWavToPcm16:
    """Test WAV header parsing and PCM extraction."""

    def test_same_rate_passthrough(self):
        """If src and target rate match, PCM data should pass through."""
        samples = [100, 200, 300, 400, 500]
        wav = _make_wav(samples, sample_rate=8000)
        pcm = wav_to_pcm16(wav, target_rate=8000)
        extracted = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert list(extracted) == samples

    def test_downsampling(self):
        """16kHz to 8kHz should halve the number of samples."""
        samples = list(range(0, 1600))
        wav = _make_wav(samples, sample_rate=16000)
        pcm = wav_to_pcm16(wav, target_rate=8000)
        extracted = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert len(extracted) == 800  # 1600 / 2

    def test_stereo_to_mono(self):
        """Stereo WAV should be averaged down to mono."""
        # L=100, R=200, L=300, R=400 -> mono=[150, 350]
        stereo_samples = [100, 200, 300, 400]
        wav = _make_wav(stereo_samples, sample_rate=8000, channels=2)
        pcm = wav_to_pcm16(wav, target_rate=8000)
        extracted = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        assert list(extracted) == [150, 350]

    def test_invalid_header(self):
        """Non-WAV data should raise ValueError."""
        with pytest.raises(ValueError, match="RIFF"):
            wav_to_pcm16(b"not a wav file")

    def test_missing_wave_marker(self):
        """RIFF without WAVE marker should raise."""
        data = b"RIFF\x00\x00\x00\x00XXXX"
        with pytest.raises(ValueError, match="WAVE"):
            wav_to_pcm16(data)

    def test_clipping(self):
        """Resampled values should be clipped to int16 range."""
        samples = [32767, 32767, -32768, -32768]
        wav = _make_wav(samples, sample_rate=16000)
        pcm = wav_to_pcm16(wav, target_rate=8000)
        extracted = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        for s in extracted:
            assert -32768 <= s <= 32767
