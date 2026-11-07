"""
qr_detect.py  -  put this file inside your  src/  folder.

A STRONG QR detector. It keeps trying until it can read the code:
  1. reads the normal camera picture
  2. finds where the QR is, crops it, enlarges it and sharpens it
     (this fixes blurry codes)
  3. fixes washed-out / too-bright pictures (like a phone screen)
  4. tries black-and-white versions of the picture

It also returns the 4 corners of the QR, so you can draw a box that follows it.

Install once:
    pip install opencv-python pillow pyzbar numpy

Optional (even stronger on blurry codes):
    pip uninstall opencv-python
    pip install opencv-contrib-python

How to use in your own scan window:
    from src.qr_detect import QRDetector, configure_camera

    detector = QRDetector()
    configure_camera(cap)                  # once, after opening the camera
    ...
    text, corners = detector.detect(frame) # for every camera frame
    # text    -> the code, or "" if not readable yet
    # corners -> 4 corner points of the QR (or None if no QR seen)
"""

from itertools import islice

import cv2
import numpy as np

try:
    from pyzbar.pyzbar import decode as _zbar
except Exception:          # pyzbar not installed -> OpenCV readers are used
    _zbar = None

MAX_DETECT_WIDTH = 960     # big camera pictures are shrunk to this width for speed
_CLAHE = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))


def _gamma_lut(gamma: float):
    return np.array([((i / 255.0) ** gamma) * 255 for i in range(256)], np.uint8)


_DARKEN = _gamma_lut(2.0)   # fixes washed-out / overexposed pictures


def configure_camera(cap) -> None:
    """Ask the camera for a bigger picture and autofocus (ignored if unsupported)."""
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
    except Exception:
        pass


def _variants(gray):
    """Different 'fixed' versions of the same picture."""
    yield gray
    yield cv2.LUT(gray, _DARKEN)                                  # too bright -> darker
    yield _CLAHE.apply(gray)                                      # more contrast
    sharp = cv2.addWeighted(gray, 2.0, cv2.GaussianBlur(gray, (0, 0), 3), -1.0, 0)
    yield sharp                                                   # sharpen blur
    yield cv2.LUT(sharp, _DARKEN)
    yield cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    yield cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 8)


class QRDetector:
    def __init__(self):
        # WeChat reader = very good with blurry codes (needs opencv-contrib)
        self.wechat = None
        try:
            self.wechat = cv2.wechat_qrcode_WeChatQRCode()
        except Exception:
            pass

        self.locator = cv2.QRCodeDetector()
        self._cv_readers = [self.locator]
        if hasattr(cv2, "QRCodeDetectorAruco"):
            try:
                self._cv_readers.append(cv2.QRCodeDetectorAruco())
            except Exception:
                pass

    # ------------------------------------------------------------------
    def detect(self, frame):
        """Return (text, corners). text is "" if the code can't be read yet."""
        h, w = frame.shape[:2]
        scale = 1.0
        if w > MAX_DETECT_WIDTH:
            scale = MAX_DETECT_WIDTH / w
            frame = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

        text, pts = self._detect_gray(gray)
        if pts is not None:
            pts = (pts / scale).astype(np.float32)
        return text, pts

    # ------------------------------------------------------------------
    def _detect_gray(self, gray):
        # 1) quick try on the normal picture
        text, pts = self._decode_once(gray)
        if text:
            return text, pts

        # 2) find the QR, crop it, enlarge it, fix it, read it again
        loc = self._locate(gray)
        if loc is not None:
            roi, (x0, y0, s) = self._crop(gray, loc)
            for v in _variants(roi):
                text, p = self._decode_once(v)
                if text:
                    p = (p / s + np.array([x0, y0], np.float32)) if p is not None else loc
                    return text, p
            return "", loc      # QR seen but not readable yet -> box still follows it

        # 3) QR not even located: fix the whole picture and try again
        for v in islice(_variants(gray), 1, 6):
            text, pts = self._decode_once(v)
            if text:
                return text, pts
        return "", None

    # ------------------------------------------------------------------
    def _decode_once(self, img):
        if self.wechat is not None:
            try:
                texts, pts = self.wechat.detectAndDecode(img)
                for t, p in zip(texts, pts):
                    if t:
                        return t, np.asarray(p, np.float32).reshape(-1, 2)
            except cv2.error:
                pass

        if _zbar is not None:
            try:
                for r in _zbar(img):
                    text = r.data.decode("utf-8", errors="ignore")
                    poly = np.array([(p.x, p.y) for p in r.polygon], np.float32)
                    if len(poly) != 4:
                        l, t, w, h = r.rect
                        poly = np.array([[l, t], [l + w, t], [l + w, t + h], [l, t + h]], np.float32)
                    return text, poly
            except Exception:
                pass

        for reader in self._cv_readers:
            try:
                text, p, _ = reader.detectAndDecode(img)
                if text:
                    return text, (p.reshape(-1, 2).astype(np.float32) if p is not None else None)
            except cv2.error:
                pass
        return "", None

    def _locate(self, gray):
        """Find the 4 corners of a QR even when it can't be decoded."""
        for img in (gray, cv2.LUT(gray, _DARKEN)):
            try:
                found, pts = self.locator.detect(img)
            except cv2.error:
                continue
            if found and pts is not None:
                pts = pts.reshape(-1, 2).astype(np.float32)
                if cv2.contourArea(pts) > 400:
                    return pts
        return None

    @staticmethod
    def _crop(gray, pts, pad=0.25):
        """Cut out the QR area (with some margin) and enlarge it."""
        x, y, w, h = cv2.boundingRect(pts.astype(np.int32))
        px, py = int(w * pad), int(h * pad)
        x0, y0 = max(0, x - px), max(0, y - py)
        x1, y1 = min(gray.shape[1], x + w + px), min(gray.shape[0], y + h + py)
        roi = gray[y0:y1, x0:x1]
        s = max(1.0, 420.0 / max(roi.shape[:2]))
        roi = cv2.resize(roi, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        return roi, (x0, y0, s)