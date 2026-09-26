import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLineEdit, QToolBar,
    QHBoxLayout, QPushButton, QLabel, QTabWidget, QTabBar, QStyleOptionTab, QStyle,
    QSizePolicy, QDockWidget, QFileDialog, QSlider,QToolButton, QMenu, QTextEdit
)
from PyQt6.QtGui import QAction, QIcon, QPainter, QFontDatabase, QPixmap
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage
from PyQt6.QtCore import QUrl, QSize, Qt, QRect, QSettings
from pathlib import Path
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from mutagen.id3 import ID3, APIC, TIT2, TPE1

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--log-level=3 --enable-gpu-rasterization --ignore-gpu-blacklist"

ICON_DIR = Path(__file__).resolve().parent

handle_path = os.path.join(ICON_DIR, "VolumeSlider2.png").replace("\\", "/")

def icon(name):
    return QIcon(os.path.join(ICON_DIR, name))


btn_style = """
    QPushButton {
        background-color: transparent;
        color: white;
        border: none;
        width: 45px;
        height: 36px;
        font-size: 18px;
    }
    QPushButton:hover {
        background-color: #4b5c70;
    }
"""
class VerticalTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)

    def tabSizeHint(self, index):
        return QSize(120, 34)

    def paintEvent(self, event):
        painter = QPainter(self)
        for i in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, i)
            self.style().drawControl(QStyle.ControlElement.CE_TabBarTabShape, option, painter, self)

            tab_rect = self.tabRect(i)

            text_rect = tab_rect.adjusted(8, 0, 0, 0)
            close_btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if close_btn is not None:
                margin = 6
                text_rect = text_rect.adjusted(0, 0, -(close_btn.width() + 2 * margin), 0)

            tab_icon = self.tabIcon(i)
            if not tab_icon.isNull():
                icon_size = self.iconSize()
                if not icon_size.isValid() or icon_size.width() <= 0:
                    icon_size = QSize(16, 16)
                icon_rect = QRect(
                    text_rect.left(),
                    tab_rect.top() + (tab_rect.height() - icon_size.height()) // 2,
                    icon_size.width(),
                    icon_size.height(),
                )
                tab_icon.paint(painter, icon_rect)
                text_rect = text_rect.adjusted(icon_size.width() + 6, 0, 0, 0)

            painter.save()
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.tabText(i))
            painter.restore()

        self._reposition_close_buttons()

    def _reposition_close_buttons(self):
        for i in range(self.count()):
            close_btn = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if close_btn is None:
                continue
            tab_rect = self.tabRect(i)
            margin = 6
            btn_x = tab_rect.right() - close_btn.width() - margin
            btn_y = tab_rect.top() + (tab_rect.height() - close_btn.height()) // 2
            close_btn.move(btn_x, btn_y)


