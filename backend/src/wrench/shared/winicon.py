"""Windows icon extraction: the icon of an executable or of a `shell:AppsFolder`
entry, encoded as a PNG. Pure ctypes, no dependency; never raises."""

import ctypes
import logging
import os
import struct
import sys
import zlib
from ctypes import wintypes
from typing import Any

logger = logging.getLogger("wrench.shared.winicon")

SHGFI_ICON = 0x100
SHGFI_LARGEICON = 0x0
SHGFI_SMALLICON = 0x1
SHGFI_PIDL = 0x8
DIB_RGB_COLORS = 0
BI_RGB = 0


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HANDLE),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HANDLE),
        ("hbmColor", wintypes.HANDLE),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", ctypes.c_long),
        ("bmWidth", ctypes.c_long),
        ("bmHeight", ctypes.c_long),
        ("bmWidthBytes", ctypes.c_long),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def encode_png(width: int, height: int, bgra: bytes) -> bytes:
    """8-bit RGBA PNG from top-down BGRA pixels."""
    if len(bgra) != width * height * 4:
        raise ValueError("pixel buffer does not match the dimensions")
    rgba = bytearray(bgra)
    rgba[0::4], rgba[2::4] = bgra[2::4], bgra[0::4]
    stride = width * 4
    raw = b"".join(b"\x00" + bytes(rgba[y * stride : (y + 1) * stride]) for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def _bits(gdi32: Any, hdc: Any, hbm: Any, width: int, height: int) -> bytes:
    """32-bit top-down pixels of a bitmap."""
    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    buf = ctypes.create_string_buffer(width * height * 4)
    if not gdi32.GetDIBits(hdc, hbm, 0, height, buf, ctypes.byref(header), DIB_RGB_COLORS):
        raise OSError("GetDIBits failed")
    return buf.raw


def _icon_pixels(hicon: Any, user32: Any, gdi32: Any) -> tuple[int, int, bytes]:
    info = ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(info)):
        raise OSError("GetIconInfo failed")
    hdc = user32.GetDC(None)
    try:
        if not info.hbmColor:
            raise OSError("monochrome icon")
        bm = BITMAP()
        gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        width, height = bm.bmWidth, bm.bmHeight
        pixels = bytearray(_bits(gdi32, hdc, info.hbmColor, width, height))
        if not any(pixels[3::4]):
            mask = _bits(gdi32, hdc, info.hbmMask, width, height)
            pixels[3::4] = bytes(0 if m else 255 for m in mask[0::4])
        return width, height, bytes(pixels)
    finally:
        user32.ReleaseDC(None, hdc)
        if info.hbmColor:
            gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            gdi32.DeleteObject(info.hbmMask)


def icon_png(target: str, size: int = 32) -> bytes | None:
    """PNG of the icon of `target` (a file path, or a `shell:` item), or None."""
    if sys.platform != "win32":
        return None
    try:
        return _icon_png(os.path.expandvars(target), size)
    except Exception:
        logger.debug("icon extraction failed for %r", target, exc_info=True)
        return None


def _icon_png(target: str, size: int) -> bytes | None:
    windll: Any = ctypes.windll  # type: ignore[attr-defined,unused-ignore]
    user32, gdi32 = windll.user32, windll.gdi32
    shell32, ole32 = windll.shell32, windll.ole32
    user32.GetDC.restype = wintypes.HDC
    user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ICONINFO)]
    user32.DestroyIcon.argtypes = [wintypes.HANDLE]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC,
        wintypes.HANDLE,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.UINT,
    ]
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    shell32.SHGetFileInfoW.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(SHFILEINFOW),
        wintypes.UINT,
        wintypes.UINT,
    ]
    shell32.SHGetFileInfoW.restype = ctypes.c_size_t
    shell32.SHParseDisplayName.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
    ]
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    flags = SHGFI_ICON | (SHGFI_SMALLICON if size <= 16 else SHGFI_LARGEICON)
    fi = SHFILEINFOW()
    pidl = ctypes.c_void_p()
    try:
        if target.lower().startswith("shell:"):
            if shell32.SHParseDisplayName(target, None, ctypes.byref(pidl), 0, None) != 0:
                return None
            ok = shell32.SHGetFileInfoW(
                pidl, 0, ctypes.byref(fi), ctypes.sizeof(fi), flags | SHGFI_PIDL
            )
        else:
            if not os.path.exists(target):
                return None
            ok = shell32.SHGetFileInfoW(target, 0, ctypes.byref(fi), ctypes.sizeof(fi), flags)
    finally:
        if pidl.value:
            ole32.CoTaskMemFree(pidl)
    if not ok or not fi.hIcon:
        return None
    try:
        width, height, pixels = _icon_pixels(fi.hIcon, user32, gdi32)
    finally:
        user32.DestroyIcon(fi.hIcon)
    return encode_png(width, height, pixels)
