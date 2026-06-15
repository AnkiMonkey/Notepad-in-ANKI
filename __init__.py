import os
from aqt import gui_hooks, mw
from aqt.qt import QWidget, QTextEdit, QVBoxLayout, QHBoxLayout, QLabel, QDockWidget, Qt, QPixmap
from PyQt6.QtGui import QFont

dock = None
text_box = None


def create_deep_notes_dock():
    global dock, text_box

    if dock:
        return

    parent = mw.app.activeWindow()

    dock = QDockWidget("", parent)
    dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
    )
    dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

    title_bar = QWidget()
    title_bar.setMaximumHeight(0)
    dock.setTitleBarWidget(title_bar)

    dock.setMinimumWidth(400)
    dock.setMinimumHeight(400)

    container = QWidget()
    layout = QVBoxLayout()

    # Header row: text + logo side by side
    header_row = QHBoxLayout()

    header_text = QLabel("Deep Notes by")
    header_text.setStyleSheet("font-size: 16px; font-weight: bold;")

    logo_label = QLabel()
    addon_dir = os.path.dirname(__file__)
    pixmap = QPixmap(os.path.join(addon_dir, "logo.png"))
    scaled = pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation)
    logo_label.setPixmap(scaled)

    header_row.addWidget(header_text)
    header_row.addWidget(logo_label)
    header_row.addStretch()

    subtitle = QLabel("Temporary scratchpad (clears after answer)")
    subtitle.setStyleSheet("font-size: 12px; color: gray;")

    text_box = QTextEdit()
    text_box.setFont(QFont("Arial", 18))
    text_box.setPlaceholderText("Write thoughts, reasoning, hypotheses...")

    layout.addLayout(header_row)
    layout.addWidget(subtitle)
    layout.addWidget(text_box)

    container.setLayout(layout)
    dock.setWidget(container)

    mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)


def on_show_question(card):
    create_deep_notes_dock()


def clear_notes(reviewer, card, ease):
    global text_box
    if text_box:
        text_box.clear()
        text_box.setPlaceholderText("Cleared ✓")


gui_hooks.reviewer_did_show_question.append(on_show_question)
gui_hooks.reviewer_did_answer_card.append(clear_notes)