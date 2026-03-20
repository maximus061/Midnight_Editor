import sys
import os
import json
import urllib.request
import urllib.error
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, 
                             QFileDialog, QMessageBox, QSplitter, 
                             QTreeView, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit, 
                             QLineEdit, QColorDialog, QInputDialog, QTabWidget,
                             QPushButton, QLabel, QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtGui import (QAction, QFileSystemModel, QSyntaxHighlighter, 
                         QTextCharFormat, QColor, QFont, QPainter)
from PyQt6.QtCore import Qt, QDir, QRect, QSize, QProcess, QRegularExpression, QThread, pyqtSignal

# ─────────────────────────────────────────────
# CONFIG — LM Studio endpoint 
# ─────────────────────────────────────────────
LM_STUDIO_URL   = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "model-identifier"
LM_STUDIO_KEY   = ""


# --- AI WORKER (runs request off the main thread) ---
class AIWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred  = pyqtSignal(str)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        payload = json.dumps({
            "model": LM_STUDIO_MODEL,
            "messages": self.messages,
            "temperature": 0.7,
            "stream": False,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if LM_STUDIO_KEY:
            headers["Authorization"] = f"Bearer {LM_STUDIO_KEY}"

        req = urllib.request.Request(
            LM_STUDIO_URL,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                self.response_ready.emit(text)
        except urllib.error.URLError as e:
            self.error_occurred.emit(f"Connection error: {e.reason}")
        except Exception as e:
            self.error_occurred.emit(str(e))


# --- CHAT BUBBLE ---
class ChatBubble(QFrame):
    def __init__(self, text, role):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        label = QLabel()
        label.setText("You" if role == "user" else "AI")
        label.setStyleSheet(f"color: {'#569cd6' if role == 'user' else '#4ec9b0'}; font-size: 10px; font-weight: bold;")
        layout.addWidget(label)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet("color: #dcdcdc; font-size: 12px; line-height: 1.4;")
        layout.addWidget(body)

        if role == "user":
            self.setStyleSheet("QFrame { background-color: #0d1117; border-left: 2px solid #569cd6; border-radius: 4px; }")
        else:
            self.setStyleSheet("QFrame { background-color: #05071a; border-left: 2px solid #4ec9b0; border-radius: 4px; }")


# --- AI CHAT PANEL ---
class AIChatPanel(QWidget):
    def __init__(self, get_editor_content):
        super().__init__()
        self.get_editor_content = get_editor_content  # callable → current editor text
        self.history = []  # list of {"role": ..., "content": ...}
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QLabel("  ✦ AI Assistant")
        header.setFixedHeight(36)
        header.setStyleSheet("""
            background-color: #05071a;
            color: #569cd6;
            font-size: 12px;
            font-weight: bold;
            border-bottom: 1px solid #1a1b26;
        """)
        root.addWidget(header)

        # Scroll area for bubbles
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.bubble_container = QWidget()
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(8, 8, 8, 8)
        self.bubble_layout.setSpacing(8)
        self.bubble_layout.addStretch()
        self.scroll.setWidget(self.bubble_container)
        root.addWidget(self.scroll, stretch=1)

        # "Send context" button row
        ctx_row = QHBoxLayout()
        ctx_row.setContentsMargins(8, 4, 8, 0)
        self.ctx_btn = QPushButton("⊞ Include current file")
        self.ctx_btn.setCheckable(True)
        self.ctx_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #5a5a5a;
                border: 1px solid #1a1b26; border-radius: 3px;
                padding: 3px 8px; font-size: 11px;
            }
            QPushButton:checked { color: #4ec9b0; border-color: #4ec9b0; }
            QPushButton:hover   { color: #858585; }
        """)
        ctx_row.addWidget(self.ctx_btn)
        ctx_row.addStretch()

        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #5a5a5a;
                border: none; font-size: 11px;
            }
            QPushButton:hover { color: #cc4444; }
        """)
        self.clear_btn.clicked.connect(self.clear_chat)
        ctx_row.addWidget(self.clear_btn)
        root.addLayout(ctx_row)

        # Input row
        input_row = QHBoxLayout()
        input_row.setContentsMargins(8, 4, 8, 8)
        input_row.setSpacing(6)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Ask anything…")
        self.input.setFixedHeight(64)
        self.input.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1117;
                color: #dcdcdc;
                border: 1px solid #1a1b26;
                border-radius: 4px;
                padding: 6px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        # Ctrl+Enter to send
        self.input.installEventFilter(self)
        input_row.addWidget(self.input)

        self.send_btn = QPushButton("↑")
        self.send_btn.setFixedSize(32, 64)
        self.send_btn.setToolTip("Send (Ctrl+Enter)")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a1b26;
                color: #569cd6;
                border: 1px solid #1a1b26;
                border-radius: 4px;
                font-size: 18px;
            }
            QPushButton:hover    { background-color: #252637; }
            QPushButton:disabled { color: #3a3a4a; }
        """)
        self.send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.send_btn)

        root.addLayout(input_row)

        # Status
        self.status = QLabel("")
        self.status.setStyleSheet("color: #5a5a5a; font-size: 10px; padding: 0 8px 4px 8px;")
        root.addWidget(self.status)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def _add_bubble(self, text, role):
        bubble = ChatBubble(text, role)
        # Insert before the trailing stretch (last item)
        self.bubble_layout.insertWidget(self.bubble_layout.count() - 1, bubble)
        # Scroll to bottom
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def send_message(self):
        text = self.input.toPlainText().strip()
        if not text or self.worker is not None:
            return

        self.input.clear()
        self._add_bubble(text, "user")

        # Build message list
        messages = list(self.history)

        # Optionally prepend file context as system message
        if self.ctx_btn.isChecked():
            code = self.get_editor_content()
            if code:
                messages = [{"role": "system",
                             "content": f"The user is editing the following code. Use it as context when answering.\n\n```\n{code}\n```"}] + messages

        messages.append({"role": "user", "content": text})

        self.history.append({"role": "user", "content": text})
        self.send_btn.setEnabled(False)
        self.status.setText("⏳ Thinking…")

        self.worker = AIWorker(messages)
        self.worker.response_ready.connect(self._on_response)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._on_worker_done)
        self.worker.start()

    def _on_response(self, text):
        self._add_bubble(text, "assistant")
        self.history.append({"role": "assistant", "content": text})
        self.status.setText("")

    def _on_error(self, msg):
        self._add_bubble(f"⚠ {msg}", "assistant")
        self.status.setText("")

    def _on_worker_done(self):
        self.worker = None
        self.send_btn.setEnabled(True)

    def clear_chat(self):
        self.history.clear()
        # Remove all bubbles (keep the trailing stretch)
        while self.bubble_layout.count() > 1:
            item = self.bubble_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


# --- 1. DYNAMIC HIGHLIGHTER ---
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, lexicon):
        super().__init__(parent)
        self.lexicon = lexicon
        self.rules = []
        self.update_rules()

    def update_rules(self):
        self.rules = []
        for category, (words, color) in self.lexicon.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if category == "keywords": 
                fmt.setFontWeight(QFont.Weight.Bold)
            for word in words:
                pattern = QRegularExpression(fr"\b{word}\b")
                self.rules.append((pattern, fmt))
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


# --- 2. CODE EDITOR ---
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
    def sizeHint(self): return QSize(self.code_editor.line_number_area_width(), 0)
    def paintEvent(self, event): self.code_editor.line_number_area_paint_event(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, file_path=None):
        super().__init__()
        self.file_path = file_path
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)

    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 25 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy: self.line_number_area.scroll(0, dy)
        else: self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#05071a"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#5a5a5a"))
                painter.drawText(0, top, self.line_number_area.width() - 5, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(block_number + 1))
            block, top = block.next(), bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1


# --- 3. MAIN APP ---
class SimpleNotepad(QMainWindow):
    def __init__(self):
        super().__init__()
        self.lexicon = {
            "keywords": (["class", "def", "self", "import", "from", "return", "if", "else"], "#569cd6"),
            "types": (["int", "str", "float", "list", "dict", "bool"], "#4ec9b0"),
            "custom": ([], "#dcdcaa")
        }
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Midnight Editor")
        self.resize(1400, 800)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #02030f; }
            QPlainTextEdit, QTextEdit, QLineEdit { 
                background-color: #02030f; color: #dcdcdc; border: none;
                font-family: 'Consolas', monospace; font-size: 13px;
            }
            QTabWidget::pane { border: none; border-left: 1px solid #1a1b26; }
            QTabBar::tab { background: #05071a; color: #858585; padding: 8px 15px; border: 1px solid #1a1b26; border-bottom: none; }
            QTabBar::tab:selected { background: #02030f; color: #dcdcdc; border-bottom: 2px solid #569cd6; }
            QTreeView { background-color: #02030f; color: #858585; border: none; padding: 5px; }
            QMenuBar { background-color: #02030f; color: #dcdcdc; }
            QMenuBar::item:selected { background-color: #1a1b26; }
            QMenu { background-color: #02030f; color: #dcdcdc; border: 1px solid #1a1b26; }
            QSplitter::handle { background-color: #1a1b26; }
            QLineEdit { border-top: 1px solid #1a1b26; color: #4ec9b0; padding: 4px; }
            QScrollBar:vertical { background: #02030f; width: 6px; }
            QScrollBar::handle:vertical { background: #1a1b26; border-radius: 3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        # ── Outer horizontal splitter: [editor side | AI panel] ──
        self.outer_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: vertical splitter with explorer+tabs on top, terminal below
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.top_splitter  = QSplitter(Qt.Orientation.Horizontal)

        # Explorer
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.rootPath())
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(QDir.currentPath()))
        for i in range(1, 4): self.tree.setColumnHidden(i, True)
        self.tree.header().hide()
        self.tree.doubleClicked.connect(self.on_explorer_double_click)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Terminal
        self.terminal_container = QWidget()
        term_layout = QVBoxLayout(self.terminal_container)
        term_layout.setContentsMargins(0, 0, 0, 0)
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("Terminal...")
        self.terminal_input.returnPressed.connect(self.execute_command)
        term_layout.addWidget(self.terminal_output)
        term_layout.addWidget(self.terminal_input)

        self.top_splitter.addWidget(self.tree)
        self.top_splitter.addWidget(self.tabs)
        self.top_splitter.setStretchFactor(1, 4)

        self.main_splitter.addWidget(self.top_splitter)
        self.main_splitter.addWidget(self.terminal_container)
        self.main_splitter.setSizes([600, 200])

        # AI Panel
        self.ai_panel = AIChatPanel(self.get_current_editor_content)
        self.ai_panel.setMinimumWidth(260)

        self.outer_splitter.addWidget(self.main_splitter)
        self.outer_splitter.addWidget(self.ai_panel)
        self.outer_splitter.setSizes([1000, 340])
        self.outer_splitter.setStretchFactor(0, 1)

        self.setCentralWidget(self.outer_splitter)
        self.create_actions()

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.start("cmd.exe" if os.name == 'nt' else "bash")

    def get_current_editor_content(self):
        editor = self.tabs.currentWidget()
        return editor.toPlainText() if editor else ""

    def create_actions(self):
        menu = self.menuBar()

        # File Menu
        file_m = menu.addMenu("&File")
        self.add_action(file_m, "New Tab",               "Ctrl+N",       self.add_new_tab)
        self.add_action(file_m, "Open File...",           "Ctrl+O",       self.open_file_dialog)
        self.add_action(file_m, "Open Folder (Project)...", "Ctrl+Shift+O", self.open_folder_dialog)
        self.add_action(file_m, "Save Current",          "Ctrl+S",       self.save_current_file)

        # View Menu
        view_m = menu.addMenu("&View")
        self.add_action(view_m, "Toggle Explorer",  "Ctrl+E",  lambda: self.tree.setVisible(not self.tree.isVisible()))
        self.add_action(view_m, "Toggle Terminal",  "Ctrl+T",  lambda: self.terminal_container.setVisible(not self.terminal_container.isVisible()))
        self.add_action(view_m, "Toggle AI Panel",  "Ctrl+I",  lambda: self.ai_panel.setVisible(not self.ai_panel.isVisible()))
        self.add_action(view_m, "Fullscreen",       "F11",     lambda: self.showFullScreen() if not self.isFullScreen() else self.showNormal())

        # Lexicon Menu
        lex_m = menu.addMenu("&Lexicon")
        lex_m.addAction("Add Custom Word",    self.add_custom_word)
        lex_m.addAction("Edit Category Color", self.pick_color)

        # AI Menu
        ai_m = menu.addMenu("&AI")
        self.add_action(ai_m, "Configure Endpoint...", "", self.configure_endpoint)

    def add_action(self, menu, text, shortcut, slot):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)

    def configure_endpoint(self):
        global LM_STUDIO_URL, LM_STUDIO_MODEL, LM_STUDIO_KEY
        url, ok = QInputDialog.getText(self, "AI Endpoint", "LM Studio URL:", text=LM_STUDIO_URL)
        if ok and url:
            LM_STUDIO_URL = url
        model, ok2 = QInputDialog.getText(self, "AI Model", "Model identifier:", text=LM_STUDIO_MODEL)
        if ok2 and model:
            LM_STUDIO_MODEL = model
        key, ok3 = QInputDialog.getText(self, "API Key", "Bearer token (leave blank for none):",
                                        QLineEdit.EchoMode.Password, LM_STUDIO_KEY)
        if ok3:
            LM_STUDIO_KEY = key.strip()

    def add_new_tab(self, file_path=None, content=""):
        if file_path:
            for i in range(self.tabs.count()):
                if self.tabs.widget(i).file_path == file_path:
                    self.tabs.setCurrentIndex(i)
                    return

        editor = CodeEditor(file_path)
        editor.setPlainText(content)
        highlighter = PythonHighlighter(editor.document(), self.lexicon)
        editor.highlighter = highlighter

        title = os.path.basename(file_path) if file_path else "Untitled"
        index = self.tabs.addTab(editor, title)
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.tabs.widget(0).clear()
            self.tabs.setTabText(0, "Untitled")
            self.tabs.widget(0).file_path = None

    def on_explorer_double_click(self, index):
        path = self.model.filePath(index)
        if not self.model.isDir(index):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.add_new_tab(path, f.read())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open: {e}")

    def open_file_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Open File")
        if p:
            with open(p, 'r', encoding='utf-8') as f:
                self.add_new_tab(p, f.read())

    def open_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.tree.setRootIndex(self.model.index(folder))

    def save_current_file(self):
        editor = self.tabs.currentWidget()
        if not editor: return

        path = editor.file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save File")
            if not path: return
            editor.file_path = path
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))

        with open(path, 'w', encoding='utf-8') as f:
            f.write(editor.toPlainText())

    def pick_color(self):
        cat, ok = QInputDialog.getItem(self, "Category", "Select Category:", ["keywords", "types", "custom"], 0, False)
        if ok:
            color = QColorDialog.getColor()
            if color.isValid():
                words, _ = self.lexicon[cat]
                self.lexicon[cat] = (words, color.name())
                for i in range(self.tabs.count()):
                    self.tabs.widget(i).highlighter.update_rules()

    def add_custom_word(self):
        word, ok = QInputDialog.getText(self, "Highlight", "Word:")
        if ok and word:
            self.lexicon["custom"][0].append(word)
            for i in range(self.tabs.count()):
                self.tabs.widget(i).highlighter.update_rules()

    def execute_command(self):
        cmd = self.terminal_input.text().strip()
        if cmd.lower() in ["cls", "clear"]:
            self.terminal_output.clear()
        else:
            self.process.write((cmd + "\n").encode())
        self.terminal_input.clear()

    def read_output(self):
        self.terminal_output.insertPlainText(self.process.readAllStandardOutput().data().decode())
        self.terminal_output.ensureCursorVisible()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleNotepad()
    window.show()
    sys.exit(app.exec())
