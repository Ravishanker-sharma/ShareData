APP_STYLE = """

/* ══ Root ══════════════════════════════════════════════════════════════════ */
QMainWindow {
    background-color: #0a0a14;
}
QWidget {
    background-color: transparent;
    color: #f0f0ff;
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

/* ══ Header ════════════════════════════════════════════════════════════════ */
QWidget#header {
    background-color: #0a0a14;
}
QLabel#appTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#appSubtitle {
    color: #3d3d6b;
    font-size: 11px;
    letter-spacing: 0.3px;
}

/* ══ Cards ═════════════════════════════════════════════════════════════════ */
QFrame#card {
    background-color: #12121e;
    border-radius: 16px;
    border: 1px solid #ffffff0d;
}
QFrame#liveCard {
    background-color: #12121e;
    border-radius: 16px;
    border: 1px solid #6c63ff40;
}
QFrame#successCard {
    background-color: #0e1e1a;
    border-radius: 16px;
    border: 1px solid #22c6a550;
}

/* ══ Drop Zone ═════════════════════════════════════════════════════════════ */
QFrame#dropZone {
    background-color: #0d0d1c;
    border-radius: 16px;
    border: 2px dashed #2a2a50;
}
QFrame#dropZoneHover {
    background-color: #12103a;
    border-radius: 16px;
    border: 2px dashed #6c63ff;
}

/* ══ Inputs ════════════════════════════════════════════════════════════════ */
QLineEdit {
    background-color: #0d0d1c;
    color: #f0f0ff;
    border: 1.5px solid #ffffff14;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: #6c63ff;
}
QLineEdit:focus {
    border-color: #6c63ff;
    background-color: #0f0f22;
}
QLineEdit:read-only {
    color: #9090c0;
    background-color: #0a0a18;
}
QLineEdit:read-only:focus {
    border-color: #ffffff14;
}

/* ══ Buttons ═══════════════════════════════════════════════════════════════ */
QPushButton#actionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6c63ff, stop:1 #8b5cf6);
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 14px 28px;
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
QPushButton#actionBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #7c73ff, stop:1 #9b6cf6);
}
QPushButton#actionBtn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5c53ef, stop:1 #7b4ce6);
}
QPushButton#actionBtn:disabled {
    background: #1e1e30;
    color: #3a3a60;
}

QPushButton#stopBtn {
    background-color: #1e1224;
    color: #e060a0;
    border: 1.5px solid #e060a040;
    border-radius: 12px;
    padding: 12px 28px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#stopBtn:hover {
    background-color: #2a1530;
    border-color: #e060a0;
    color: #ff80c0;
}

QPushButton#secondaryBtn {
    background-color: #1a1a28;
    color: #8080b0;
    border: 1.5px solid #ffffff12;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover {
    border-color: #6c63ff60;
    color: #c0c0e8;
    background-color: #1e1e32;
}
QPushButton#secondaryBtn:disabled {
    color: #2e2e50;
    border-color: #1a1a28;
}

QPushButton#dangerBtn {
    background-color: #1e0f18;
    color: #f06080;
    border: 1.5px solid #f0608040;
    border-radius: 10px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#dangerBtn:hover {
    background-color: #2a1022;
    border-color: #f06080;
    color: #ff80a0;
}
QPushButton#dangerBtn:disabled {
    color: #302030;
    border-color: #1e0f18;
}

QPushButton#copyBtn {
    background-color: #1a1a28;
    color: #6c63ff;
    border: 1.5px solid #6c63ff40;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#copyBtn:hover {
    background-color: #20203a;
    border-color: #6c63ff;
}

/* ══ Labels ════════════════════════════════════════════════════════════════ */
QLabel#sectionLabel {
    color: #3d3d6b;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
QLabel#fileNameLabel {
    color: #ffffff;
    font-size: 14px;
    font-weight: 600;
}
QLabel#fileSizeLabel {
    color: #5a5a8a;
    font-size: 11px;
}
QLabel#statusLabel {
    color: #4a4a7a;
    font-size: 12px;
}
QLabel#statusOk {
    color: #22c6a5;
    font-size: 12px;
}
QLabel#statusWarn {
    color: #f59e0b;
    font-size: 12px;
}
QLabel#pctLabel {
    color: #6c63ff;
    font-size: 26px;
    font-weight: 700;
}
QLabel#liveDot {
    color: #22c6a5;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#dropIcon {
    font-size: 40px;
    background: transparent;
}
QLabel#dropHint {
    color: #3d3d6b;
    font-size: 13px;
    background: transparent;
}
QLabel#dropHintSub {
    color: #2a2a50;
    font-size: 11px;
    background: transparent;
}
QLabel#qrHint {
    color: #3d3d6b;
    font-size: 11px;
}

/* ══ Scroll ════════════════════════════════════════════════════════════════ */
QScrollArea {
    background-color: #0a0a14;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 5px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2a45;
    border-radius: 2px;
    min-height: 30px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
"""
