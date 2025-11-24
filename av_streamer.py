from __future__ import annotations
import time
import threading
from fractions import Fraction
from typing import Callable, Optional, Tuple
from collections import deque

import numpy as np

try:
    import av
    from av.audio.resampler import AudioResampler
except Exception as e:  # pragma: no cover
    av = None
    AudioResampler = None

from PyQt6.QtGui import QImage
from PyQt6.QtCore import QSize


class AVMasterClockRTMPStreamer:
    """RTMP streamer using PyAV with a master clock based on time.monotonic().

    - Video frames are provided by a callback returning QImage of target size.
    - Audio is captured from a platform device using FFmpeg device demuxers via PyAV.
    - Both audio and video are timestamped (PTS) against the same monotonic timeline.
    - Audio is resampled to 48 kHz stereo AAC and slightly time-stretched via sample drop/pad to correct drift.
    - Output is FLV (RTMP) to the given URL.

    Notes:
      - This backend currently focuses on macOS using avfoundation for audio input. Other platforms may need device string adjustments.
    """

    def __init__(self,
                 frame_provider: Callable[[QSize], QImage],
                 width: int,
                 height: int,
                 fps: int,
                 url: str,
                 audio_device: str | None,
                 encoder: str = 'libx264',
                 video_bitrate_kbps: int = 4500,
                 log_cb: Optional[Callable[[str], None]] = None,
                 resolve_avf_index: Optional[Callable[[str], Optional[str]]] = None):
        if av is None:
            raise RuntimeError("PyAV is not installed. Please install 'av' to use master clock streaming.")
        self._frame_provider = frame_provider
        self._w = int(width)
        self._h = int(height)
        self._fps = int(fps)
        self._url = url
        self._audio_device = (audio_device or '').strip()
        self._encoder = encoder
        self._video_bitrate_kbps = int(max(500, video_bitrate_kbps))
        self._log = log_cb or (lambda s: None)
        self._resolve_avf_index = resolve_avf_index

        # AV state
        self._oc: Optional[av.container.OutputContainer] = None
        self._vstream = None
        self._astream = None
        self._audio_ic: Optional[av.container.InputContainer] = None
        self._audio_in_stream = None

        # Master clock
        self._t0 = 0.0  # monotonic start
        self._video_time_base = Fraction(1, max(1, self._fps))
        self._audio_time_base = Fraction(1, 48000)
        # PTS counters
        self._video_frame_index = 0  # counts frames since start

        # Threads
        self._run = False
        self._vthread: Optional[threading.Thread] = None
        self._athread: Optional[threading.Thread] = None

        # Audio drift tracking
        self._audio_total_samples_out = 0  # number of audio samples written to encoder in 48k domain
        # Audio delay buffer (implements adelay-like behavior)
        self._audio_buffer: deque[av.AudioFrame] = deque()
        self._buffered_samples: int = 0
        self._pending_audio_delay_samples: int = 0  # samples to withhold before starting to emit

        # Lock for muxing
        self._mux_lock = threading.Lock()

    # ---- Public API ----
    def start(self):
        self._open_output()
        self._open_audio_input()
        self._run = True
        self._t0 = time.monotonic()
        self._video_frame_index = 0

        self._vthread = threading.Thread(target=self._video_loop, name="AV_VideoLoop", daemon=True)
        self._vthread.start()

        self._athread = threading.Thread(target=self._audio_loop, name="AV_AudioLoop", daemon=True)
        self._athread.start()

    def stop(self):
        self._run = False
        # Join threads
        for th in (self._vthread, self._athread):
            if th is not None and th.is_alive():
                th.join(timeout=2.0)
        self._flush_and_close()

    def source_switched(self, delay_ms: int = 150):
        """Notify backend that program source switched.
        - Discard any buffered audio to avoid bleed from previous source.
        - Apply a small pending delay so new audio does not lead video.
        - Do NOT reset master counters; PTS remains on the global timeline.
        """
        try:
            # Clear buffer immediately
            self._audio_buffer.clear()
            self._buffered_samples = 0
            # Schedule a delay (samples)
            d = int(max(0, delay_ms) * 48)  # 48kHz -> 48 samples per ms
            # Keep the larger of any existing pending delay and new request
            if d > self._pending_audio_delay_samples:
                self._pending_audio_delay_samples = d
            self._log(f"[AV] Source switch: cleared audio buffer and set pending delay {self._pending_audio_delay_samples} samples (~{self._pending_audio_delay_samples/48:.1f} ms)\n")
        except Exception:
            pass

    # ---- Setup helpers ----
    def _open_output(self):
        # Open RTMP FLV output
        self._oc = av.open(self._url, mode='w', format='flv', options={'rtmp_live': 'live'})

        # Video stream
        self._vstream = self._oc.add_stream(self._encoder, rate=self._fps)
        self._vstream.width = self._w
        self._vstream.height = self._h
        self._vstream.pix_fmt = 'yuv420p'
        self._vstream.time_base = self._video_time_base
        # Try to set bitrate-like parameters where supported
        try:
            self._vstream.bit_rate = self._video_bitrate_kbps * 1000
        except Exception:
            pass

        # Audio stream: AAC stereo 48k
        self._astream = self._oc.add_stream('aac', rate=48000)
        self._astream.channels = 2
        self._astream.layout = 'stereo'
        self._astream.sample_rate = 48000
        self._astream.time_base = self._audio_time_base

        self._log(f"[AV] Opened output -> {self._url} (v: {self._w}x{self._h}@{self._fps} yuv420p, a: 48k stereo AAC)\n")

    def _open_audio_input(self):
        if not self._audio_device:
            self._log("[AV] No audio device specified; will generate silence.\n")
            self._audio_ic = None
            self._audio_in_stream = None
            return
        # macOS avfoundation input: use ":<index>" form when possible
        dev_spec = self._audio_device
        if self._resolve_avf_index is not None:
            try:
                idx = self._resolve_avf_index(self._audio_device)
                if idx:
                    dev_spec = f":{idx}"
            except Exception:
                pass
        try:
            self._audio_ic = av.open(dev_spec, format='avfoundation', mode='r', timeout=1.0)
            # Find the first audio stream
            for s in self._audio_ic.streams:
                if s.type == 'audio':
                    self._audio_in_stream = s
                    break
            if not self._audio_in_stream:
                self._log("[AV] No audio stream found on device; falling back to silence.\n")
                self._audio_ic.close()
                self._audio_ic = None
        except Exception as e:
            self._log(f"[AV] Failed to open audio device via avfoundation: {e}\n")
            self._audio_ic = None
            self._audio_in_stream = None

    # ---- Loops ----
    def _video_loop(self):
        size = QSize(self._w, self._h)
        frame_period = 1.0 / float(max(1, self._fps))
        next_t = time.monotonic()
        while self._run:
            now = time.monotonic()
            if now < next_t:
                time.sleep(min(0.002, next_t - now))
                continue
            next_t += frame_period

            try:
                qimg = self._frame_provider(size)
                if qimg is None or qimg.isNull():
                    continue
                if qimg.size() != size:
                    qimg = qimg.scaled(size)
                if qimg.format() != QImage.Format.Format_RGBA8888:
                    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)

                # Convert QImage -> numpy RGBA -> VideoFrame in RGB, then reformat to yuv420p
                ptr = qimg.bits()
                ptr.setsize(self._w * self._h * 4)
                arr = np.frombuffer(ptr, dtype=np.uint8).reshape((self._h, self._w, 4))
                # Drop alpha to get RGB24
                rgb = arr[:, :, :3]
                vf = av.VideoFrame.from_ndarray(rgb, format='rgb24')
                vf = vf.reformat(self._w, self._h, format='yuv420p')

                # PTS from explicit frame counter: pts = frame_index (time_base = 1/fps)
                vf.pts = self._video_frame_index
                vf.time_base = self._video_time_base

                for packet in self._vstream.encode(vf):
                    with self._mux_lock:
                        self._oc.mux(packet)
                self._video_frame_index += 1
            except Exception as e:
                self._log(f"[AV][video] error: {e}\n")
                # Try to continue
                continue

        # Flush
        try:
            for packet in self._vstream.encode(None):
                with self._mux_lock:
                    self._oc.mux(packet)
        except Exception:
            pass

    def _audio_loop(self):
        resampler = AudioResampler(format='s16', layout='stereo', rate=48000)
        silence_frame = self._make_silence_frame(1024)

        while self._run:
            try:
                if self._audio_ic is None or self._audio_in_stream is None:
                    # No device: generate silence block aligned to master
                    out_frames = [silence_frame]
                else:
                    # Read one packet -> decode -> resample
                    in_pkt = next(self._audio_ic.demux(self._audio_in_stream), None)
                    if in_pkt is None:
                        out_frames = [silence_frame]
                    else:
                        out_frames = []
                        for frm in in_pkt.decode():
                            # Convert to 48k stereo s16
                            for afr in resampler.resample(frm):
                                out_frames.append(afr)
                        if not out_frames:
                            out_frames = [silence_frame]

                # Compute drift using counter-based PTS (seconds)
                video_pts_seconds = (self._video_frame_index / float(max(1, self._fps)))
                audio_pts_seconds = (self._audio_total_samples_out / 48000.0)
                drift = audio_pts_seconds - video_pts_seconds
                if drift > 0.200:
                    # Set pending delay to at least current drift amount
                    desired_delay = int(drift * 48000.0)
                    if desired_delay > self._pending_audio_delay_samples:
                        self._pending_audio_delay_samples = desired_delay

                # Apply drift correction relative to master clock before buffering
                for afr in out_frames:
                    nb_samples = int(afr.samples)

                    desired_samples = int((time.monotonic() - self._t0) * 48000)
                    delta = desired_samples - (self._audio_total_samples_out + self._buffered_samples)
                    if delta > 240:  # >5ms late relative to master: drop some samples
                        drop = min(delta, nb_samples // 4)
                        if drop > 0:
                            afr = self._drop_samples(afr, drop)
                            nb_samples = int(afr.samples)
                    elif delta < -240:  # >5ms early: pad zeros
                        pad = min(-delta, 480)
                        if pad > 0:
                            afr = self._pad_silence(afr, pad)
                            nb_samples = int(afr.samples)

                    # Enqueue into delay buffer
                    self._audio_buffer.append(afr)
                    self._buffered_samples += nb_samples

                # Emit from buffer depending on pending delay
                if self._pending_audio_delay_samples > 0:
                    if self._buffered_samples >= self._pending_audio_delay_samples:
                        # Delay accumulated, start emitting and clear pending
                        self._pending_audio_delay_samples = 0
                    else:
                        # Not enough buffered yet; hold emission this cycle
                        continue

                # Emit all currently buffered frames this cycle (or you can rate limit)
                while self._audio_buffer:
                    afr = self._audio_buffer.popleft()
                    nb_samples = int(afr.samples)

                    afr.sample_rate = 48000
                    afr.time_base = self._audio_time_base
                    afr.pts = self._audio_total_samples_out

                    self._audio_total_samples_out += nb_samples
                    self._buffered_samples -= nb_samples

                    for packet in self._astream.encode(afr):
                        with self._mux_lock:
                            self._oc.mux(packet)
            except StopIteration:
                # No more audio; sleep a bit
                time.sleep(0.005)
            except Exception as e:
                self._log(f"[AV][audio] error: {e}\n")
                time.sleep(0.005)

        # Flush
        try:
            for packet in self._astream.encode(None):
                with self._mux_lock:
                    self._oc.mux(packet)
        except Exception:
            pass

    # ---- Utils ----
    def _flush_and_close(self):
        try:
            if self._oc is not None:
                try:
                    with self._mux_lock:
                        self._oc.close()
                except Exception:
                    pass
        finally:
            self._oc = None
        try:
            if self._audio_ic is not None:
                self._audio_ic.close()
        except Exception:
            pass
        self._audio_ic = None

    def _make_silence_frame(self, samples: int):
        afr = av.AudioFrame(format='s16', layout='stereo', samples=samples)
        for p in afr.planes:
            # zero-initialize
            b = p.to_bytes()
            p.update(b)  # already zeros
        afr.sample_rate = 48000
        return afr

    def _pad_silence(self, afr: av.AudioFrame, samples: int) -> av.AudioFrame:
        # Convert to ndarray, pad zeros at end, return a new frame
        arr = afr.to_ndarray()
        if arr.ndim == 1:
            arr = np.expand_dims(arr, axis=0)
        pad = np.zeros((arr.shape[0], samples), dtype=arr.dtype)
        new_arr = np.concatenate([arr, pad], axis=1)
        out = av.AudioFrame(format=afr.format.name, layout=afr.layout.name, samples=new_arr.shape[1])
        for ch, plane in enumerate(out.planes):
            plane.update(new_arr[ch].tobytes())
        out.sample_rate = 48000
        return out

    def _drop_samples(self, afr: av.AudioFrame, samples: int) -> av.AudioFrame:
        arr = afr.to_ndarray()
        if arr.ndim == 1:
            arr = np.expand_dims(arr, axis=0)
        if samples >= arr.shape[1]:
            return self._make_silence_frame(afr.samples)
        new_arr = arr[:, samples:]
        out = av.AudioFrame(format=afr.format.name, layout=afr.layout.name, samples=new_arr.shape[1])
        for ch, plane in enumerate(out.planes):
            plane.update(new_arr[ch].tobytes())
        out.sample_rate = 48000
        return out