class MP3PlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.player = QMediaPlayer(self)

        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #64778d;")
        self.playlist = []
        self.current_index = 0

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(150, 150)
        self.cover_label.setStyleSheet("color: black; background-color: #cbdbfc;")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setText("cover")

        self.song_label = QLabel("No song loaded")
        self.artist_label = QLabel("")
        self.song_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold; background-color: transparent;")
        self.artist_label.setStyleSheet("color: #cbdbfc; font-size: 13px; background-color: transparent;")
        self.song_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.song_label.setWordWrap(True)
        self.song_label.setMaximumWidth(380)
        self.song_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        

        self.open_btn = QPushButton(" Open folder ")
        self.open_btn.setStyleSheet(btn_style)
        self.open_btn.setFixedWidth(100)
        self.open_btn.clicked.connect(self.open_folder)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(icon("Pause_Button.png"))
        self.play_btn.setIconSize(QSize(32, 32))
        self.play_btn.setStyleSheet(btn_style)
        self.play_btn.clicked.connect(self.toggle_play)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(icon("Fast_Forward.png"))
        self.next_btn.setIconSize(QSize(32, 32))
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.clicked.connect(self.next_track)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.audio_output.setVolume(0.5)
        self.volume_slider.valueChanged.connect(
        lambda v: self.audio_output.setVolume(v / 100)
        )

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 100)
        self.time_slider.setValue(50)
        self.player.durationChanged.connect(self.update_seek_range)
        self.player.positionChanged.connect(self.update_seek_position)
        self.time_slider.sliderMoved.connect(self.seek_to_position)

        self.time_slider.setStyleSheet(f"""
             QSlider {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                background-color: #4b5c70;
                height: 6px;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                image: url({handle_path});
                width: 18px;
                height: 18px;
                margin: -5px 0;
           }}
        
        
            QSlider::sub-page:horizontal {{
                background-color: #9fabc4;
                height: 6px;
                border-radius: 3px;
            }}
        """)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(icon("Fast_Backwards.png"))
        self.prev_btn.setIconSize(QSize(32, 32))
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.clicked.connect(self.prev_track)

        self.player.playbackStateChanged.connect(self.update_play_icon)
        self.player.mediaStatusChanged.connect(self.AUTO_next)

        controls_row = QHBoxLayout()
        controls_row.addWidget(self.prev_btn)
        controls_row.addWidget(self.play_btn)
        controls_row.addWidget(self.next_btn)
        self.time_label = QLabel("0:00 / 0:00")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.addStretch()
        layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)
        layout.addWidget(self.song_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.time_slider)
        layout.addLayout(controls_row)
        layout.addWidget(self.open_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.volume_slider)
        layout.addStretch()

        self.volume_slider.setStyleSheet(f"""
     QSlider {{
        background: transparent;
    }}
    QSlider::groove:horizontal {{
        background-color: #4b5c70;
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        image: url({handle_path});
        width: 18px;
        height: 18px;
        margin: -5px 0;
   }}


    QSlider::sub-page:horizontal {{
        background-color: #9fabc4;
        height: 6px;
        border-radius: 3px;
    }}
""")

    def load_track(self, path):
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

        self.song_label.setText(os.path.splitext(os.path.basename(path))[0])

        cover_data = get_cover_bytes(path)
        if cover_data:
            pixmap = QPixmap()
            pixmap.loadFromData(cover_data)
            self.cover_label.setPixmap(
                pixmap.scaled(
                    150, 150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.cover_label.setText("cover")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()


    def update_seek_range(self, duration):
            self._duration = duration
            self.time_slider.setRange(0, duration)

    def seek_to_position(self, value):
            self.player.setPosition(value)


    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a music folder", "")
        if folder:
            self.playlist = [
                os.path.join(folder, f) for f in sorted(os.listdir(folder))
                if f.lower().endswith((".mp3", ".wav", ".ogg", ".flac", ".m4a"))
            ]
            if self.playlist:
                self.current_index = 0
                self.load_track(self.playlist[self.current_index])

    def next_track(self):
        if self.playlist:
            self.current_index = (self.current_index + 1) % len(self.playlist)
            self.load_track(self.playlist[self.current_index])

    def prev_track(self):
        if self.playlist:
            self.current_index = (self.current_index - 1) % len(self.playlist)
            self.load_track(self.playlist[self.current_index])

    def update_play_icon(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setIcon(icon("Pause_Button.png"))
        else:
            self.play_btn.setIcon(icon("Play_Button.png"))

    def AUTO_next(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
          self.next_track()

    def format_time(self, ms):
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def update_seek_position(self, position):
        self.time_slider.setValue(position)
        current_str = self.format_time(position)
        total_str = self.format_time(self._duration)
        self.time_label.setText(f"{current_str} / {total_str}")

class StickyNoteWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #64778d;")

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit() 
        self.text_edit.setStyleSheet("background-color: #cbdbfc; color: black;")

        layout.addWidget(self.text_edit)
    
        
class browser(QMainWindow):
    def __init__(self):
        super().__init__()

        
        profile = QWebEngineProfile("MyBrowserProfile")
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        profile.setPersistentStoragePath("CON_DIR")

        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        font_path = os.path.join(ICON_DIR, "Jersey10-Regular.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 800, 600)

        self.setStyleSheet("""
            QWidget {
                 font-family: 'Jersey 10';
                 font-size: 18px;
                 color: #ffffff;
                 background-color: #ffffff;
             }
            QMainWindow {
                background-color: #64778d;
            }
            QToolBar {
                background-color: #64778d;
                border: none;
                padding: 5px;
                spacing: 10px;
            }
            QToolBar QToolButton {
                color: #64778d;
                background-color: #64778d;
            }
            QToolBar QToolButton:hover {
                background-color: #4b5c70;
            }
            QToolBar QToolButton:pressed {
                background-color: #3e4b59;
            }
            QLineEdit {
                border: 2px solid #cbdbfc;
                border-radius: 6px;
                padding: 4px 8px;
                background-color: #cbdbfc;
                color: #000000;
            }
            QLineEdit:focus {
                border: 4px solid #9fabc4;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar {
                background-color: #64778d;
            }
            QTabBar::tab {
                background-color: #4b5c70;
                color: white;
                padding: 6px;
                margin-bottom: 2px;
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #3e4b59;
            }
            QTabBar::tab:hover {
                background-color: #55677d;
            }
            QMenu {
                background-color: #4b5c70;
                color: white;
                border: 1px solid #3e4b59;
            }
            QMenu::item:selected {
                background-color: #3e4b59;
            }
        """)

        title_bar = QWidget()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet("background-color: #3e4b59;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 0, 10, 0)
        title_layout.setSpacing(0)

        title_label = QLabel("My Browser")
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.min_btn = QPushButton()
        self.min_btn.setIcon(icon("Minimize.png"))
        self.min_btn.setIconSize(QSize(16, 16))
        self.min_btn.setStyleSheet(btn_style)
        self.min_btn.clicked.connect(self.showMinimized)

        self.max_btn = QPushButton()
        self.max_btn.setIcon(icon("Fullscreen.png"))
        self.max_btn.setIconSize(QSize(16, 16))
        self.max_btn.setStyleSheet(btn_style)
        self.max_btn.clicked.connect(self.toggle_max_restore)

        self.close_btn = QPushButton()
        self.close_btn.setIcon(icon("Close.png"))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setStyleSheet(btn_style)
        self.close_btn.clicked.connect(self.close)

        title_layout.addWidget(self.min_btn)
        title_layout.addWidget(self.max_btn)
        title_layout.addWidget(self.close_btn)

        title_bar.mousePressEvent = self.title_mouse_press
        title_bar.mouseMoveEvent = self.title_mouse_move
        title_bar.mouseReleaseEvent = self.title_mouse_release
        title_bar.mouseDoubleClickEvent = lambda e: self.toggle_max_restore()
        self._drag_pos = None

        self.settings = QSettings("MyBrowserOrg", "MyBrowser")

        self.tabs = QTabWidget()
        self.tabs.setTabBar(VerticalTabBar())
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setIconSize(QSize(18, 18))
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(False)
        self.tabs.currentChanged.connect(self.update_urlbar_for_current_tab)
        self.tabs.tabBar().tabBarClicked.connect(self.handle_tab_clicked)

        self._plus_tab_index = self.tabs.addTab(QWidget(), "")
        self.tabs.setTabIcon(self._plus_tab_index, icon("New_Tab.png"))
        self.tabs.tabBar().setTabToolTip(self._plus_tab_index, "New Tab")

        navbar = QToolBar("NAVBAR")
        navbar.setIconSize(QSize(24, 24))
        navbar.setMovable(True)
        navbar.setFloatable(True)

        self.dock_btn = QAction(icon("Switch_Tab_Mode.png"), "Move tabs to top/side", self)
        self.dock_btn.triggered.connect(self.toggle_tab_bar_position)
        navbar.addAction(self.dock_btn)

        home_btn = QAction(icon("Home.png"), "home", self)
        home_btn.triggered.connect(self.navigate_home)
        navbar.addAction(home_btn)

        back_btn = QAction(icon("BArrow.png"), "back", self)
        back_btn.triggered.connect(lambda: self.current_browser().back())
        navbar.addAction(back_btn)

        next_btn = QAction(icon("FArrow.png"), "forward", self)
        next_btn.triggered.connect(lambda: self.current_browser().forward())
        navbar.addAction(next_btn)

        reload_btn = QAction(icon("Refresh.png"), "Reload", self)
        reload_btn.triggered.connect(lambda: self.current_browser().reload())
        navbar.addAction(reload_btn)

        self.mp3_dock = QDockWidget("MP3 Player", self)
        self.mp3_dock.setWidget(MP3PlayerWidget())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.mp3_dock)
        self.mp3_dock.hide()

        self.sticky_dock = QDockWidget("sticky note", self)
        self.sticky_dock.setWidget(StickyNoteWidget())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sticky_dock)
        self.sticky_dock.hide()

        mp3_but = QAction("", self)
        mp3_but.triggered.connect(lambda: self.mp3_dock.setVisible(not self.mp3_dock.isVisible()))
        navbar.addAction(mp3_but)

        dotmenu = QToolButton()
        dotmenu.setIcon(icon("close.png"))
        dotmenu.setIconSize(QSize(24,24))
        dotmenu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        dotmenumenu = QMenu(self)
        sticky_note = QAction(icon("note.png"), "sticky note",self)
        sticky_note.triggered.connect(lambda: self.sticky_dock.setVisible(not self.sticky_dock.isVisible()))
        dotmenumenu.addAction(sticky_note)

        dotmenu.setMenu(dotmenumenu)
        navbar.addWidget(dotmenu) 

        self.urlbar = QLineEdit()
        self.urlbar.returnPressed.connect(self.navigate_to_url)
        self.urlbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_toolbar = QToolBar("URLBAR")
        top_toolbar.addWidget(self.urlbar)
        top_toolbar.setMovable(True)
        top_toolbar.setFloatable(True)
        top_toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        inner = QMainWindow()
        inner.setWindowFlags(Qt.WindowType.Widget)
        inner.addToolBar(Qt.ToolBarArea.TopToolBarArea, navbar)
        inner.addToolBar(Qt.ToolBarArea.TopToolBarArea, top_toolbar)
        inner.setCentralWidget(self.tabs)

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(title_bar)
        main_layout.addWidget(inner)

        self.setCentralWidget(central)

        saved = self.settings.value("open_tabs", "")
        urls = json.loads(saved) if saved else []
        if urls:
            for u in urls:
                self.add_new_tab(QUrl(u), "New Tab")
        else:
            self.add_new_tab(QUrl("http://www.google.com"), "New Tab")
        self.show()

    def toggle_tab_bar_position(self):
        if self.tabs.tabPosition() == QTabWidget.TabPosition.West:
            self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        else:
            self.tabs.setTabPosition(QTabWidget.TabPosition.West)

        tab_bar = self.tabs.tabBar()
        tab_bar._reposition_close_buttons()
        tab_bar.update()

    def toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setIcon(icon("Fullscreen.png"))
        else:
            self.showMaximized()
            self.max_btn.setIcon(icon("Splitscreen.png"))

    def title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def title_mouse_move(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def title_mouse_release(self, event):
        self._drag_pos = None

    def navigate_home(self):
        self.current_browser().setUrl(QUrl("http://www.google.com"))

    def navigate_to_url(self):
        q = QUrl(self.urlbar.text())
        if q.scheme() == "":
            q.setScheme("http")
        self.current_browser().setUrl(q)

    def current_browser(self):
        return self.tabs.currentWidget()

    def update_urlbar_for_current_tab(self, index):
        if not hasattr(self, "urlbar"):
            return
        instance = self.tabs.widget(index)
        if instance is not None and hasattr(instance, "url"):
            self.urlbar.setText(instance.url().toString())

    def update_urlbar(self, qurl, instance):
        if instance == self.current_browser():
            self.urlbar.setText(qurl.toString())

    def handle_tab_clicked(self, index):
        if index == self._plus_tab_index:
            self.add_new_tab()

    def add_new_tab(self, url=None, label="New Tab"):
        if url is None:
            url = QUrl("http://www.google.com")
        new_browser = QWebEngineView()

        s = new_browser.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)

        new_browser.setUrl(url)

        idx = self.tabs.insertTab(self._plus_tab_index, new_browser, label)
        self._plus_tab_index += 1
        self.tabs.setCurrentIndex(idx)

        close_btn = QPushButton()
        close_btn.setIcon(icon("Close.png"))
        close_btn.setIconSize(QSize(18, 18))
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; border-radius: 3px; }
            QPushButton:hover { background-color: #e81123; }
        """)
        close_btn.clicked.connect(lambda checked=False, b=new_browser: self.close_tab(self.tabs.indexOf(b)))
        self.tabs.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, close_btn)

        new_browser.urlChanged.connect(
            lambda qurl, b=new_browser: self.update_urlbar(qurl, b)
        )
        new_browser.titleChanged.connect(
            lambda title, b=new_browser: self.handle_title_change(title, b)
        )

    def handle_title_change(self, title, instance):
        index = self.tabs.indexOf(instance)
        if index != -1:
            self.tabs.setTabText(index, title)

    def closeEvent(self, event):
        urls = []
        for i in range(self.tabs.count()):
            if i == self._plus_tab_index:
                continue
            w = self.tabs.widget(i)
            if hasattr(w, "url"):
                urls.append(w.url().toString())
        self.settings.setValue("open_tabs", json.dumps(urls))
        super().closeEvent(event)

     
    def close_tab(self, index):
        if self.tabs.count() <= 2 or index == self._plus_tab_index:
            return

        widget = self.tabs.widget(index)
        if widget is None:
            return

        widget.stop()
        try:
            widget.urlChanged.disconnect()
        except TypeError:
            pass
        try:
            widget.titleChanged.disconnect()
        except TypeError:
            pass

        self.tabs.removeTab(index)
        if index < self._plus_tab_index:
            self._plus_tab_index -= 1
        widget.setParent(None)
        widget.deleteLater()


def get_cover_bytes(path):
    try:
        tags = ID3(path)
        for tag in tags.values():
            if isinstance(tag, APIC):
                return tag.data
    except Exception:
        pass
    return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = browser()
    sys.exit(app.exec())