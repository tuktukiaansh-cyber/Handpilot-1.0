DARK_QSS = """
QMainWindow, QWidget {
    background: #0b0c10;
    color: #edf0f5;
    font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif;
}
QTabWidget::pane { border: 0; }
QTabBar::tab {
    background: #11131a;
    color: #9ea5b4;
    padding: 10px 18px;
    margin-right: 6px;
    border-radius: 10px;
    font-weight: 600;
}
QTabBar::tab:selected { background: #1a1d25; color: #ffffff; }
QFrame#Card {
    background: #12141b;
    border: 1px solid #20242d;
    border-radius: 16px;
}
QLabel#Title { font-size: 25px; font-weight: 800; color: #ffffff; }
QLabel#Subtitle { color: #9299a8; font-size: 12px; }
QLabel#Section { font-size: 12px; font-weight: 700; color: #858d9d; letter-spacing: 1px; }
QLabel#GestureValue { font-size: 31px; font-weight: 850; color: #74edb3; }
QLabel#MetricValue { font-size: 21px; font-weight: 750; color: #ffffff; }
QLabel#StatusGood { color: #74edb3; font-weight: 700; }
QLabel#StatusWarn { color: #ff8d9b; font-weight: 700; }
QPushButton {
    background: #1a1d25;
    border: 1px solid #292e39;
    color: #f4f6fa;
    border-radius: 11px;
    padding: 9px 14px;
    font-weight: 700;
}
QPushButton:hover { background: #222631; }
QPushButton:checked { background: #193b2d; border-color: #2f7654; color: #8af3be; }
QPushButton#Primary { background: #1f4b3a; border-color: #31795a; }
QPushButton#Danger { background: #3a1d24; border-color: #6d3444; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0e1015;
    border: 1px solid #272c37;
    border-radius: 9px;
    padding: 7px 9px;
    color: #f0f2f7;
}
QComboBox QAbstractItemView { background: #141720; color: #ffffff; selection-background-color: #2a3140; }
QTableWidget {
    background: #0f1117;
    alternate-background-color: #12141b;
    border: 1px solid #20242d;
    border-radius: 12px;
    gridline-color: #20242d;
}
QHeaderView::section {
    background: #151821;
    color: #9ba3b3;
    border: 0;
    padding: 9px;
    font-weight: 700;
}
QProgressBar {
    background: #0d0f14;
    border: 1px solid #20242d;
    border-radius: 8px;
    text-align: center;
    color: #ffffff;
}
QProgressBar::chunk { background: #3c9b70; border-radius: 7px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
"""
