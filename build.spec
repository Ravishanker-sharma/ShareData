# -*- mode: python ; coding: utf-8 -*-
#
# Build with:  pyinstaller build.spec
#
# Before building, download the matching cloudflared binary into the project root:
#   macOS arm64:  cloudflared-darwin-arm64
#   macOS x86:    cloudflared-darwin-amd64
#   Windows:      cloudflared-windows-amd64.exe

import platform, os, sys

system = platform.system()
machine = platform.machine().lower()

# ── Cloudflared binary to bundle ────────────────────────────────────────────
if system == "Darwin":
    cf_src = "cloudflared-darwin-arm64" if "arm" in machine else "cloudflared-darwin-amd64"
    cf_dest = "cloudflared"
elif system == "Windows":
    cf_src = "cloudflared-windows-amd64.exe"
    cf_dest = "cloudflared.exe"
else:
    cf_src = "cloudflared-linux-amd64"
    cf_dest = "cloudflared"

binaries = []
if os.path.exists(cf_src):
    binaries = [(cf_src, ".")]   # bundled into root of the package

# ── Analysis ─────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=[],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.off",
        "fastapi",
        "starlette",
        "anyio",
        "httpx",
        "qrcode",
        "PIL",
        "PIL.Image",
        "PIL.PngImagePlugin",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ShareData",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # No terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.icns",  # Uncomment and add icon file if desired
)

# macOS .app bundle
if system == "Darwin":
    app = BUNDLE(
        exe,
        name="ShareData.app",
        icon=None,
        bundle_identifier="com.sharedata.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleShortVersionString": "1.0.0",
        },
    )
