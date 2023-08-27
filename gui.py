"""
Graphical user interface for the MKDD Extender.
"""
import argparse
import atexit
import collections
import concurrent.futures
import configparser
import contextlib
import datetime
import gc
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import tempfile
import threading
import time
import traceback
import wave

from typing import Any

from PIL import Image

from PySide6 import QtCore, QtGui, QtMultimedia, QtWidgets

import ast_converter
import mkdd_extender

FONT_FAMILIES = 'Liberation Mono, FreeMono, Nimbus Mono, Consolas, Courier New'

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
tools_dir = os.path.join(script_dir, 'tools')
data_dir = os.path.join(script_dir, 'data')
placeholder_course_dir = os.path.join(data_dir, 'courses', 'dstestcircle')


def set_dark_theme(app: QtWidgets.QApplication):

    class CustomStyle(QtWidgets.QProxyStyle):

        def styleHint(self, hint, option, widget, return_data) -> int:
            if hint == QtWidgets.QStyle.SH_ToolTip_WakeUpDelay:
                if QtWidgets.QApplication.instance().property('insta_tool_tips') is not None:
                    return 150

            return super().styleHint(hint, option, widget, return_data)

    app.setStyle(CustomStyle("Fusion"))

    role_colors = []
    role_colors.append((QtGui.QPalette.Window, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.WindowText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Base, QtGui.QColor(25, 25, 25)))
    role_colors.append((QtGui.QPalette.AlternateBase, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.ToolTipBase, QtGui.QColor(40, 40, 40)))
    role_colors.append((QtGui.QPalette.ToolTipText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.PlaceholderText, QtGui.QColor(160, 160, 160)))
    role_colors.append((QtGui.QPalette.Text, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.Button, QtGui.QColor(55, 55, 55)))
    role_colors.append((QtGui.QPalette.ButtonText, QtGui.QColor(200, 200, 200)))
    role_colors.append((QtGui.QPalette.BrightText, QtCore.Qt.white))
    role_colors.append((QtGui.QPalette.Light, QtGui.QColor(65, 65, 65)))
    role_colors.append((QtGui.QPalette.Midlight, QtGui.QColor(60, 60, 60)))
    role_colors.append((QtGui.QPalette.Dark, QtGui.QColor(45, 45, 45)))
    role_colors.append((QtGui.QPalette.Mid, QtGui.QColor(50, 50, 50)))
    role_colors.append((QtGui.QPalette.Shadow, QtCore.Qt.black))
    role_colors.append((QtGui.QPalette.Highlight, QtGui.QColor(45, 140, 225)))
    role_colors.append((QtGui.QPalette.HighlightedText, QtCore.Qt.black))
    role_colors.append((QtGui.QPalette.Link, QtGui.QColor(40, 130, 220)))
    role_colors.append((QtGui.QPalette.LinkVisited, QtGui.QColor(110, 70, 150)))
    palette = QtGui.QPalette()
    for role, color in role_colors:
        palette.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(color).darker())
        palette.setColor(QtGui.QPalette.Active, role, color)
        palette.setColor(QtGui.QPalette.Inactive, role, color)
    app.setPalette(palette)

    # The application's palette doesn't seem to cover the tool tip colors.
    QtWidgets.QToolTip.setPalette(palette)

    # Further global customization for the tool tips.
    padding = app.fontMetrics().height() // 2
    app.setStyleSheet(f'QToolTip {{ padding: {padding}px; }}')


@contextlib.contextmanager
def blocked_signals(obj: QtCore.QObject):
    # QSignalBlocker may or may not be available in some versions of the different Qt bindings.
    signals_were_blocked = obj.blockSignals(True)
    try:
        yield
    finally:
        if not signals_were_blocked:
            obj.blockSignals(False)


def style_message(text: str) -> str:
    # Since it seems impossible to set a style sheet that affects the <code> and <pre> tags, the
    # style attribute will be embedded in the text. Padding doesn't seem to work either; a space in
    # inserted instead. Also, border doesn't seem to work, hence that is has not been added.
    code_style_attr = 'style="background: #555; color: #CCC"'
    text = text.replace('<code>', f'<code {code_style_attr}>&nbsp;')
    text = text.replace('</code>', '&nbsp;</code>')
    pre_style_attr = 'style="background: #555; color: #CCC"'
    text = text.replace('<pre>', f'<pre {pre_style_attr}>')

    # For convenience, also add nowrap to <b> tags here with another replace action.
    b_style_attr = 'style="white-space: nowrap;"'
    text = text.replace('<b>', f'<b {b_style_attr}>')

    return text


def human_readable_duration(sample_count: int, sample_rate: int) -> str:
    duration = round(sample_count / sample_rate * 1000)
    minutes = duration // 1000 // 60
    seconds = duration // 1000 - minutes * 60
    milliseconds = duration - (minutes * 60 + seconds) * 1000
    text = []
    if minutes:
        text.append(f'{minutes} min')
    if seconds:
        text.append(f'{seconds} s')
    if milliseconds:
        text.append(f'{milliseconds} ms')
    if not text:
        text.append('0 s')
    text.append(f'&nbsp;&nbsp;<small><small>({sample_count} samples)</small></small>')
    return ' '.join(text)


def show_message(icon_name: str,
                 title: str,
                 text: str,
                 detailed_text: str = None,
                 parent: QtWidgets.QWidget = None):
    text = style_message(text)

    message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, title, text,
                                        QtWidgets.QMessageBox.NoButton, parent)

    icon_path = os.path.join(data_dir, 'gui', f'{icon_name}.svg')
    icon = QtGui.QIcon(icon_path)
    icon_size = message_box.fontMetrics().averageCharWidth() * 6
    message_box.setIconPixmap(icon.pixmap(icon.actualSize(QtCore.QSize(icon_size, icon_size))))

    if detailed_text:
        message_box.setDetailedText(detailed_text)

        # In order to customize the detailed text, it is assumed that QTextEdit is used, and that
        # a button with the action role is present.

        font_size = round(message_box.font().pointSize() * 0.75)
        for text_edit in message_box.findChildren(QtWidgets.QTextEdit):
            text_edit.setStyleSheet(
                f'QTextEdit {{ font-family: {FONT_FAMILIES}; font-size: {font_size}pt; }}')

            # If a detailed message is present, make sure the size is sufficient to show a few
            # words per line, and several lines (e.g. stack traces).
            char_width = text_edit.fontMetrics().averageCharWidth()
            char_height = text_edit.fontMetrics().height()
            text_edit.setFixedWidth(char_width * 80)
            text_edit.setFixedHeight(char_height * min(30, len(detailed_text.split('\n')) + 2))
            text_edit.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

        buttons = message_box.buttons()
        assert len(buttons) == 1, 'Expected a single button in the message box'
        if len(buttons) == 1:
            show_details_button = buttons[0]
            show_details_button.click()
            show_details_button.setFocusPolicy(QtCore.Qt.NoFocus)
            show_details_button.hide()

            # If seems something shows the button at a later time, so hide also in the next tick.
            QtCore.QTimer.singleShot(0, show_details_button.hide)

            # Also, when the message box is brought to the front after being in the background,
            # something makes the button visible again; give a null size to ensure it doesn't come
            # back.
            show_details_button.setFixedSize(0, 0)

    message_box.addButton(QtWidgets.QPushButton('Close', message_box),
                          QtWidgets.QMessageBox.AcceptRole)

    message_box.exec()


def show_long_message(icon_name: str, title: str, text: str, parent: QtWidgets.QWidget = None):
    text = style_message(text)

    message_box = QtWidgets.QDialog(parent)
    message_box.setWindowTitle(title)
    message_box.setModal(True)

    char_width = message_box.fontMetrics().averageCharWidth()
    char_height = message_box.fontMetrics().height()

    icon_path = os.path.join(data_dir, 'gui', f'{icon_name}.svg')
    icon = QtGui.QIcon(icon_path)
    icon_size = char_width * 6
    icon_label = QtWidgets.QLabel()
    icon_label.setPixmap(icon.pixmap(icon.actualSize(QtCore.QSize(icon_size, icon_size))))
    icon_layout = QtWidgets.QVBoxLayout()
    icon_layout.addWidget(icon_label)
    icon_layout.addStretch()

    text_browser = QtWidgets.QTextBrowser()
    text_browser.setOpenExternalLinks(True)
    text_browser.setFrameShape(QtWidgets.QFrame.NoFrame)
    text_browser.viewport().setAutoFillBackground(False)
    text_browser.setText(text)
    close_button = QtWidgets.QPushButton('Close')
    close_button.clicked.connect(message_box.close)
    close_button_layout = QtWidgets.QHBoxLayout()
    close_button_layout.addStretch()
    close_button_layout.addWidget(close_button)
    main_layout = QtWidgets.QVBoxLayout()
    main_layout.addWidget(text_browser)
    main_layout.addLayout(close_button_layout)

    outer_layout = QtWidgets.QHBoxLayout(message_box)
    outer_layout.addLayout(icon_layout)
    outer_layout.addLayout(main_layout)

    message_box.setMinimumWidth(char_width * 60)
    message_box.setMinimumHeight(char_height * 40)

    message_box.exec()


def open_directory(dirpath: str):
    if mkdd_extender.windows:
        os.startfile(dirpath)  # pylint: disable=no-member
    else:
        subprocess.check_call(('open' if mkdd_extender.macos else 'xdg-open', dirpath))


class PathEdit(QtWidgets.QWidget):

    def __init__(self,
                 caption: str,
                 accept_mode: QtWidgets.QFileDialog.AcceptMode,
                 file_mode: QtWidgets.QFileDialog.FileMode,
                 name_filters: 'tuple[str]' = tuple(),
                 parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)

        self._caption = caption
        self._accept_mode = accept_mode
        self._file_mode = file_mode
        self._name_filters = name_filters

        self._last_dir = ''

        self._line_edit = QtWidgets.QLineEdit()
        self.textChanged = self._line_edit.textChanged
        browse_button = QtWidgets.QPushButton('Browse')
        browse_button.setAutoDefault(False)
        browse_button.clicked.connect(self._show_file_dialog)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._line_edit)
        layout.addWidget(browse_button)

        self._line_edit.textChanged.connect(self._update_last_dir)

    def get_path(self) -> str:
        return self._line_edit.text()

    def get_last_dir(self) -> str:
        return self._last_dir

    def set_path(self, path: str):
        self._line_edit.setText(path)

    def set_last_dir(self, last_dir: str):
        self._last_dir = last_dir

    def _show_file_dialog(self):
        path = self._line_edit.text()
        name = os.path.basename(path)
        dirpath = os.path.dirname(path) or self._last_dir or os.path.expanduser('~')
        file_dialog = QtWidgets.QFileDialog(self, self._caption, dirpath)
        file_dialog.setAcceptMode(self._accept_mode)
        file_dialog.setFileMode(self._file_mode)
        file_dialog.setNameFilters(self._name_filters)
        file_dialog.selectFile(name)
        dialog_code = file_dialog.exec_()
        if dialog_code == QtWidgets.QDialog.Accepted and file_dialog.selectedFiles():
            with blocked_signals(self._line_edit):
                # Clear to force a value change, even if wasn't really changed from the file dialog.
                self._line_edit.setText(str())
            self._line_edit.setText(file_dialog.selectedFiles()[0])

    def _update_last_dir(self, text: str):
        current_dir = os.path.dirname(text)
        if current_dir and os.path.isdir(current_dir):
            self._last_dir = current_dir


class IconWidget(QtWidgets.QLabel):

    def __init__(self, icon: QtGui.QIcon, rotation_angle: float, parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)

        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)

        self._icon = icon
        self._rotation_angle = rotation_angle

    def sizeHint(self) -> QtCore.QSize:
        size = super().sizeHint()
        return QtCore.QSize(size.height(), size.height())

    def paintEvent(self, event: QtGui.QPaintEvent):
        super().paintEvent(event)

        size = self.sizeHint()
        pixmap = self._icon.pixmap(size).transformed(QtGui.QTransform().rotate(
            self._rotation_angle))
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, size.width(), size.height(), pixmap)
        del painter


class VerticalLabel(QtWidgets.QWidget):

    def __init__(self, text: str = '', parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)
        self._text = text

    def setText(self, text: str):
        if self._text != text:
            self._text = text
            self.update()

    def minimumSizeHint(self) -> QtCore.QSize:
        font_metrics = self.fontMetrics()
        width = font_metrics.height()
        margin = round(width * 0.5)
        height = font_metrics.horizontalAdvance(self._text)
        width += margin * 2
        height += margin * 2
        return QtCore.QSize(width, height)

    def paintEvent(self, event: QtGui.QPaintEvent):
        _ = event
        painter = QtGui.QPainter(self)
        rect = self.rect()
        painter.fillRect(rect.marginsRemoved(QtCore.QMargins(0, 0, 0, 1)),
                         self.palette().base().color().darker())
        painter.translate(rect.center())
        painter.rotate(90)
        painter.translate(-rect.center())
        rect = QtCore.QRect(round((rect.width() - rect.height()) / 2), 0, rect.height(),
                            rect.height())
        painter.drawText(rect, QtCore.Qt.AlignCenter | QtCore.Qt.AlignHCenter, self._text)


class SpinnableSlider(QtWidgets.QWidget):

    value_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setContentsMargins(0, 0, 0, 0)

        self.__slider = QtWidgets.QSlider()
        self.__slider.setOrientation(QtCore.Qt.Horizontal)
        self.__slider.valueChanged.connect(self._on_value_changed)
        self.__spinbox = QtWidgets.QSpinBox()
        self.__spinbox.valueChanged.connect(self._on_value_changed)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.__slider)
        layout.addWidget(self.__spinbox)

    def set_range(self, min_value: int, max_value: int, value: int):
        self.__slider.setMinimum(min_value)
        self.__slider.setMaximum(max_value)
        self.__spinbox.setMinimum(min_value)
        self.__spinbox.setMaximum(max_value)
        self.__slider.setValue(value)
        self.__spinbox.setValue(value)

    def set_value(self, value: int):
        self.__slider.setValue(value)

    def get_value(self) -> int:
        return self.__slider.value()

    def set_read_only(self, read_only: bool):
        self.__slider.setDisabled(bool(read_only))
        self.__spinbox.setReadOnly(bool(read_only))

    def _on_value_changed(self, value: int):
        with blocked_signals(self.__slider):
            self.__slider.setValue(value)
        with blocked_signals(self.__spinbox):
            self.__spinbox.setValue(value)
        self.value_changed.emit(value)


class SelectionStyledItemDelegate(QtWidgets.QStyledItemDelegate):

    def initStyleOption(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        super().initStyleOption(option, index)

        selected = option.state & QtWidgets.QStyle.State_Selected
        if selected:
            option.backgroundBrush = option.palette.highlight().color().darker()
            option.showDecorationSelected = True
            option.state = (option.state & ~QtWidgets.QStyle.State_Selected
                            & ~QtWidgets.QStyle.State_HasFocus)


class DropWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._source_ids = tuple()
        self._overlay_widget = None

        self.setAcceptDrops(True)

    def set_sources(self, sources: 'list[QtCore.QObject]'):
        self._source_ids = tuple(id(src) for src in sources)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if id(event.source()) in self._source_ids:
            event.accept()

            self._overlay_widget = QtWidgets.QWidget(self)
            self._overlay_widget.setAutoFillBackground(True)
            palette = self._overlay_widget.palette()
            color = palette.color(QtGui.QPalette.Text)
            palette.setColor(QtGui.QPalette.Window, color)
            self._overlay_widget.setPalette(palette)
            self._overlay_widget.setVisible(True)
            rect = self.rect()
            rect.setWidth(rect.width() - 1)
            rect.setHeight(rect.height() - 1)
            self._overlay_widget.setGeometry(rect)
            if rect.width() > 2 and rect.height() > 2:
                inner_rect = QtCore.QRect(1, 1, rect.width() - 2, rect.height() - 2)
                region = QtGui.QRegion(rect).xored(QtGui.QRegion(inner_rect))
                self._overlay_widget.setMask(region)

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        _ = event

        self._overlay_widget.deleteLater()
        self._overlay_widget = None

    def dropEvent(self, event: QtGui.QDropEvent):
        event.accept()

        self._overlay_widget.deleteLater()
        self._overlay_widget = None


class DragDropTableWidget(QtWidgets.QTableWidget):

    def __init__(self, rows: int, columns: int, parent: QtWidgets.QWidget = None):
        super().__init__(rows, columns, parent=parent)

        self._rows = rows
        self._columns = columns

        self.__companion_tables = []

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

        self.itemSelectionChanged.connect(self._on_itemSelectionChanged)

    def add_companion_table(self, table: QtWidgets.QTableWidget):
        self.__companion_tables.append(table)

    def dropEvent(self, event: QtGui.QDropEvent):
        # When a drop occurs on the edge between two items, Qt may try to insert a row. This is a
        # workaround that modifies the drop position to match the center of the target item,
        # minimizing the probability of dropping over an edge. Also, dropped items are not
        # reselected in the target table, which this code addresses.
        if not event.isAccepted():
            target_model_index = self.indexAt(event.pos())
            if target_model_index.isValid():

                rect = self.visualRect(target_model_index)
                centered_pos = QtCore.QPointF(rect.x() + rect.width() / 2,
                                              rect.y() + rect.height() / 2)
                synthetic_event = QtGui.QDropEvent(centered_pos, event.dropAction(),
                                                   event.mimeData(), event.mouseButtons(),
                                                   event.keyboardModifiers(), event.type())

                # Find in the companion tables (and ourselves) the list of selected indexes, so that
                # the selection in this table can be replicated after dropping the items.
                target_indexes = []
                dropping_model_indexes = None
                for table in [self] + self.__companion_tables:
                    indexes = table.selectionModel().selectedIndexes()
                    if indexes:
                        assert dropping_model_indexes is None
                        dropping_model_indexes = indexes
                if dropping_model_indexes:
                    min_row = min(mi.row() for mi in dropping_model_indexes)
                    min_column = min(mi.column() for mi in dropping_model_indexes)
                    for mi in dropping_model_indexes:
                        row = mi.row() - min_row + target_model_index.row()
                        column = mi.column() - min_column + target_model_index.column()
                        target_indexes.append((row, column))

                super().dropEvent(synthetic_event)

                def select_later():
                    item_selection = QtCore.QItemSelection()
                    for row, column in target_indexes:
                        model_index = self.model().index(row, column)
                        item_selection.select(model_index, model_index)

                    if target_indexes:
                        self.setCurrentCell(*target_indexes[0])
                    self.selectionModel().select(item_selection,
                                                 QtCore.QItemSelectionModel.ClearAndSelect)

                QtCore.QTimer.singleShot(0, select_later)

                if synthetic_event.isAccepted():
                    event.accept()

                self._create_missing_items()

                return

        super().dropEvent(event)

    def _on_itemSelectionChanged(self):
        self._create_missing_items()

    def _on_itemChanged(self, item: QtWidgets.QTableWidgetItem):
        # The QTableWidget's drag and drop default behavior can be odd when movable rows have been
        # disabled: it may append rows when an item is dropped between two cells. In case things go
        # wrong, the number of rows will be trimmed.
        if item.row() >= self._rows:
            self.setRowCount(self._rows)
        if item.column() >= self._columns:
            self.setColumnCount(self._columns)

    def _create_missing_items(self):
        # Make sure that all cells have an item, even if it's empty. Again, this is to prevent some
        # misbehavior when attempting to move itemless cells between different tables.
        for row in range(self.rowCount()):
            for column in range(self.columnCount()):
                item = self.item(row, column)
                if item is None:
                    self.setItem(row, column, QtWidgets.QTableWidgetItem(str()))


class ASTPlayer(QtWidgets.QWidget):

    _play_icon = None
    _pause_icon = None
    _audio_tmp_dir = None

    def __init__(self, filepath: str, parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)

        self._ast_filepath = filepath
        self._wav_filepath = None

        self._media_player = None
        self._audio_output = None

        if ASTPlayer._play_icon is None:
            play_icon_path = os.path.join(data_dir, 'gui', 'play.svg')
            ASTPlayer._play_icon = QtGui.QIcon(play_icon_path)

        if ASTPlayer._pause_icon is None:
            pause_icon_path = os.path.join(data_dir, 'gui', 'pause.svg')
            ASTPlayer._pause_icon = QtGui.QIcon(pause_icon_path)

        self._play_button = QtWidgets.QPushButton(ASTPlayer._play_icon, '')
        self._play_button.setCheckable(True)
        height = self._play_button.sizeHint().height()
        self._play_button.setFixedSize(height, height)
        self._play_button.clicked.connect(self._on_play_button_clicked)

        self._timeline_slider = QtWidgets.QSlider()
        self._timeline_slider.setOrientation(QtCore.Qt.Horizontal)
        self._timeline_slider.setEnabled(False)
        self._timeline_slider.setMaximum(0)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._play_button)
        layout.addWidget(self._timeline_slider)

    def _initialize_media_player(self):
        if self._media_player is not None:
            return

        if not self._wav_filepath or not os.path.isfile(self._wav_filepath):
            error_message = None
            exception_info = None

            try:
                progress_dialog = ProgressDialog('Converting AST audio file...',
                                                 self._convert_audio_file, self)
                progress_dialog.execute_and_wait()

            except mkdd_extender.MKDDExtenderError as e:
                error_message = str(e)
            except AssertionError as e:
                error_message = str(e) or 'Assertion error.'
                exception_info = traceback.format_exc()
            except Exception as e:
                error_message = str(e)
                exception_info = traceback.format_exc()

            if error_message is not None:
                error_message = error_message or 'Unknown error.'

                icon_name = 'error'
                title = 'Error'
                text = error_message
                detailed_text = exception_info

                show_message(icon_name, title, text, detailed_text, self)

        if not self._wav_filepath or not os.path.isfile(self._wav_filepath):
            return

        self._media_player = QtMultimedia.QMediaPlayer()
        self._audio_output = QtMultimedia.QAudioOutput()
        self._audio_output.setVolume(0.5)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.setSource(QtCore.QUrl.fromLocalFile(self._wav_filepath))
        self._media_player.playbackStateChanged.connect(self._on_media_player_playbackStateChanged)
        self._media_player.seekableChanged.connect(self._on_media_player_seekableChanged)
        self._media_player.durationChanged.connect(self._on_media_player_durationChanged)
        self._media_player.positionChanged.connect(self._on_media_player_positionChanged)

        self._timeline_slider.valueChanged.connect(self._on_timeline_slider_valueChanged)

    def _convert_audio_file(self):
        if ASTPlayer._audio_tmp_dir is None:
            ASTPlayer._audio_tmp_dir = tempfile.mkdtemp(prefix=mkdd_extender.TEMP_DIR_PREFIX)
            atexit.register(shutil.rmtree, ASTPlayer._audio_tmp_dir, ignore_errors=True)

        wav_filepath = os.path.join(ASTPlayer._audio_tmp_dir, f'{hash(self._ast_filepath)}.wav')

        if not os.path.isfile(wav_filepath):
            ast_converter.convert_to_wav(self._ast_filepath, wav_filepath)

        self._wav_filepath = wav_filepath

    def _on_play_button_clicked(self, checked: bool = False):
        if checked:
            self._initialize_media_player()

            if self._media_player is not None:
                self._media_player.play()
        else:
            if self._media_player is not None:
                self._media_player.pause()

    def _on_media_player_playbackStateChanged(self, state: QtMultimedia.QMediaPlayer.PlaybackState):
        playing = state == QtMultimedia.QMediaPlayer.PlayingState

        with blocked_signals(self._play_button):
            self._play_button.setChecked(playing)

        icon = ASTPlayer._pause_icon if playing else ASTPlayer._play_icon
        self._play_button.setIcon(icon)

    def _on_media_player_seekableChanged(self, seekable: bool):
        if seekable:
            self._timeline_slider.setEnabled(True)

    def _on_media_player_durationChanged(self, duration: int):
        with blocked_signals(self._timeline_slider):
            self._timeline_slider.setMaximum(duration)
            self._timeline_slider.setPageStep(round(duration / 10))
            self._timeline_slider.setSingleStep(round(duration / 100))

    def _on_media_player_positionChanged(self, position: int):
        with blocked_signals(self._timeline_slider):
            self._timeline_slider.setValue(position)

    def _on_timeline_slider_valueChanged(self, value: int):
        with blocked_signals(self._media_player):
            self._media_player.setPosition(value)


def shutdown_executor(thread_pool_executor: concurrent.futures.ThreadPoolExecutor):
    if sys.version_info >= (3, 9):
        thread_pool_executor.shutdown(wait=False, cancel_futures=True)
    else:
        thread_pool_executor.shutdown(wait=False)
        cancel_futures(thread_pool_executor)


def cancel_futures(thread_pool_executor: concurrent.futures.ThreadPoolExecutor):
    while True:
        try:
            # pylint: disable=protected-access
            work_item = thread_pool_executor._work_queue.get_nowait()
            # pylint: enable=protected-access
        except queue.Empty:
            break
        if work_item is not None:
            work_item.future.cancel()


class InfoViewWidget(QtWidgets.QScrollArea):

    shown = QtCore.Signal()

    _images_loaded = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)

        palette = self.palette()
        palette.setBrush(self.backgroundRole(), palette.dark())
        self.setPalette(palette)
        self.setWidgetResizable(True)

        self._ast_metadata_cache = {}

        self._pending_image_filepaths_by_language = None
        self._images_loaded.connect(self._on_images_loaded)

        # Loading BTI files is somehow expensive. Once an image is loaded, it is cached using its
        # checksum as key. Very often custom tracks reuse the same images for all languages; this
        # helps greatly.
        # To avoid calculating checksums often, another cache is used to map filepaths to checksums.
        self._checksum_cache = {}
        self._pixmap_cache = {}
        self._thread_pool_executor = concurrent.futures.ThreadPoolExecutor(1)
        self._child_thread_pool_executor = concurrent.futures.ThreadPoolExecutor(4)
        self._about_to_quit = False

        def shutdown_executors():
            self._about_to_quit = True
            shutdown_executor(self._child_thread_pool_executor)
            shutdown_executor(self._thread_pool_executor)

        QtWidgets.QApplication.instance().aboutToQuit.connect(shutdown_executors)

        self.show_placeholder_message()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)

        self.shown.emit()

    def purge_caches(self):
        self._ast_metadata_cache.clear()
        self._checksum_cache.clear()
        self._pixmap_cache.clear()

    def show_placeholder_message(self):
        self._build_label('Select a custom track to view its details', QtGui.QColor(100, 100, 100))

    def show_not_valid_message(self):
        self._build_label('Unable to preview selected custom track', QtGui.QColor(170, 20, 20))

    def set_path(self, path: str):
        if os.path.isfile(path):
            self._build_label('Compressed archives cannot be previewed', QtGui.QColor(150, 130, 10))
            return

        dirpath = path

        trackinfo_filepath = None
        for rootpath, _dirnames, filenames in os.walk(dirpath):
            for filename in filenames:
                if filename == 'trackinfo.ini':
                    trackinfo_filepath = os.path.join(rootpath, 'trackinfo.ini')
                    break
            if trackinfo_filepath is not None:
                break

        trackinfo = configparser.ConfigParser()
        try:
            trackinfo.read(trackinfo_filepath)
            track_name = trackinfo['Config'].get('trackname') or ''
            author = trackinfo['Config'].get('author') or ''
            auxiliary_audio_track = trackinfo['Config'].get('auxiliary_audio_track') or ''
        except Exception:
            self.show_not_valid_message()
            return

        dirpath = os.path.dirname(trackinfo_filepath)
        parent_dirpath = os.path.dirname(dirpath)
        dirname = os.path.basename(dirpath)

        minimap_filepath = os.path.join(dirpath, 'minimap.json')
        minimap_present = os.path.isfile(minimap_filepath)
        staffghost_filepath = os.path.join(dirpath, 'staffghost.ght')
        staffghost_present = os.path.isfile(staffghost_filepath)

        IMAGE_FILENAMES = ('track_image.bti', 'track_name.bti', 'track_big_logo.bti',
                           'track_small_logo.bti')

        image_filepaths_by_language = {}
        for language in mkdd_extender.LANGUAGES:
            image_filepaths = []
            image_filepaths_by_language[language] = image_filepaths
            for image_filename in IMAGE_FILENAMES:
                image_filepaths.append(
                    os.path.join(dirpath, 'course_images', language, image_filename))

        AUDIO_FILENAMES = ('lap_music_normal.ast', 'lap_music_fast.ast')
        audio_filepaths = tuple(
            os.path.join(dirpath, audio_filename) for audio_filename in AUDIO_FILENAMES)
        audio_filepaths = tuple(audio_filepath for audio_filepath in audio_filepaths
                                if os.path.isfile(audio_filepath))

        widget = QtWidgets.QWidget()
        widget.setPalette(self.palette())  # To inherit background color from parent.
        layout = QtWidgets.QVBoxLayout(widget)

        info_box = QtWidgets.QGroupBox('Info')
        info_box.setLayout(QtWidgets.QVBoxLayout())
        info_widget = QtWidgets.QLabel()
        info_widget.setText(
            textwrap.dedent(f"""\
            <table>
            <tr><td><b>Track Name: </b> </td><td>{track_name}</td></tr>
            <tr><td><b>Author: </b> </td><td>{author}</td></tr>
            <tr><td><b>Directory Name: </b> </td><td>{dirname}</td></tr>
            <tr><td><b>Parent Directory: </b> </td><td><code>{parent_dirpath}</code></td></tr>
            <tr><td><b>Minimap Coordinates: </b> </td><td>{'Yes' if minimap_present else ''}</td></tr>
            <tr><td><b>Staff Ghost: </b> </td><td>{'Yes' if staffghost_present else ''}</td></tr>
            <tr><td><b>Auxiliary Audio Track: </b> </td><td>{auxiliary_audio_track}</td></tr>
            </table>
        """))  # noqa: E501
        info_widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        info_box.layout().addWidget(info_widget)
        layout.addWidget(info_box)

        if audio_filepaths:
            audio_box = QtWidgets.QGroupBox('Audio Tracks')
            audio_box.setLayout(QtWidgets.QFormLayout())
            for audio_filepath in audio_filepaths:
                text = 'Normal' if 'normal' in audio_filepath else 'Fast'
                label = QtWidgets.QLabel(f'<b>{text} Pace:</b>')
                ast_player = ASTPlayer(audio_filepath)
                tool_tip = self.generate_ast_file_tool_tip(audio_filepath)
                label.setToolTip(tool_tip)
                ast_player.setToolTip(tool_tip)
                audio_box.layout().addRow(label, ast_player)
            layout.addWidget(audio_box)

        image_group_boxes = QtWidgets.QWidget(self)
        image_group_boxes.setObjectName('image_group_boxes')
        image_group_boxes.setLayout(QtWidgets.QVBoxLayout())
        image_group_boxes.layout().setContentsMargins(0, 0, 0, 0)
        self._show_image_files(image_filepaths_by_language)  # May load images asynchronously.
        layout.addWidget(image_group_boxes)

        layout.addStretch()

        self.setWidget(widget)
        widget.show()

    def generate_ast_file_tool_tip(self, ast_filepath, cache=True) -> str:
        metadata = self._ast_metadata_cache.get(ast_filepath) if cache else None
        if metadata is None:
            metadata = ast_converter.get_ast_info(ast_filepath)
            if cache:
                self._ast_metadata_cache[ast_filepath] = metadata

        sample_count = metadata['sample_count']
        sample_rate = metadata['sample_rate']
        bit_depth = metadata['bit_depth']
        channel_count = metadata['channel_count']
        volume = metadata['volume']
        looped = metadata['looped']
        loop_start = metadata['loop_start']
        loop_end = metadata['loop_end']

        return textwrap.dedent(f"""\
            <table>
            <tr><td><b>Duration: </b> </td><td>{human_readable_duration(sample_count, sample_rate)}</td></tr>
            <tr><td><b>Sample Rate: </b> </td><td>{sample_rate} Hz</td></tr>
            <tr><td><b>Bit Depth: </b> </td><td>{bit_depth}</td></tr>
            <tr><td><b>Channel Count: </b> </td><td>{channel_count}</td></tr>
            <tr><td><b>Volume: </b> </td><td>{volume}</td></tr>
            <tr><td><b>Looped: </b> </td><td>{'Yes' if looped else ''}</td></tr>
            <tr><td><b>Loop Start: </b> </td><td>{human_readable_duration(loop_start, sample_rate) if looped else ''}</td></tr>
            <tr><td><b>Loop End: </b> </td><td>{human_readable_duration(loop_end, sample_rate) if looped else ''}</td></tr>
            </table>
        """)  # noqa: E501

    def _verify_image_files_ready(self, image_filepaths_by_language: 'dict[str, list[str]]'):
        for image_filepaths in image_filepaths_by_language.values():
            for image_filepath in image_filepaths:
                checksum = self._checksum_cache.get(image_filepath)
                if checksum is None:
                    return False
                pixmap = self._pixmap_cache.get(checksum)
                if pixmap is None:
                    return False
        return True

    def _show_image_files(self, image_filepaths_by_language: 'dict[str, list[str]]'):
        if not self._verify_image_files_ready(image_filepaths_by_language):
            # Cancel all pending futures to prioritize the current request.
            cancel_futures(self._thread_pool_executor)

            self._pending_image_filepaths_by_language = image_filepaths_by_language
            self._thread_pool_executor.submit(self._load_images_async, image_filepaths_by_language)
            return
        self._pending_image_filepaths_by_language = None

        # Get checksums and group them by language. Most custom tracks share the same images for all
        # the languages, so they are shown within the same box to save vertical space.
        language_checksums = {}
        for language, image_filepaths in image_filepaths_by_language.items():
            checksums = []
            for image_filepath in image_filepaths:
                checksum = self._checksum_cache[image_filepath]
                checksums.append(checksum)
            checksums = tuple(checksums)
            if checksums in language_checksums:
                language_checksums[checksums].append(language)
            else:
                language_checksums[checksums] = [language]

        # An group box is created for each language (or languages, if they share checksums).
        for checksums, languages in language_checksums.items():
            labels = []
            at_least_one_image = False

            for checksum in checksums:
                pixmap = self._pixmap_cache.get(checksum)
                if pixmap is not None and not pixmap.isNull():
                    label = QtWidgets.QLabel()
                    label.setPixmap(pixmap)
                    labels.append(label)
                    at_least_one_image = True
                else:
                    labels.append(None)

            if not at_least_one_image:
                continue

            language_box = QtWidgets.QGroupBox(f'{"/".join(languages)} Images')
            language_box.setLayout(QtWidgets.QHBoxLayout())

            assert len(labels) == 4

            for label_top, label_bottom in (labels[:2], labels[2:4]):
                if (label_top, label_bottom) == (None, None):
                    continue

                if label_top is None or label_bottom is None:
                    language_box.layout().addWidget(label_top or label_bottom)
                    continue

                double_label_widget = QtWidgets.QWidget()
                double_label_layout = QtWidgets.QVBoxLayout(double_label_widget)
                double_label_layout.setContentsMargins(0, 0, 0, 0)
                double_label_layout.addWidget(label_top)
                double_label_layout.addWidget(label_bottom)
                language_box.layout().addWidget(double_label_widget)

            language_box.layout().addStretch()

            image_group_boxes = self.findChild(QtWidgets.QWidget, 'image_group_boxes')
            if image_group_boxes is not None:
                image_group_boxes.layout().addWidget(language_box)

    def _load_images_async(self, image_filepaths_by_language: 'dict[str, list[str]]'):
        for _language, image_filepaths in image_filepaths_by_language.items():
            # The images within a given language will likely be different (different checksum),
            # which means they can be parallelized without risking loading the same image twice.
            futures = []

            for image_filepath in image_filepaths:
                futures.append(
                    self._child_thread_pool_executor.submit(self._load_image, image_filepath))

            while not self._about_to_quit:
                done, _undone = concurrent.futures.wait(futures, timeout=0.250)
                if len(futures) == len(done):
                    break

            if self._about_to_quit:
                return

        self._images_loaded.emit(image_filepaths_by_language)

    def _load_image(self, filepath: str):
        checksum = self._checksum_cache.get(filepath)
        if checksum is None:
            try:
                checksum = mkdd_extender.md5sum(filepath)
            except Exception:
                checksum = False
            self._checksum_cache[filepath] = checksum

        if checksum in self._pixmap_cache:
            return

        pixmap = QtGui.QPixmap()

        if checksum is not False:
            try:
                image = mkdd_extender.convert_bti_to_image(filepath)
                if image is not None:
                    if image.mode != 'RGBA':
                        image = image.convert('RGBA')
                    data = image.tobytes("raw", "RGBA")
                    image = QtGui.QImage(data, *image.size, QtGui.QImage.Format_RGBA8888)
                    pixmap = QtGui.QPixmap.fromImage(image)
            except Exception:
                pass

        self._pixmap_cache[checksum] = pixmap

    def _on_images_loaded(self, image_filepaths_by_language: 'dict[str, list[str]]'):
        if image_filepaths_by_language == self._pending_image_filepaths_by_language:
            self._show_image_files(image_filepaths_by_language)

    def _build_label(self, text: str, color: QtGui.QColor = None):
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignCenter)
        palette = self.palette()  # To inherit background color from parent.
        if color is not None:
            palette.setColor(label.foregroundRole(), color)
        label.setPalette(palette)
        self.setWidget(label)
        label.show()


class ProgressDialog(QtWidgets.QProgressDialog):

    def __init__(self, text: str, func: callable, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        self.setMinimum(0)
        self.setMaximum(0)
        self.setValue(0)
        self.setCancelButton(None)
        self.setLabelText(text)

        self.setWindowFlags(self.windowFlags() | QtCore.Qt.FramelessWindowHint)

        self._func = func
        self._finished = False

    def closeEvent(self, event: QtGui.QCloseEvent):
        if not self._finished:
            event.ignore()
            return
        super().closeEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if not self._finished:
            event.ignore()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        if not self._finished:
            event.ignore()
            return
        super().keyReleaseEvent(event)

    def execute_and_wait(self) -> Any:
        result = None
        exc_info = None

        def wrapped_func():
            try:
                nonlocal result
                result = self._func()
            except Exception:
                nonlocal exc_info
                exc_info = sys.exc_info()

        thread = threading.Thread(target=wrapped_func)
        thread.start()

        timer = QtCore.QTimer()
        timer.setInterval(10)

        def check_completion():
            if self._finished or not thread.is_alive():
                self._finished = True
                self.close()

        timer.timeout.connect(check_completion)
        timer.start()

        # Only if the operation takes longer than 100 ms will the progress dialog be displayed. This
        # prevents some flickering when potentially-slow operations happen to return quickly (I/O
        # responsiveness can vary dramatically between different file systems).
        thread.join(0.1)
        if thread.is_alive():
            self.exec_()
        else:
            self._finished = True
            self.close()

        timer.stop()
        thread.join()

        if exc_info is not None:
            # pylint: disable=unsubscriptable-object
            raise exc_info[1].with_traceback(exc_info[2])
            # pylint: enable=unsubscriptable-object

        return result


class SplitterChildHolder(QtWidgets.QWidget):

    def __init__(self, widget: QtWidgets.QWidget, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        self.widget = widget

        size_policy = widget.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        widget.setSizePolicy(size_policy)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

        QtCore.QTimer.singleShot(0, self._update_visibility)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)

        self._update_visibility(event.size())

    def _update_visibility(self, size: QtCore.QSize = None):
        if size is None:
            size = self.size()
        visible = size.width() > 0 and size.height() > 0
        self.widget.setVisible(visible)


class LogTable(QtWidgets.QTableWidget):

    log_message_received = QtCore.Signal(tuple)

    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)

        font_size = round(self.font().pointSize() * 0.80)
        self.setStyleSheet(
            f'QTableWidget {{ font-family: {FONT_FAMILIES}; font-size: {font_size}pt; }}')

        self.setItemDelegate(SelectionStyledItemDelegate(self))
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(('Timestamp', 'Level', 'System', 'Message'))
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionsClickable(False)
        self.horizontalHeader().setSectionsMovable(False)
        self.verticalHeader().hide()
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setWordWrap(False)

        self.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        clear_log_action = QtGui.QAction('Clear Log', self)
        clear_log_action.triggered.connect(lambda: self.setRowCount(0))
        self._clear_log_before_each_run_action = QtGui.QAction('Clear Log Before Each Run', self)
        self._clear_log_before_each_run_action.setCheckable(True)
        self._clear_log_before_each_run_action.setChecked(True)
        self._clear_log_before_each_run_action.triggered.connect(lambda: self.setRowCount(0))
        self.addAction(clear_log_action)
        self.addAction(self._clear_log_before_each_run_action)

        self.log_message_received.connect(self._on_log_handler_log_message_received,
                                          QtCore.Qt.QueuedConnection)

        log_table = self

        class LogHandler(logging.Handler):

            def emit(self, record: logging.LogRecord):
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                log_message = (timestamp, record.levelno, record.levelname.title(), record.name,
                               record.msg)
                log_table.log_message_received.emit(log_message)

        self._log_handler = LogHandler()
        mkdd_extender.log.addHandler(self._log_handler)

    def get_clear_log_before_each_run(self) -> bool:
        return self._clear_log_before_each_run_action.isChecked()

    def set_clear_log_before_each_run(self, clear_log_before_each_run: bool):
        return self._clear_log_before_each_run_action.setChecked(clear_log_before_each_run)

    def _on_log_handler_log_message_received(self, log_message: 'tuple[str, int, str, str, str]'):
        MAX_ROW_COUNT = 20000
        if self.rowCount() >= MAX_ROW_COUNT:
            self.removeRow(0)

        row = self.rowCount()
        self.insertRow(row)

        color = QtGui.QBrush()
        if log_message[1] == logging.WARNING:
            color = QtGui.QColor(239, 204, 0)
        elif log_message[1] == logging.ERROR:
            color = QtGui.QColor(215, 40, 40)
        elif log_message[1] == logging.CRITICAL:
            color = QtGui.QColor(166, 58, 199)

        for column, column_value in enumerate(
            (log_message[0], log_message[2], log_message[3], log_message[4])):
            item = QtWidgets.QTableWidgetItem(column_value)
            item.setForeground(color)
            self.setItem(row, column, item)

        scroll_bar = self.verticalScrollBar()
        QtCore.QTimer.singleShot(0, lambda: scroll_bar.setSliderPosition(scroll_bar.maximum()))


class DelayedDirectoryWatcher(QtCore.QObject):

    changed = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self._watcher = QtCore.QFileSystemWatcher(self)
        self._directory = None
        self._notification_scheduled = False

        # If the watched directory disappears, Qt's implementation won't tell about it. A cheap
        # implementation is to periodically check the existence of the watched directory. If it
        # changes, we know that it needs to be re-watched. This is a very naive approach, but it
        # should work on every known file system. A more clever approach (but less trivial) would be
        # to check the inode/file ID of the directory.
        self._exists = None
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._verify_existence)
        self._timer.start()

        self._watcher.directoryChanged.connect(self._on_watcher_directoryChanged)

    def set_directory(self, dirpath: str):
        directories = self._watcher.directories()
        if directories:
            self._watcher.removePaths(directories)

        self._directory = dirpath
        try:
            self._exists = os.path.isdir(self._directory)
        except Exception:
            self._exists = False

        if dirpath and os.path.isdir(dirpath):
            self._watcher.addPath(dirpath)

    def get_directory(self) -> str:
        return self._directory

    def _verify_existence(self):
        try:
            exists = os.path.isdir(self._directory)
        except Exception:
            exists = False

        if self._exists != exists:
            self._exists = exists

            self.set_directory(self._directory)
            self.changed.emit()

    def _notify_change(self):
        self._notification_scheduled = False
        self.changed.emit()

    def _on_watcher_directoryChanged(self, dirpath: str):
        _ = dirpath

        if self._notification_scheduled:
            return

        QtCore.QTimer.singleShot(1000, self._notify_change)
        self._notification_scheduled = True


class MKDDExtenderWindow(QtWidgets.QMainWindow):

    def __init__(self,
                 parent: QtWidgets.QWidget = None,
                 flags: QtCore.Qt.WindowFlags = QtCore.Qt.WindowFlags()):
        super().__init__(parent=parent, flags=flags)

        self._red_color = QtGui.QColor(215, 40, 40)
        self._yellow_color = QtGui.QColor(239, 204, 0)

        for _group_name, group_options in mkdd_extender.OPTIONAL_ARGUMENTS.items():
            for option_label, _option_type, _option_help in group_options:
                option_member_name = f'_{mkdd_extender.option_label_as_variable_name(option_label)}'
                setattr(self, option_member_name, None)

        organization = application = 'mkdd-extender'
        self._settings = QtCore.QSettings(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope,
                                          organization, application)

        self.resize(1100, 700)
        self.setWindowTitle(f'MKDD Extender {mkdd_extender.__version__}')
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        logo_icon_path = os.path.join(data_dir, 'gui', 'logo.svg')
        logo_icon = QtGui.QIcon(logo_icon_path)
        self.setWindowIcon(logo_icon)

        error_icon_path = os.path.join(data_dir, 'gui', 'error.svg')
        self._error_icon = QtGui.QIcon(error_icon_path)
        warning_icon_path = os.path.join(data_dir, 'gui', 'warning.svg')
        self._warning_icon = QtGui.QIcon(warning_icon_path)
        options_icon_path = os.path.join(data_dir, 'gui', 'options.svg')
        options_icon = QtGui.QIcon(options_icon_path)

        self._item_text_to_path = {}

        self._directory_watcher = DelayedDirectoryWatcher()
        self._directory_watcher.changed.connect(self._load_custom_tracks_directory)

        self._undo_history = []
        self._redo_history = []
        self._pending_undo_actions = 0

        self._pending_sync_updates = 0

        menu = self.menuBar()
        file_menu = menu.addMenu('File')
        open_configuration_directory_action = file_menu.addAction('Open Configuration Directory...')
        open_configuration_directory_action.triggered.connect(
            self._on_open_configuration_directory_action_triggered)
        file_menu.addSeparator()
        quit_action = file_menu.addAction('Quit')
        quit_action.triggered.connect(self.close)
        edit_menu = menu.addMenu('Edit')
        self._undo_action = edit_menu.addAction('Undo')
        self._undo_action.setShortcut(QtGui.QKeySequence('Ctrl+Z'))
        self._undo_action.triggered.connect(self._undo)
        self._redo_action = edit_menu.addAction('Redo')
        self._redo_action.setShortcuts(
            [QtGui.QKeySequence('Ctrl+Shift+Z'),
             QtGui.QKeySequence('Ctrl+Y')])
        self._redo_action.triggered.connect(self._redo)
        edit_menu.addSeparator()
        options_action = edit_menu.addAction('Options')
        options_action.setIcon(options_icon)
        options_action.triggered.connect(self._on_options_action_triggered)
        tools_menu = menu.addMenu('Tools')
        pack_generator_action = tools_menu.addAction('Pack Generator')
        pack_generator_action.triggered.connect(self._on_pack_generator_action_triggered)
        text_image_builder_action = tools_menu.addAction('Text Image Builder')
        text_image_builder_action.triggered.connect(self._on_text_image_builder_action_triggered)
        ast_converter_action = tools_menu.addAction('AST Converter')
        ast_converter_action.triggered.connect(self._on_ast_converter_action_triggered)
        view_menu = menu.addMenu('View')
        purge_preview_caches_action = view_menu.addAction('Purge Preview Caches')
        purge_preview_caches_action.triggered.connect(
            self._on_purge_preview_caches_action_triggered)
        shelf_menu = menu.addMenu('Shelf')
        shelf_menu.aboutToShow.connect(self._on_shelf_menu_about_to_show)
        help_menu = menu.addMenu('Help')
        instructions_action = help_menu.addAction('Instructions')
        instructions_action.triggered.connect(self._open_instructions_dialog)
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self._open_about_dialog)

        self._input_iso_file_edit = PathEdit('Select Input ISO File',
                                             QtWidgets.QFileDialog.AcceptOpen,
                                             QtWidgets.QFileDialog.ExistingFile,
                                             ('ISO (*.iso)', 'GCM (*.gcm)'))
        self._output_iso_file_edit = PathEdit('Select Output ISO File',
                                              QtWidgets.QFileDialog.AcceptSave,
                                              QtWidgets.QFileDialog.AnyFile,
                                              ('ISO (*.iso)', 'GCM (*.gcm)'))
        self._custom_tracks_directory_edit = PathEdit('Select Custom Tracks Directory',
                                                      QtWidgets.QFileDialog.AcceptOpen,
                                                      QtWidgets.QFileDialog.Directory)
        input_form_layout = QtWidgets.QFormLayout()
        input_form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        input_form_layout.addRow('Input ISO File', self._input_iso_file_edit)
        input_form_layout.addRow('Output ISO File', self._output_iso_file_edit)
        input_form_layout.addRow('Custom Tracks Directory', self._custom_tracks_directory_edit)

        self._custom_tracks_filter_edit = QtWidgets.QLineEdit()
        self._custom_tracks_filter_edit.textChanged.connect(self._update_custom_tracks_filter)
        self._custom_tracks_filter_edit.setPlaceholderText('Filter')
        clear_icon_path = os.path.join(data_dir, 'gui', 'clear.svg')
        clear_icon = QtGui.QIcon(clear_icon_path)
        self._clear_filter_action = self._custom_tracks_filter_edit.addAction(
            clear_icon, QtWidgets.QLineEdit.TrailingPosition)
        self._clear_filter_action.triggered.connect(self._custom_tracks_filter_edit.clear)
        self._clear_filter_action.setVisible(False)
        self._custom_tracks_table = QtWidgets.QTableWidget()
        self._custom_tracks_table.setItemDelegate(
            SelectionStyledItemDelegate(self._custom_tracks_table))
        self._custom_tracks_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._custom_tracks_table.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self._custom_tracks_table.setColumnCount(1)
        self._custom_tracks_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)
        self._custom_tracks_table.horizontalHeader().setSectionsMovable(False)
        # NOTE: It is important to make the table sortable before making the indicator clearable, or
        # else the label in the header would be boldified. An odd behavior in Qt that may bite back.
        self._custom_tracks_table.setSortingEnabled(True)
        self._custom_tracks_table.horizontalHeader().setSortIndicatorClearable(True)
        self._custom_tracks_table.horizontalHeader().sortIndicatorChanged.connect(
            self._on_custom_tracks_table_sortIndicatorChanged)
        self._custom_tracks_table.verticalHeader().hide()
        self._custom_tracks_table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self._custom_tracks_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self._custom_tracks_table.setWordWrap(False)
        self._custom_tracks_table_label = 'Custom Tracks'
        self._custom_tracks_table.setHorizontalHeaderLabels([self._custom_tracks_table_label])
        custom_tracks_drop_widget = DropWidget()
        custom_tracks_drop_widget_layout = QtWidgets.QVBoxLayout(custom_tracks_drop_widget)
        custom_tracks_drop_widget_layout.addWidget(self._custom_tracks_table)
        custom_tracks_drop_widget_layout.setContentsMargins(0, 0, 0, 0)
        custom_tracks_widget = QtWidgets.QWidget()
        custom_tracks_layout = QtWidgets.QVBoxLayout(custom_tracks_widget)
        custom_tracks_layout.setContentsMargins(0, 0, 0, 0)
        custom_tracks_layout.setSpacing(2)
        custom_tracks_layout.addWidget(self._custom_tracks_filter_edit)
        custom_tracks_layout.addWidget(custom_tracks_drop_widget)
        pages_widget = QtWidgets.QWidget()
        pages_layout = QtWidgets.QVBoxLayout(pages_widget)
        pages_layout.setSpacing(0)
        pages_layout.setContentsMargins(0, 0, 0, 0)

        font_height = self.fontMetrics().height()

        HEADER_LABELS = ('Mushroom Cup', 'Flower Cup', 'Star Cup', 'Special Cup')
        ROWS = 4
        COLUMNS = len(HEADER_LABELS)

        self._page_labels = []
        self._page_tables = []
        self._page_widgets = []

        for page_index in range(mkdd_extender.MAX_EXTRA_PAGES):
            page_table = DragDropTableWidget(ROWS, COLUMNS)
            page_table.setFixedHeight(round(font_height * 1.5) * (ROWS + 1))
            page_table.setItemDelegate(SelectionStyledItemDelegate(page_table))
            self._page_tables.append(page_table)
            page_table.setHorizontalHeaderLabels(HEADER_LABELS)
            if page_index == 0:
                page_table.setHorizontalHeaderLabels(HEADER_LABELS)
            else:
                page_table.setHorizontalHeaderLabels([''] * COLUMNS)
                page_table.horizontalHeader().setFixedHeight(int(font_height * 0.4))
            page_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
            page_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
            page_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            page_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            page_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            page_table.horizontalHeader().setSectionsClickable(False)
            page_table.horizontalHeader().setSectionsMovable(False)
            page_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            page_table.verticalHeader().hide()
            page_table.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
            clear_selection_action = QtGui.QAction('Clear', page_table)
            clear_selection_action.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete))
            clear_selection_action.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)
            clear_selection_action.triggered.connect(self._clear_selection)
            page_table.addAction(clear_selection_action)
            page_label = VerticalLabel()
            self._page_labels.append(page_label)
            page_widget = QtWidgets.QWidget()
            page_widget.setContentsMargins(0, 0, 0, 0)
            page_widget_layout = QtWidgets.QHBoxLayout(page_widget)
            page_widget_layout.setContentsMargins(0, 0, 0, 0)
            page_widget_layout.setSpacing(0)
            page_widget_layout.addWidget(page_table)
            page_widget_layout.addWidget(page_label)
            self._page_widgets.append(page_widget)
            pages_layout.addWidget(page_widget)
        pages_layout.addStretch(1)
        for page_table in self._page_tables:
            for other_page_table in self._page_tables:
                if page_table != other_page_table:
                    page_table.add_companion_table(other_page_table)
            page_table.add_companion_table(self._custom_tracks_table)
        custom_tracks_drop_widget.set_sources(self._page_tables)
        pages_scroll_widget = QtWidgets.QScrollArea()
        pages_scroll_widget.setWidgetResizable(True)
        pages_scroll_widget.setFrameShape(QtWidgets.QFrame.NoFrame)
        pages_scroll_widget.setWidget(pages_widget)

        self._extra_pages_count_combobox = QtWidgets.QComboBox()
        for i in range(mkdd_extender.MAX_EXTRA_PAGES):
            self._extra_pages_count_combobox.addItem(str(i + 2))
        self._update_page_visibility(1)
        self._extra_pages_count_combobox.currentIndexChanged.connect(
            self._on_extra_pages_count_combobox_currentIndexChanged)

        extra_pages_layout = QtWidgets.QHBoxLayout()
        extra_pages_layout.addStretch()
        self._total_page_count_label = QtWidgets.QLabel('Total Page Count')
        extra_pages_layout.addWidget(self._total_page_count_label)
        extra_pages_layout.addWidget(self._extra_pages_count_combobox)

        main_area_widget = QtWidgets.QWidget()
        main_area_layout = QtWidgets.QVBoxLayout(main_area_widget)
        main_area_layout.setContentsMargins(0, 0, 0, 0)
        main_area_layout.addLayout(extra_pages_layout)
        main_area_layout.addWidget(pages_scroll_widget)

        self._info_view = InfoViewWidget()
        self._info_view.shown.connect(self._update_info_view)
        self._splitter = QtWidgets.QSplitter()
        self._splitter.addWidget(SplitterChildHolder(custom_tracks_widget))
        self._splitter.addWidget(SplitterChildHolder(main_area_widget))
        self._splitter.addWidget(SplitterChildHolder(self._info_view))
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setStretchFactor(2, 2)
        self._splitter.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                     QtWidgets.QSizePolicy.Expanding)

        options_button = QtWidgets.QPushButton('Options')
        options_button.clicked.connect(self._on_options_action_triggered)
        options_button.setIcon(options_icon)
        self._options_edit = QtWidgets.QLineEdit()
        self._options_edit.setFocusPolicy(QtCore.Qt.NoFocus)
        self._options_edit.setPlaceholderText('No options set')
        self._options_edit.setReadOnly(True)
        font_size = round(self._options_edit.font().pointSize() * 0.75)
        self._options_edit.setStyleSheet(
            f'QLineEdit {{ font-family: {FONT_FAMILIES}; font-size: {font_size}pt; }}')

        options_layout = QtWidgets.QHBoxLayout()
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(0)
        options_layout.addWidget(options_button)
        options_layout.addWidget(self._options_edit)

        self._build_button = QtWidgets.QPushButton('Build')
        hpadding = self._build_button.fontMetrics().averageCharWidth()
        vpadding = self._build_button.fontMetrics().height() // 2
        self._build_button.setStyleSheet(f'QPushButton {{ padding: {vpadding}px {hpadding}px }}')
        build_icon_path = os.path.join(data_dir, 'gui', 'build.svg')
        build_icon = QtGui.QIcon(build_icon_path)
        self._build_button.setIcon(build_icon)
        self._build_button.clicked.connect(self._build)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(self._build_button)

        main_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(main_widget)
        layout.addLayout(input_form_layout)
        layout.addWidget(self._splitter)
        layout.addLayout(options_layout)
        layout.addLayout(bottom_layout)

        self._log_table = LogTable()

        self._log_splitter = QtWidgets.QSplitter()
        self._log_splitter.setOrientation(QtCore.Qt.Vertical)
        self._log_splitter.addWidget(SplitterChildHolder(main_widget))
        self._log_splitter.addWidget(SplitterChildHolder(self._log_table))
        self._log_splitter.setCollapsible(0, False)
        self._log_splitter.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                         QtWidgets.QSizePolicy.Expanding)

        self.setCentralWidget(self._log_splitter)

        self._restore_settings()

        self._input_iso_file_edit.textChanged.connect(self._initialize_output_filepath)
        self._custom_tracks_directory_edit.textChanged.connect(self._load_custom_tracks_directory)
        self._custom_tracks_table.itemSelectionChanged.connect(self._on_tables_itemSelectionChanged)
        for page_table in self._page_tables:
            page_table.itemSelectionChanged.connect(self._on_tables_itemSelectionChanged)
            page_table.itemChanged.connect(self._on_page_table_itemChanged)

        self._update_options_string()

        # Custom tracks (and indirectly emblems) to be updated in the next iteration, to guarantee
        # that the main window has been shown before showing a potential progress dialog.
        QtCore.QTimer.singleShot(0, self._load_custom_tracks_directory)

        self._pending_undo_actions = 1
        QtCore.QTimer.singleShot(0, self._process_undo_action)

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._save_settings()

        super().closeEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent):
        super().keyReleaseEvent(event)

        if not event.isAccepted():
            if event.modifiers() in (QtCore.Qt.NoModifier, QtCore.Qt.KeypadModifier):
                if event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
                    if self.hasFocus():
                        self._clear_selection()

    def _save_settings(self):
        self._settings.setValue('window/geometry', self.saveGeometry())
        self._settings.setValue('window/state', self.saveState())
        self._settings.setValue('window/splitter', self._splitter.saveState())
        self._settings.setValue('window/log_splitter', self._log_splitter.saveState())

        self._settings.setValue('miscellaneous/input_path', self._input_iso_file_edit.get_path())
        self._settings.setValue('miscellaneous/input_last_dir',
                                self._input_iso_file_edit.get_last_dir())
        self._settings.setValue('miscellaneous/output_path', self._output_iso_file_edit.get_path())
        self._settings.setValue('miscellaneous/output_last_dir',
                                self._output_iso_file_edit.get_last_dir())
        self._settings.setValue('miscellaneous/tracks_path',
                                self._custom_tracks_directory_edit.get_path())
        self._settings.setValue('miscellaneous/tracks_last_dir',
                                self._custom_tracks_directory_edit.get_last_dir())
        self._settings.setValue('miscellaneous/tracks_filter',
                                self._custom_tracks_filter_edit.text())

        custom_tracks_table_header = self._custom_tracks_table.horizontalHeader()
        sort_indicator_order = (0 if custom_tracks_table_header.sortIndicatorOrder()
                                == QtCore.Qt.AscendingOrder else 1)
        self._settings.setValue('miscellaneous/tracks_order',
                                (f'{custom_tracks_table_header.sortIndicatorSection()} '
                                 f'{sort_indicator_order}'))

        extra_page_count = self._get_configured_extra_page_count()
        page_item_values = self._get_page_item_values()[:extra_page_count * 16]
        self._settings.setValue('miscellaneous/page_item_values', json.dumps(page_item_values))

        options = []
        for _group_name, group_options in mkdd_extender.OPTIONAL_ARGUMENTS.items():
            for option_label, _option_type, _option_help in group_options:
                option_variable_name = mkdd_extender.option_label_as_variable_name(option_label)
                option_member_name = f'_{option_variable_name}'
                option_value = getattr(self, option_member_name)
                if option_value:
                    options.append((option_variable_name, option_value))
        self._settings.setValue('miscellaneous/options', json.dumps(options))

        self._settings.setValue('miscellaneous/clear_log_before_each_run',
                                self._log_table.get_clear_log_before_each_run())

    def _restore_settings(self):
        geometry = self._settings.value('window/geometry')
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value('window/state')
        if state:
            self.restoreState(state)
        state = self._settings.value('window/splitter')
        if state:
            self._splitter.restoreState(state)
        state = self._settings.value('window/log_splitter')
        if state:
            self._log_splitter.restoreState(state)

        path = self._settings.value('miscellaneous/input_path')
        if path:
            self._input_iso_file_edit.set_path(path)
        path = self._settings.value('miscellaneous/input_last_dir')
        if path:
            self._input_iso_file_edit.set_last_dir(path)

        path = self._settings.value('miscellaneous/output_path')
        if path:
            self._output_iso_file_edit.set_path(path)
        path = self._settings.value('miscellaneous/output_last_dir')
        if path:
            self._output_iso_file_edit.set_last_dir(path)

        path = self._settings.value('miscellaneous/tracks_path')
        if path:
            self._custom_tracks_directory_edit.set_path(path)
        path = self._settings.value('miscellaneous/tracks_last_dir')
        if path:
            self._custom_tracks_directory_edit.set_last_dir(path)

        text = self._settings.value('miscellaneous/tracks_filter')
        if text:
            self._custom_tracks_filter_edit.setText(text)

        text = self._settings.value('miscellaneous/tracks_order')
        if text:
            custom_tracks_table_header = self._custom_tracks_table.horizontalHeader()
            logical_index = int(text.split(' ')[0])
            if logical_index >= 0:
                order = QtCore.Qt.SortOrder(int(text.split(' ')[1]))
                custom_tracks_table_header.setSortIndicator(logical_index, order)

        page_item_values = self._settings.value('miscellaneous/page_item_values')
        if page_item_values:
            try:
                page_item_values = json.loads(page_item_values)
            except json.decoder.JSONDecodeError:
                pass
            else:
                self._set_page_item_values(page_item_values, also_selected_state=False)
                self._update_page_visibility(len(page_item_values) // 16)

        options = self._settings.value('miscellaneous/options')
        if options:
            try:
                options = json.loads(options)
            except json.decoder.JSONDecodeError:
                pass
            else:
                for option_variable_name, option_value in options:
                    option_member_name = f'_{option_variable_name}'
                    setattr(self, option_member_name, option_value)

        self._log_table.set_clear_log_before_each_run(
            self._settings.value('miscellaneous/clear_log_before_each_run', 'true') == 'true')

    def _get_shelf_items(self) -> 'tuple[tuple[str, list[tuple[int, int, int, str, bool]]]]':
        return tuple(self._settings.value('shelf/items', tuple()))

    def _create_shelf_item(self):
        dialog = QtWidgets.QDialog(self)
        dialog.deleteLater()
        dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 60)
        dialog.setWindowTitle('Create Shelf Item')
        layout = QtWidgets.QVBoxLayout(dialog)
        description_label = QtWidgets.QLabel()
        description_label.setWordWrap(True)
        description_label.setText('This tool is used to create a backup of the current mapping, '
                                  'and store it on the shelf to be checked out in the future.')
        layout.addWidget(description_label)
        layout.addSpacing(dialog.fontMetrics().height())
        name_layout = QtWidgets.QFormLayout()
        name_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        name_edit = QtWidgets.QLineEdit()
        name_edit.setText(time.strftime('%Y-%m-%d %H:%M:%S'))
        QtCore.QTimer.singleShot(0, name_edit.selectAll)
        name_layout.addRow('Shelf Item Name', name_edit)
        layout.addLayout(name_layout)
        layout.addStretch()
        layout.addSpacing(dialog.fontMetrics().height() * 2)

        def on_create_button_clicked():
            name = name_edit.text()
            shelf_items = list(self._get_shelf_items())
            extra_page_count = self._get_configured_extra_page_count()
            course_names = tuple(item[3]
                                 for item in self._get_page_item_values()[:extra_page_count * 16])
            shelf_items.append((name, course_names))
            self._settings.setValue('shelf/items', shelf_items)
            dialog.close()

        create_button = QtWidgets.QPushButton('Create')
        create_button.clicked.connect(on_create_button_clicked)

        def on_name_edit_textChanged(text: str):
            create_button.setEnabled(bool(text))

        name_edit.textChanged.connect(on_name_edit_textChanged)

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(create_button)
        layout.addLayout(bottom_layout)
        dialog.exec_()

    def _delete_shelf_item(self, index: int):
        shelf_items = list(self._get_shelf_items())
        if 0 <= index < len(shelf_items):
            messageBox = QtWidgets.QMessageBox(self)
            messageBox.setIcon(QtWidgets.QMessageBox.Question)
            messageBox.setWindowTitle('Delete Shelf Item')
            messageBox.setText(f'Delete "{shelf_items[index][0]}" item?')
            keepButton = messageBox.addButton('&Keep', QtWidgets.QMessageBox.RejectRole)
            messageBox.setEscapeButton(keepButton)
            deleteButton = messageBox.addButton('&Delete', QtWidgets.QMessageBox.DestructiveRole)
            messageBox.setDefaultButton(deleteButton)
            messageBox.exec_()
            clickedButton = messageBox.clickedButton()
            if clickedButton == deleteButton:
                del shelf_items[index]
                if shelf_items:
                    self._settings.setValue('shelf/items', shelf_items)
                else:
                    self._settings.remove('shelf/items')

    def _load_shelf_item(self, index: int):
        shelf_items = self._get_shelf_items()
        if 0 <= index < len(shelf_items):
            items = self._get_page_item_values()
            course_names = shelf_items[index][1]
            for i, course_name in enumerate(course_names):
                items[i] = list(items[i])
                items[i][3] = course_name
                items[i][4] = False
            extra_page_count = len(course_names) // 16
            self._set_page_item_values(items[:extra_page_count * 16])

            self._update_page_visibility(extra_page_count)

            self._sync_emblems()
            self._update_info_view()

            self._pending_undo_actions += 1
            self._process_undo_action()

    def _open_instructions_dialog(self):
        text = textwrap.dedent(f"""\
            <h1>Instructions</h1>
            <p><h3>1. Input ISO file</h3>
            Select the path to the retail ISO file of Mario Kart: Double Dash!!.

            <br/>
            All regions are supported.
            </p>
            <p><h3>2. Output ISO file</h3>
            Select the path to the location where the <em>extended</em> ISO file will be written.
            </p>
            <p><h3>3. Custom tracks directory</h3>
            Select the path to the directory that contains the custom tracks.
            <br/>
            <br/>
            MKDD Extender follows the custom track format that the
            <a href="https://github.com/RenolY2/mkdd-track-patcher"
               style="white-space: nowrap;">MKDD Track Patcher</a> defines.
            <br/>
            <br/>
            Custom tracks can be downloaded from the community-powered
            <a href="https://mkdd.org">Custom Mario Kart: Double Dash Wiki!!</a>.
            </p>
            <p><h3>4. Assign custom tracks</h3>
            Once the custom tracks directory has been selected, the
            <b>{self._custom_tracks_table_label}</b> list on the left-hand side will be populated.
            Drag & drop the custom tracks onto the slots on each of the course pages on the
            right-hand side.
            <br/>
            <br/>
            If any of the slots is not filled in, a placeholder will be provided.
            <br/>
            <br/>
            The number of course pages can be customized in the
            <b>{self._total_page_count_label.text()}</b> drop down (from 2 to
            {mkdd_extender.MAX_EXTRA_PAGES + 1} pages). The first page is reserved for the stock
            courses in the input ISO file; it does not appear in the list, which starts counting at
            2.
            </p>
            <p><h3>5. Build ISO file</h3>
            When ready, press the <b>{self._build_button.text()}</b> button to generate the extended
            ISO file.
            </p>
            <p><h3>6. Play</h3>
            Start the game in GameCube, Wii, or Dolphin.
            </p>
            <p><h3>7. In-game course page selection</h3>
            Use <code>D-pad Up</code> and <code>D-pad Down</code> while in the <b>SELECT COURSE</b>
            or b>SELECT CUP</b> screens to increment or decrement course page number.
            </p>
        """)
        show_long_message('info', 'Instructions', text, self)

    def _open_about_dialog(self):
        forward_slashes_script_dir = '/'.join(script_dir.split('\\'))
        if not forward_slashes_script_dir.startswith('/'):
            forward_slashes_script_dir = f'/{forward_slashes_script_dir}'
        copying_url = f'file://{forward_slashes_script_dir}/COPYING'

        updates_url = 'https://github.com/cristian64/mkdd-extender/releases'

        text = textwrap.dedent(f"""\
            <h1 style="white-space: nowrap">MKDD Extender {mkdd_extender.__version__}</h1>
            <br/>
            <small><a href="https://github.com/cristian64/mkdd-extender">
                github.com/cristian64/mkdd-extender
            </a></small>
            <br/><br/>
            {mkdd_extender.__doc__}
            <br/>
            <br/>
            <small>
            <a href="{copying_url}">License</a> | <a href="{updates_url}">Updates</a>
            </small>
        """)
        show_message('logo', 'About MKDD Extender', text, '', self)

    def _initialize_output_filepath(self, text: str):
        if not text or self._output_iso_file_edit.get_path():
            return
        root, ext = os.path.splitext(text)
        if os.path.isfile(text) and ext in ('.iso', '.gcm'):
            self._output_iso_file_edit.set_path(f'{root}_extended.iso')

    def _update_custom_tracks_filter(self):
        custom_tracks_filter = self._custom_tracks_filter_edit.text()
        self._clear_filter_action.setVisible(bool(custom_tracks_filter))

        if not self._custom_tracks_table.isEnabled():
            return

        custom_tracks_filter = custom_tracks_filter.lower()

        for row in range(self._custom_tracks_table.rowCount()):
            item = self._custom_tracks_table.item(row, 0)
            visible = custom_tracks_filter in item.text().lower()
            if visible:
                self._custom_tracks_table.showRow(row)
            else:
                self._custom_tracks_table.hideRow(row)

    def _load_custom_tracks_directory(self, dirpath: str = ''):
        selected_items_text = []
        for item in self._custom_tracks_table.selectedItems():
            selected_items_text.append(item.text())

        self._custom_tracks_table.setEnabled(False)
        self._custom_tracks_table.setRowCount(0)

        self._item_text_to_path.clear()

        dirpath = dirpath or self._custom_tracks_directory_edit.get_path()

        if self._directory_watcher.get_directory() != dirpath:
            self._directory_watcher.set_directory(dirpath)

        if dirpath:
            progress_dialog = ProgressDialog(
                'Scanning custom tracks directory...',
                lambda: mkdd_extender.scan_custom_tracks_directory(dirpath), self)
            paths_to_track_name = progress_dialog.execute_and_wait()

            if not paths_to_track_name:
                if paths_to_track_name is None:
                    label = 'Directory not accessible.'
                    color = self._red_color
                else:
                    label = 'No custom track found in directory.'
                    color = self._yellow_color
                item = QtWidgets.QTableWidgetItem(label)
                item.setForeground(color)
                self._custom_tracks_table.insertRow(0)
                self._custom_tracks_table.setItem(0, 0, item)

            else:
                self._custom_tracks_table.setRowCount(len(paths_to_track_name))
                track_names = tuple(paths_to_track_name.values())

                item_text_to_item = {}

                for i, (path, track_name) in enumerate(paths_to_track_name.items()):
                    # If the track name is not unique (e.g. different versions of the same course),
                    # the entry name is added to the text).
                    name = os.path.basename(path)
                    if track_names.count(track_name) > 1:
                        text = f'{track_name} ({name})'
                    else:
                        text = track_name
                    self._item_text_to_path[text] = path
                    item = QtWidgets.QTableWidgetItem(text)
                    item_text_to_item[text] = item
                    self._custom_tracks_table.setItem(i, 0, item)

                # Restore selection if there was one. Note that the order matters, and that we only
                # care about the last item selected signal.
                items_to_select = []
                for selected_item_text in selected_items_text:
                    item = item_text_to_item.get(selected_item_text)
                    if item is not None:
                        items_to_select.append(item)
                if items_to_select:
                    with blocked_signals(self._custom_tracks_table):
                        for item in items_to_select[:-1]:
                            item.setSelected(True)
                    items_to_select[-1].setSelected(True)

                self._custom_tracks_table.setEnabled(True)
                self._update_custom_tracks_filter()

        self._sync_emblems()
        self._update_info_view()

    @contextlib.contextmanager
    def _blocked_page_signals(self):
        signals_were_blocked_map = {}
        for page_table in self._page_tables:
            signals_were_blocked_map[page_table] = page_table.blockSignals(True)
        try:
            yield
        finally:
            for page_table, signals_were_blocked in signals_were_blocked_map.items():
                if not signals_were_blocked:
                    page_table.blockSignals(False)

    def _get_configured_extra_page_count(self):
        return sum(int(page_widget.isVisible()) for page_widget in self._page_widgets)

    def _update_page_visibility(self, extra_page_count: int):
        for page_widget in self._page_widgets[:extra_page_count]:
            page_widget.show()
        for page_widget in self._page_widgets[extra_page_count:]:
            page_widget.hide()
        for page_index, page_label in enumerate(self._page_labels):
            page_label.setText(f'{page_index + 2} / {extra_page_count + 1}')
        with blocked_signals(self._extra_pages_count_combobox):
            self._extra_pages_count_combobox.setCurrentIndex(extra_page_count - 1)

    def _on_extra_pages_count_combobox_currentIndexChanged(self, index: int):
        extra_page_count = index + 1
        items = self._get_page_item_values()
        self._set_page_item_values(items[:extra_page_count * 16])

        self._update_page_visibility(index + 1)

        self._sync_emblems()
        self._update_info_view()

        self._pending_undo_actions += 1
        self._process_undo_action()

    def _get_page_items(self) -> 'list[QtWidgets.QTableWidgetItem]':
        items = []
        for page_table in self._page_tables:
            for column in range(page_table.columnCount()):
                for row in range(page_table.rowCount()):
                    item = page_table.item(row, column)
                    if item is not None:
                        items.append(item)
        return items

    def _get_page_item_values(self) -> 'list[tuple[int, int, int, str, bool]]':
        page_item_values = []
        for i, page_table in enumerate(self._page_tables):
            page_table_model = page_table.model()
            selected_indexes = page_table.selectedIndexes()
            for column in range(page_table.columnCount()):
                for row in range(page_table.rowCount()):
                    item = page_table.item(row, column)
                    value = item.text() if item is not None else ''
                    selected = page_table_model.createIndex(row, column) in selected_indexes
                    page_item_values.append((i, column, row, value, selected))
        return page_item_values

    def _set_page_item_values(self,
                              page_item_values: 'list[tuple[int, int, int, str]]',
                              also_selected_state: bool = True):
        assert len(page_item_values) % 16 == 0

        # Pad the values with an empty version of the expected tuple.
        reference_item_values = self._get_page_item_values()
        if len(reference_item_values) != len(page_item_values):
            page_item_values = list(page_item_values)
            for _ in range(len(page_item_values)):
                reference_item_values.pop(0)
            for i, column, row, _value, _selected in reference_item_values:
                page_item_values.append((i, column, row, '', False))

        with self._blocked_page_signals():
            if also_selected_state:
                for page_table in self._page_tables:
                    page_table.clearSelection()

            for i, column, row, value, selected in page_item_values:
                item = QtWidgets.QTableWidgetItem(value)
                self._page_tables[i].setItem(row, column, item)
                if also_selected_state and selected:
                    item.setSelected(True)
                    self._page_tables[i].setCurrentCell(row, column,
                                                        QtCore.QItemSelectionModel.NoUpdate)

    def _get_custom_track_names(self) -> 'set[str]':
        custom_tracks = set()
        if self._custom_tracks_table.isEnabled():
            for i in range(self._custom_tracks_table.rowCount()):
                custom_tracks.add(self._custom_tracks_table.item(i, 0).text())
        return custom_tracks

    def _sync_emblems(self):
        with self._blocked_page_signals():
            page_items = self._get_page_items()
            for page_item in page_items:
                page_item.setIcon(QtGui.QIcon())
                page_item.setToolTip(str())
                page_item.setForeground(QtGui.QBrush())

            custom_tracks = self._get_custom_track_names()

            custom_tracks_maps = collections.defaultdict(list)

            for page_item in page_items:
                text = page_item.text()
                if not text:
                    continue

                if text not in custom_tracks:
                    page_item.setIcon(self._error_icon)
                    page_item.setToolTip('Custom track can no longer be located in the track list.')
                    page_item.setForeground(self._red_color)
                else:
                    custom_tracks_maps[text].append(page_item)

            for _custom_track, page_items in custom_tracks_maps.items():
                if len(page_items) > 1:
                    for page_item in page_items:
                        page_item.setIcon(self._warning_icon)
                        page_item.setToolTip(
                            'Custom track has been assigned to more than one slot.')
                        page_item.setForeground(self._yellow_color)

        if self._custom_tracks_table.isEnabled():
            in_use_color = self.palette().windowText().color().darker(220)
            for row in range(self._custom_tracks_table.rowCount()):
                item = self._custom_tracks_table.item(row, 0)
                color = in_use_color if item.text() in custom_tracks_maps else QtGui.QBrush()
                item.setForeground(color)

    def _sync_tables_selection(self):
        sender = self.sender()
        with self._blocked_page_signals():
            for page_table in self._page_tables:
                if sender != page_table:
                    page_table.clearSelection()
                    page_table.clearFocus()

        if sender != self._custom_tracks_table:
            with blocked_signals(self._custom_tracks_table):
                self._custom_tracks_table.clearSelection()
                self._custom_tracks_table.clearFocus()

    def _on_tables_itemSelectionChanged(self):
        self._sync_tables_selection()
        self._update_info_view()

    def _update_info_view(self):
        if not self._info_view.isVisible():
            return

        for table in list(self._page_tables) + [self._custom_tracks_table]:
            for item in reversed(table.selectedItems()):
                item_text = item.text()
                if not item_text:
                    self._info_view.show_placeholder_message()
                else:
                    path = self._item_text_to_path.get(item_text)
                    if not path:
                        self._info_view.show_not_valid_message()
                    else:
                        self._info_view.set_path(path)
                return

        self._info_view.show_placeholder_message()

    def _sync_widgets(self):
        if not self._pending_sync_updates:
            return
        self._pending_sync_updates = 0

        self._sync_emblems()
        self._update_info_view()

    def _on_page_table_itemChanged(self, item: QtWidgets.QTableWidgetItem):
        _ = item

        # Drag and drop events may generate several of these events in bursts. To avoid wasting
        # cycles, the update is deferred to the next event loop iteration.
        self._pending_sync_updates += 1
        QtCore.QTimer.singleShot(0, self._sync_widgets)

        # Drag and drop events may generate several of these events in bursts. They need to be
        # grouped together as a single undo action.
        self._pending_undo_actions += 1
        QtCore.QTimer.singleShot(0, self._process_undo_action)

    def _clear_selection(self):
        with self._blocked_page_signals():
            for item in self._get_page_items():
                if item.isSelected():
                    item.setText(str())
        self._sync_emblems()
        self._update_info_view()

        self._pending_undo_actions += 1
        self._process_undo_action()

    def _process_undo_action(self):
        if not self._pending_undo_actions:
            return
        self._pending_undo_actions = 0

        # Resolve any potential pending event (e.g. item selection changed events).
        QtWidgets.QApplication.instance().processEvents()

        extra_page_count = self._get_configured_extra_page_count()
        page_item_values = self._get_page_item_values()[:extra_page_count * 16]

        # Undo action is only collected if the values (excluding the selection state) are actually
        # different.
        page_item_values_texts = [value for _, _, _, value, _ in page_item_values]
        if self._undo_history:
            previous_page_item_values = self._undo_history[-1]
            previous_page_item_values_texts = [
                value for _, _, _, value, _ in previous_page_item_values
            ]
        else:
            previous_page_item_values_texts = None

        if page_item_values_texts != previous_page_item_values_texts:
            self._undo_history.append(page_item_values)
            self._redo_history.clear()

            self._update_undo_redo_actions()

    def _undo(self):
        if len(self._undo_history) > 1:
            self._redo_history.insert(0, self._undo_history.pop())
            page_item_values = self._undo_history[-1]
            self._set_page_item_values(page_item_values)
            self._update_page_visibility(len(page_item_values) // 16)
            self._sync_emblems()
            self._update_info_view()

            self._update_undo_redo_actions()

    def _redo(self):
        if self._redo_history:
            page_item_values = self._redo_history.pop(0)
            self._undo_history.append(page_item_values)
            self._set_page_item_values(page_item_values)
            self._update_page_visibility(len(page_item_values) // 16)
            self._sync_emblems()
            self._update_info_view()

            self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        self._undo_action.setEnabled(len(self._undo_history) > 1)
        self._redo_action.setEnabled(bool(self._redo_history))

    def _on_custom_tracks_table_sortIndicatorChanged(self, logical_index: int,
                                                     order: QtCore.Qt.SortOrder):
        _ = order

        # When the sort indicator is unset, Qt won't reset the order to the original; it will be
        # done manually.
        if logical_index == -1:
            # Initialize dictionary in the correct [insertion] order.
            item_text_to_item = {item_text: None for item_text in self._item_text_to_path}

            # Take all the items and add in dictionary in the new order.
            for row in range(self._custom_tracks_table.rowCount()):
                item_text = self._custom_tracks_table.item(row, 0).text()
                if item_text not in item_text_to_item:
                    # Early out if the text in the row is not recognized (it could be a warning or
                    # error message in the first row).
                    return
                item = self._custom_tracks_table.takeItem(row, 0)
                item_text_to_item[item_text] = item

            # Reinsert the items back to the table.
            for row, item in enumerate(item_text_to_item.values()):
                self._custom_tracks_table.setItem(row, 0, item)

    def _on_open_configuration_directory_action_triggered(self):
        open_directory(os.path.dirname(os.path.abspath(self._settings.fileName())))

    def _on_options_action_triggered(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Options')

        dialog.deleteLater()
        dialog.destroyed.connect(
            lambda _obj: QtWidgets.QApplication.instance().setProperty('insta_tool_tips', None))
        QtWidgets.QApplication.instance().setProperty('insta_tool_tips', True)

        layout = QtWidgets.QVBoxLayout(dialog)

        horizontal_layout = QtWidgets.QHBoxLayout()
        horizontal_layout.setSpacing(dialog.fontMetrics().height())
        layout.addLayout(horizontal_layout)
        vertical_layouts = [QtWidgets.QVBoxLayout(), QtWidgets.QVBoxLayout()]
        for vertical_layout in vertical_layouts:
            vertical_layout.setSpacing(dialog.fontMetrics().height())
            horizontal_layout.addLayout(vertical_layout)

        def markdown_to_html(title: str, text: str) -> str:
            html = f'<h3>{title}</h3>\n'
            for paragraph in text.split('\n\n'):
                paragraph = paragraph.strip()
                if paragraph.startswith('- '):
                    unordered_list = ''
                    for line in paragraph.splitlines():
                        unordered_list += f'<li>{line[1:].strip()}</li>\n'
                    paragraph = f'<ul>{unordered_list}</ul>\n'
                else:
                    paragraph = paragraph.replace('\n', ' ')
                paragraph = re.sub(r'^---(.*)', r'<hr/>\1', paragraph)
                paragraph = re.sub(r'\b_(.+)_\b', r'<em>\1</em>', paragraph)
                paragraph = re.sub(r'\*\*([^\*]+)\*\*', r'<b style="white-space: nowrap;">\1</b>',
                                   paragraph)
                paragraph = re.sub(
                    r'`([^`]+)`', r'<code style="background: #1B1B1B; white-space: nowrap;">'
                    r'&nbsp;\1&nbsp;</code>', paragraph)
                html += f'<p>{paragraph}</p>\n'
            return html

        group_count = len(mkdd_extender.OPTIONAL_ARGUMENTS.items())

        for i, (group_name, group_options) in enumerate(mkdd_extender.OPTIONAL_ARGUMENTS.items()):
            group_box = QtWidgets.QGroupBox(group_name)
            group_box.setLayout(QtWidgets.QVBoxLayout())

            for option_label, option_type, option_help in group_options:
                option_member_name = f'_{mkdd_extender.option_label_as_variable_name(option_label)}'
                option_value = getattr(self, option_member_name)
                option_help = markdown_to_html(option_label, option_help)

                if option_type is bool:
                    option_widget = QtWidgets.QCheckBox(option_label)
                    option_widget.setToolTip(option_help)
                    option_widget.setChecked(bool(option_value))

                    def on_toggled(checked, option_member_name=option_member_name):
                        setattr(self, option_member_name, checked)

                    option_widget.toggled.connect(on_toggled)
                    option_widget.toggled.connect(self._update_options_string)
                    group_box.layout().addWidget(option_widget)

                if option_type is int:
                    option_widget_label = QtWidgets.QLabel(option_label)
                    option_widget_label.setToolTip(option_help)
                    option_widget = QtWidgets.QLineEdit(str(option_value or 0))
                    option_widget.setToolTip(option_help)
                    validator = QtGui.QIntValidator()
                    validator.setBottom(0)
                    option_widget.setValidator(validator)
                    option_widget_layout = QtWidgets.QHBoxLayout()
                    option_widget_layout.addWidget(option_widget_label)
                    option_widget_layout.addWidget(option_widget)

                    def on_textChanged(text, option_member_name=option_member_name):
                        try:
                            value = int(text)
                        except ValueError:
                            value = 0
                        setattr(self, option_member_name, value)

                    option_widget.textChanged.connect(on_textChanged)
                    option_widget.textChanged.connect(self._update_options_string)
                    group_box.layout().addLayout(option_widget_layout)

                if isinstance(option_type, tuple):
                    option_type, *rest = option_type

                    if option_type == 'choices':
                        option_values, default_value = rest

                        option_widget_label = QtWidgets.QLabel(option_label)
                        option_widget_label.setToolTip(option_help)
                        option_widget = QtWidgets.QComboBox()
                        option_widget.addItems(tuple(str(v) for v in option_values))
                        if option_value in option_values:
                            option_widget.setCurrentIndex(option_values.index(option_value))
                        elif default_value in option_values:
                            option_widget.setCurrentIndex(option_values.index(default_value))
                        option_widget.setToolTip(option_help)
                        option_widget_layout = QtWidgets.QHBoxLayout()
                        option_widget_layout.addWidget(option_widget_label)
                        option_widget_layout.addWidget(option_widget, 1)

                        def on_currentTextChanged(text,
                                                  default_value=default_value,
                                                  option_member_name=option_member_name):
                            try:
                                value = type(default_value)(text)
                            except ValueError:
                                value = type(default_value)()
                            setattr(self, option_member_name, value)

                        option_widget.currentTextChanged.connect(on_currentTextChanged)
                        option_widget.currentTextChanged.connect(self._update_options_string)
                        group_box.layout().addLayout(option_widget_layout)

            vertical_layouts[int(i >= group_count / 2)].addWidget(group_box)

        for vertical_layout in vertical_layouts:
            vertical_layout.addStretch()

        layout.addSpacing(dialog.fontMetrics().height() * 2)
        close_button = QtWidgets.QPushButton('Close')
        close_button.clicked.connect(dialog.close)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(close_button)
        layout.addLayout(bottom_layout)
        dialog.exec_()

    def _update_options_string(self):
        options_strings = []
        for _group_name, group_options in mkdd_extender.OPTIONAL_ARGUMENTS.items():
            for option_label, option_type, _option_help in group_options:
                option_member_name = f'_{mkdd_extender.option_label_as_variable_name(option_label)}'
                option_value = getattr(self, option_member_name)
                option_as_argument = mkdd_extender.option_label_as_argument_name(option_label)

                if option_type is bool:
                    if option_value:
                        options_strings.append(option_as_argument)

                if option_type is int:
                    if option_value:
                        options_strings.append(f'{option_as_argument}={option_value}')

                if isinstance(option_type, tuple):
                    option_type, *rest = option_type

                    if option_type == 'choices':
                        _option_values, default_value = rest
                        if option_value != default_value:
                            options_strings.append(f'{option_as_argument}={option_value}')

        self._options_edit.setText(' '.join(options_strings))

    def _on_pack_generator_action_triggered(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 80)
        dialog.setWindowTitle('Pack Generator')
        layout = QtWidgets.QVBoxLayout(dialog)
        description_label = QtWidgets.QLabel()
        description_label.setWordWrap(True)
        description_label.setText(
            'This is a helper tool that copies, extracts, and flattens the custom tracks that are '
            'currently mapped to each of the slots.'
            '\n\n'
            'Its main purpose is to provide a directory of custom tracks that can be used with the '
            'MKDD Extender in command-line mode.')
        layout.addWidget(description_label)
        layout.addSpacing(dialog.fontMetrics().height())
        output_directory_layout = QtWidgets.QFormLayout()
        output_directory_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        output_directory_edit = PathEdit('Select Output Directory',
                                         QtWidgets.QFileDialog.AcceptSave,
                                         QtWidgets.QFileDialog.Directory)
        path = self._settings.value('miscellaneous/pack_generator_path')
        if path:
            output_directory_edit.set_path(path)
        path = self._settings.value('miscellaneous/pack_generator_last_dir')
        if path:
            output_directory_edit.set_last_dir(path)

        def on_output_directory_textChanged(dirpath: str):
            _ = dirpath
            self._settings.setValue('miscellaneous/pack_generator_path',
                                    output_directory_edit.get_path())
            self._settings.setValue('miscellaneous/pack_generator_last_dir',
                                    output_directory_edit.get_last_dir())

        output_directory_edit.textChanged.connect(on_output_directory_textChanged)
        output_directory_layout.addRow('Output Directory', output_directory_edit)
        layout.addLayout(output_directory_layout)
        layout.addStretch()
        layout.addSpacing(dialog.fontMetrics().height() * 2)

        def generate_pack():
            dirpath = output_directory_edit.get_path()

            if not dirpath:
                raise mkdd_extender.MKDDExtenderError('Output directory has not been set.')

            os.makedirs(dirpath, exist_ok=True)

            if not os.path.isdir(dirpath):
                raise mkdd_extender.MKDDExtenderError(
                    'Output path already exists, but it is not a directory.')

            if os.listdir(dirpath):
                raise mkdd_extender.MKDDExtenderError('Output directory is not empty.')

            extra_page_count = self._get_configured_extra_page_count()

            paths = []
            for item in self._get_page_items()[:extra_page_count * 16]:
                path = self._item_text_to_path.get(item.text())
                if not path:
                    raise mkdd_extender.MKDDExtenderError(
                        'Please make sure that all slots have been assigned to a valid custom '
                        'track.')
                paths.append(path)

            LETTER_RANGE = f'A-{chr(ord("A") + mkdd_extender.MAX_EXTRA_PAGES - 1)}'

            for i, src_path in enumerate(paths):
                name = os.path.basename(src_path)

                # If the name had a recognizable prefix (probably as part of a previous run), get
                # rid of it.
                parts = name.split('_', maxsplit=1)
                if len(parts) > 1 and re.match(rf'[{LETTER_RANGE}][0-1][0-9].?', parts[0]):
                    filtered_name = parts[1]
                else:
                    filtered_name = name

                # Also drop the potential exception, as any archive will be extracted.
                if filtered_name.endswith('.zip'):
                    filtered_name = filtered_name[:-len('.zip')]

                page_index = i // 16
                track_number = i % 16 + 1
                letter = chr(ord('A') + page_index)
                prefix = f'{letter}{track_number:02}'

                dst_dirname = f'{prefix}_{filtered_name}'
                dst_dirpath = os.path.join(dirpath, dst_dirname)

                mkdd_extender.extract_and_flatten(src_path, dst_dirpath)

        def on_generate_button_clicked():
            error_message = None
            exception_info = None

            try:
                progress_dialog = ProgressDialog('Processing custom tracks...', generate_pack, self)
                progress_dialog.execute_and_wait()

            except mkdd_extender.MKDDExtenderError as e:
                error_message = str(e)
            except AssertionError as e:
                error_message = str(e) or 'Assertion error.'
                exception_info = traceback.format_exc()
            except Exception as e:
                error_message = str(e)
                exception_info = traceback.format_exc()

            if error_message is not None:
                error_message = error_message or 'Unknown error.'

                icon_name = 'error'
                title = 'Error'
                text = error_message
                detailed_text = exception_info
            else:
                icon_name = 'success'
                title = 'Success!!'
                text = 'Custom tracks processed successfully.'
                detailed_text = ''

            show_message(icon_name, title, text, detailed_text, self)

        generate_button = QtWidgets.QPushButton('Generate')
        generate_button.clicked.connect(on_generate_button_clicked)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(generate_button)
        layout.addLayout(bottom_layout)
        dialog.exec_()

    def _on_text_image_builder_action_triggered(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 80)
        dialog.setWindowTitle('Text Image Builder')

        description_label = QtWidgets.QLabel()
        description_label.setWordWrap(True)
        description_label.setText(
            'This is a helper tool to build text images using Mario Kart: Double Dash!!\'s '
            'bitmap-based font.')

        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        resolution_combobox = QtWidgets.QComboBox()
        resolution_combobox.addItem('Course Name (256x32)', QtCore.QSize(256, 32))
        resolution_combobox.addItem('Character Name (152x32)', QtCore.QSize(152, 32))
        resolution_combobox.addItem('Custom')
        resolution_width_spinbox = QtWidgets.QSpinBox()
        resolution_height_spinbox = QtWidgets.QSpinBox()
        for spinbox in (resolution_width_spinbox, resolution_height_spinbox):
            spinbox.setMinimum(1)
            spinbox.setMaximum(4 * 1024)
        resolution_width_spinbox.setValue(256)
        resolution_height_spinbox.setValue(32)
        resolution_times_label = QtWidgets.QLabel('\u00d7')
        resolution_layout = QtWidgets.QHBoxLayout()
        resolution_layout.addWidget(resolution_combobox, 2)
        resolution_layout.addWidget(resolution_width_spinbox, 1)
        resolution_layout.addWidget(resolution_times_label)
        resolution_layout.addWidget(resolution_height_spinbox, 1)
        form_layout.addRow('Resolution', resolution_layout)
        text_edit = QtWidgets.QLineEdit()
        font = text_edit.font()
        font.setCapitalization(QtGui.QFont.AllUppercase)
        text_edit.setFont(font)
        form_layout.addRow('Text', text_edit)
        character_spacing_slider = SpinnableSlider()
        INITIAL_CHARACTER_SPACING = -9
        character_spacing_slider.set_range(-30, 20, INITIAL_CHARACTER_SPACING)
        form_layout.addRow('Character Spacing', character_spacing_slider)
        word_spacing_slider = SpinnableSlider()
        INITIAL_WORD_SPACING = 1
        word_spacing_slider.set_range(-20, 30, INITIAL_WORD_SPACING)
        form_layout.addRow('Word Spacing', word_spacing_slider)
        horizontal_scaling_slider = SpinnableSlider()
        horizontal_scaling_slider.set_range(1, 100, 100)
        form_layout.addRow('Horizontal Scaling', horizontal_scaling_slider)
        vertical_scaling_slider = SpinnableSlider()
        vertical_scaling_slider.set_range(1, 100, 100)
        form_layout.addRow('Vertical Scaling', vertical_scaling_slider)

        menu = QtWidgets.QMenu()
        save_as_png_action = menu.addAction('Save as PNG')
        save_as_bti_action = menu.addAction('Save as BTI')
        menu.addSeparator()
        copy_action = menu.addAction('Copy to Clipboard')

        image_placeholder = []

        def save_as(as_bti: bool):
            if not image_placeholder:
                return

            file_type = "bti" if as_bti else "png"

            last_filepath_setting_name = f'text_image_builder/last_{file_type}_filepath'
            filepath = self._settings.value(last_filepath_setting_name)
            if filepath:
                dirpath = os.path.dirname(filepath)
            else:
                dirpath = os.path.expanduser('~')
                filepath = f'image.{file_type}'

            file_dialog = QtWidgets.QFileDialog(self, f'Save text image as {file_type.upper()}',
                                                dirpath)
            file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
            file_dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
            file_dialog.setNameFilters((f'{file_type.upper()} (*.{file_type})', ))
            file_dialog.selectFile(os.path.basename(filepath))

            dialog_code = file_dialog.exec_()
            if dialog_code == QtWidgets.QDialog.Accepted and file_dialog.selectedFiles():
                image = image_placeholder[0]
                filepath = file_dialog.selectedFiles()[0]

                if not as_bti:
                    image.save(filepath)
                else:
                    with tempfile.TemporaryDirectory(
                            prefix=mkdd_extender.TEMP_DIR_PREFIX) as tmp_dir:
                        tmp_filepath = os.path.join(tmp_dir, 'image.png')
                        image.save(tmp_filepath)
                        mkdd_extender.convert_png_to_bti(tmp_filepath, filepath, 'IA4')

                self._settings.setValue(last_filepath_setting_name, filepath)

        save_as_png_action.triggered.connect(lambda: save_as(False))
        save_as_bti_action.triggered.connect(lambda: save_as(True))

        def on_copy_action_triggered():
            if not image_placeholder:
                return

            image = image_placeholder[0]
            width = image.width
            height = image.height
            data = image.tobytes("raw", "RGBA")
            QtWidgets.QApplication.instance().clipboard().setImage(
                QtGui.QImage(data, width, height, QtGui.QImage.Format_RGBA8888))

        copy_action.triggered.connect(on_copy_action_triggered)

        image_widget = QtWidgets.QLabel()
        image_widget.setAlignment(QtCore.Qt.AlignCenter)
        image_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        image_widget.customContextMenuRequested.connect(
            lambda pos: menu.exec_(image_widget.mapToGlobal(pos)))
        palette = image_widget.palette()
        palette.setColor(image_widget.foregroundRole(), QtGui.QColor(170, 20, 20))
        image_widget.setPalette(palette)

        image_frame = QtWidgets.QFrame()
        image_frame.setAutoFillBackground(True)
        image_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        MARGIN = dialog.fontMetrics().height() * 5
        image_frame.setMinimumSize(MARGIN * 2, MARGIN * 2)
        palette = image_frame.palette()
        palette.setBrush(image_frame.backgroundRole(), palette.dark())
        image_frame.setPalette(palette)
        image_frame_layout = QtWidgets.QVBoxLayout(image_frame)
        image_frame_layout.setAlignment(QtCore.Qt.AlignCenter)
        image_frame_layout.addWidget(image_widget)

        reset_button = QtWidgets.QPushButton('Reset')
        reset_button.setAutoDefault(False)
        save_button = QtWidgets.QPushButton('Save')
        save_button.setAutoDefault(False)
        save_button.setMenu(menu)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(reset_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_button)

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addWidget(description_label)
        layout.addSpacing(dialog.fontMetrics().height())
        layout.addLayout(form_layout)
        layout.addSpacing(dialog.fontMetrics().height() // 2)
        layout.addWidget(image_frame, 1)
        layout.addSpacing(dialog.fontMetrics().height() // 2)
        layout.addLayout(bottom_layout)

        def update():
            text = text_edit.text()
            resolution = resolution_combobox.currentData()
            if resolution is not None:
                width = resolution.width()
                height = resolution.height()
            else:
                width = resolution_width_spinbox.value()
                height = resolution_height_spinbox.value()
            character_spacing = character_spacing_slider.get_value()
            word_spacing = word_spacing_slider.get_value()
            horizontal_scaling = horizontal_scaling_slider.get_value() / 100
            vertical_scaling = vertical_scaling_slider.get_value() / 100

            image_placeholder.clear()
            image, overflow = mkdd_extender.build_text_image_from_bitmap_font(
                text, width, height, character_spacing, word_spacing, horizontal_scaling,
                vertical_scaling)
            image_placeholder.append(image)

            background = (255, 40, 40) if overflow else (128, 128, 128)
            image_with_background = Image.new('RGBA', (width, height), background)
            image_with_background.alpha_composite(image)
            data = image_with_background.tobytes("raw", "RGBA")
            pixmap = QtGui.QPixmap.fromImage(
                QtGui.QImage(data, width, height, QtGui.QImage.Format_RGBA8888))
            image_widget.setPixmap(pixmap)

            image_widget.setMinimumSize(width, height)
            save_as_png_action.setEnabled(bool(image_placeholder))
            save_as_bti_action.setEnabled(bool(image_placeholder))
            copy_action.setEnabled(bool(image_placeholder))
            resolution_width_spinbox.setVisible(resolution is None)
            resolution_height_spinbox.setVisible(resolution is None)
            resolution_times_label.setVisible(resolution is None)

        def reset():
            with blocked_signals(character_spacing_slider):
                character_spacing_slider.set_value(INITIAL_CHARACTER_SPACING)
            with blocked_signals(word_spacing_slider):
                word_spacing_slider.set_value(INITIAL_WORD_SPACING)
            with blocked_signals(horizontal_scaling_slider):
                horizontal_scaling_slider.set_value(100)
            with blocked_signals(vertical_scaling_slider):
                vertical_scaling_slider.set_value(100)

            update()

        resolution = self._settings.value('text_image_builder/resolution')
        for i in range(resolution_combobox.count()):
            if resolution_combobox.itemText(i) == resolution:
                resolution_combobox.setCurrentIndex(i)
        resolution_width = self._settings.value('text_image_builder/resolution_width')
        if resolution_width is not None:
            resolution_width_spinbox.setValue(int(resolution_width))
        resolution_height = self._settings.value('text_image_builder/resolution_height')
        if resolution_height is not None:
            resolution_height_spinbox.setValue(int(resolution_height))
        text = self._settings.value('text_image_builder/text')
        if text is not None:
            text_edit.setText(text)
        character_spacing = self._settings.value('text_image_builder/character_spacing')
        if character_spacing is not None:
            character_spacing_slider.set_value(int(character_spacing))
        word_spacing = self._settings.value('text_image_builder/word_spacing')
        if word_spacing is not None:
            word_spacing_slider.set_value(int(word_spacing))
        horizontal_scaling = self._settings.value('text_image_builder/horizontal_scaling')
        if horizontal_scaling is not None:
            horizontal_scaling_slider.set_value(int(horizontal_scaling))
        vertical_scaling = self._settings.value('text_image_builder/vertical_scaling')
        if vertical_scaling is not None:
            vertical_scaling_slider.set_value(int(vertical_scaling))

        resolution_combobox.currentIndexChanged.connect(lambda _index: update())
        resolution_width_spinbox.valueChanged.connect(lambda _value: update())
        resolution_height_spinbox.valueChanged.connect(lambda _value: update())
        text_edit.textChanged.connect(lambda _text: update())
        character_spacing_slider.value_changed.connect(lambda _value: update())
        word_spacing_slider.value_changed.connect(lambda _value: update())
        horizontal_scaling_slider.value_changed.connect(lambda _value: update())
        vertical_scaling_slider.value_changed.connect(lambda _value: update())
        reset_button.clicked.connect(reset)

        update()

        dialog.exec_()

        self._settings.setValue('text_image_builder/resolution', resolution_combobox.currentText())
        self._settings.setValue('text_image_builder/resolution_width',
                                resolution_width_spinbox.value())
        self._settings.setValue('text_image_builder/resolution_height',
                                resolution_height_spinbox.value())
        self._settings.setValue('text_image_builder/text', text_edit.text())
        self._settings.setValue('text_image_builder/character_spacing',
                                character_spacing_slider.get_value())
        self._settings.setValue('text_image_builder/word_spacing', word_spacing_slider.get_value())
        self._settings.setValue('text_image_builder/horizontal_scaling',
                                horizontal_scaling_slider.get_value())
        self._settings.setValue('text_image_builder/vertical_scaling',
                                vertical_scaling_slider.get_value())

    def _on_ast_converter_action_triggered(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setMinimumWidth(dialog.fontMetrics().averageCharWidth() * 100)
        dialog.setWindowTitle('AST Converter')
        dialog.setFocusPolicy(QtCore.Qt.StrongFocus)

        name_filters = ('WAV or AST (*.wav *.ast)', )
        input_file_edit = PathEdit('Select Input Audio File', QtWidgets.QFileDialog.AcceptOpen,
                                   QtWidgets.QFileDialog.ExistingFile, name_filters)
        output_file_edit = PathEdit('Select Output Audio File', QtWidgets.QFileDialog.AcceptSave,
                                    QtWidgets.QFileDialog.AnyFile, name_filters)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        form_layout.addRow('Input Audio File', input_file_edit)
        form_layout.addRow('Output Audio File', output_file_edit)

        info_frame = QtWidgets.QFrame()
        info_frame.setAutoFillBackground(True)
        info_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        MARGIN = dialog.fontMetrics().height() * 6
        info_frame.setMinimumSize(MARGIN * 2, MARGIN * 2)
        palette = info_frame.palette()
        palette.setBrush(info_frame.backgroundRole(), palette.dark())
        info_frame.setPalette(palette)
        info_frame_layout = QtWidgets.QVBoxLayout(info_frame)
        info_frame_layout.setContentsMargins(0, 0, 0, 0)

        info_browser = QtWidgets.QTextBrowser()
        info_browser.setFrameShape(QtWidgets.QFrame.NoFrame)
        info_browser.viewport().setAutoFillBackground(False)
        info_frame_layout.addWidget(info_browser)
        info_label = QtWidgets.QLabel()
        info_label.setWordWrap(True)
        info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_frame_layout.addWidget(info_label)

        info_box = QtWidgets.QGroupBox('Input File Info')
        info_box.setContentsMargins(0, 0, 0, 0)
        info_box_layout = QtWidgets.QVBoxLayout(info_box)
        info_box_layout.addWidget(info_frame)
        info_box_layout.setContentsMargins(0, 0, 0, 0)

        ast_box = QtWidgets.QGroupBox('AST Output Settings')
        volume_slider = SpinnableSlider()
        volume_slider.set_range(0, 127, 127)
        looped_box = QtWidgets.QCheckBox()
        looped_box.setChecked(True)
        loop_start_slider = SpinnableSlider()
        ast_form_layout = QtWidgets.QFormLayout(ast_box)
        ast_form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        ast_form_layout.addRow('Volume', volume_slider)
        ast_form_layout.addRow('Looped', looped_box)
        ast_form_layout.addRow('Loop Start', loop_start_slider)

        body_layout = QtWidgets.QHBoxLayout()
        body_layout.addWidget(info_box, 1)
        body_layout.addWidget(ast_box, 1)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addLayout(body_layout, 1)

        reset_button = QtWidgets.QPushButton('Reset')
        reset_button.setAutoDefault(False)
        convert_button = QtWidgets.QPushButton('Convert')
        convert_button.setAutoDefault(False)
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(reset_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(convert_button)

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.addLayout(main_layout)
        layout.addSpacing(dialog.fontMetrics().height() // 2)
        layout.addLayout(bottom_layout)

        def set_info_label(text: str, color: QtGui.QColor = None):
            info_label.setText(text)
            palette = self.palette()  # To inherit background color from parent.
            if color is not None:
                palette.setColor(info_label.foregroundRole(), color)
            info_label.setPalette(palette)
            info_label.setVisible(bool(text))
            info_browser.setVisible(not bool(text))

        local_sample_count = [0]

        def update_info():
            set_info_label('')

            input_filepath = input_file_edit.get_path()
            output_filepath = output_file_edit.get_path()

            stem, ext = os.path.splitext(input_filepath)
            if not input_filepath:
                set_info_label('Select an input audio file', QtGui.QColor(100, 100, 100))
            elif ext not in ('.ast', '.wav'):
                set_info_label(f'Unrecognized file extension "{ext}"', QtGui.QColor(170, 20, 20))
            else:
                if os.path.isfile(input_filepath):
                    output_ext = '.ast' if ext == '.wav' else '.wav'
                    if not output_filepath:
                        output_filepath = f'{stem}{output_ext}'
                    else:
                        output_stem, _output_ext = os.path.splitext(output_filepath)
                        output_filepath = f'{output_stem}{output_ext}'

                    with blocked_signals(output_file_edit):
                        output_file_edit.set_path(output_filepath)

            if input_filepath.endswith('.ast'):
                ast_box.setEnabled(False)
                convert_button.setText('Convert to WAV')
            else:
                ast_box.setEnabled(True)
                convert_button.setText('Convert to AST')

            try:
                html = ''

                if ext == '.ast':
                    html = self._info_view.generate_ast_file_tool_tip(input_filepath, cache=False)
                elif ext == '.wav':
                    with wave.open(input_filepath, 'rb') as f:
                        bit_depth = f.getsampwidth() * 8
                        channel_count = f.getnchannels()
                        sample_rate = f.getframerate()
                        sample_count = f.getnframes()

                    local_sample_count[0] = sample_count

                    html = textwrap.dedent(f"""\
                        <table>
                        <tr><td><b>Duration: </b> </td><td>{human_readable_duration(sample_count, sample_rate)}</td></tr>
                        <tr><td><b>Sample Rate: </b> </td><td>{sample_rate} Hz</td></tr>
                        <tr><td><b>Bit Depth: </b> </td><td>{bit_depth}</td></tr>
                        <tr><td><b>Channel Count: </b> </td><td>{channel_count}</td></tr>
                        </table>
                    """)  # noqa: E501

                info_browser.setHtml(html)
            except Exception as e:  # pylint: disable=broad-exception-caught
                set_info_label(f'Unexpected error: "{e}"', QtGui.QColor(170, 20, 20))

            update_ast_form()

        def update_ast_form():
            sample_count = local_sample_count[0]
            with blocked_signals(loop_start_slider):
                clampped_value = max(0, min(loop_start_slider.get_value(), sample_count - 1))
                loop_start_slider.set_range(0, max(0, sample_count - 1), clampped_value)
                loop_start_slider.setEnabled(looped_box.isChecked())

        def reset():
            with blocked_signals(volume_slider):
                volume_slider.set_value(127)
            with blocked_signals(looped_box):
                looped_box.setChecked(True)
            with blocked_signals(loop_start_slider):
                loop_start_slider.set_range(0, max(0, local_sample_count[0] - 1), 0)

            update_ast_form()

        def convert():
            error_message = None
            exception_info = None

            input_path = input_file_edit.get_path()
            output_path = output_file_edit.get_path()

            try:
                _output_stem, output_ext = os.path.splitext(output_path)

                if input_path.endswith('.ast'):
                    if output_ext != '.wav':
                        raise mkdd_extender.MKDDExtenderError(
                            f'Unexpected output file extension: "{output_ext}" (expected ".wav")')

                    def func():
                        ast_converter.convert_to_wav(input_path, output_path)
                else:
                    if output_ext != '.ast':
                        raise mkdd_extender.MKDDExtenderError(
                            f'Unexpected output file extension: "{output_ext}" (expected ".ast")')

                    def func():
                        if looped_box.isChecked():
                            loop_start = loop_start_slider.get_value()
                        else:
                            loop_start = None

                        ast_converter.convert_to_ast(
                            input_path,
                            output_path,
                            looped=0xFFFF if looped_box.isChecked() else 0x0000,
                            sample_count=None,
                            loop_start=loop_start,
                            loop_end=None,
                            volume=volume_slider.get_value(),
                        )

                progress_dialog = ProgressDialog('Converting audio file...', func, dialog)
                progress_dialog.execute_and_wait()

            except mkdd_extender.MKDDExtenderError as e:
                error_message = str(e)
            except AssertionError as e:
                error_message = str(e) or 'Assertion error.'
                exception_info = traceback.format_exc()
            except Exception as e:
                error_message = str(e)
                exception_info = traceback.format_exc()

            if error_message is not None:
                error_message = error_message or 'Unknown error.'

                icon_name = 'error'
                title = 'Error'
                text = error_message
                detailed_text = exception_info
            else:
                icon_name = 'success'
                title = 'Success!!'
                text = 'Audio file converted successfully.'
                detailed_text = ''

            show_message(icon_name, title, text, detailed_text, self)

        path = self._settings.value('ast_converter/input_path')
        if path:
            input_file_edit.set_path(path)
        path = self._settings.value('ast_converter/input_last_dir')
        if path:
            input_file_edit.set_last_dir(path)
        path = self._settings.value('ast_converter/output_path')
        if path:
            output_file_edit.set_path(path)
        path = self._settings.value('ast_converter/output_last_dir')
        if path:
            output_file_edit.set_last_dir(path)

        update_info()

        volume = self._settings.value('ast_converter/volume')
        if volume is not None:
            volume_slider.set_value(int(volume))
        looped = self._settings.value('ast_converter/looped')
        if looped is not None:
            looped_box.setChecked(looped == 'true')
        loop_start = self._settings.value('ast_converter/loop_start')
        if loop_start is not None:
            loop_start_slider.set_value(int(loop_start))

        update_ast_form()

        input_file_edit.textChanged.connect(lambda _text: update_info())
        looped_box.toggled.connect(lambda _checked: update_ast_form())
        loop_start_slider.value_changed.connect(lambda _value: update_ast_form())
        reset_button.clicked.connect(reset)
        convert_button.clicked.connect(convert)

        dialog.exec_()

        self._settings.setValue('ast_converter/input_path', input_file_edit.get_path())
        self._settings.setValue('ast_converter/input_last_dir', input_file_edit.get_last_dir())
        self._settings.setValue('ast_converter/output_path', output_file_edit.get_path())
        self._settings.setValue('ast_converter/output_last_dir', output_file_edit.get_last_dir())
        self._settings.setValue('ast_converter/volume', volume_slider.get_value())
        self._settings.setValue('ast_converter/looped', looped_box.isChecked())
        self._settings.setValue('ast_converter/loop_start', loop_start_slider.get_value())

    def _on_purge_preview_caches_action_triggered(self):
        self._info_view.purge_caches()
        gc.collect()  # Rather placebo, but at least intention is shown.
        self._load_custom_tracks_directory()

    def _on_shelf_menu_about_to_show(self):
        shelf_menu = self.sender()
        shelf_menu.clear()

        font_height = self.fontMetrics().height()
        header_font_size = int(font_height * 0.85)
        font_size = int(font_height * 0.75)

        def generate_html(course_names):
            html = '<table style="white-space: nowrap;">'
            pages = len(course_names) // 16
            for page in range(pages):
                margin = 0.0 if page == 0 else 0.8
                html += ('<tr>'
                         f'<td colspan="4" style="text-align: center; padding-top: {margin}em; '
                         f'font-size: {header_font_size}px;">'
                         f'<b>Page {page + 2}/{pages + 1}</b></td>'
                         '</tr>')
                for col in range(4):
                    html += '<tr>'
                    for row in range(4):
                        course_name = course_names[page * 16 + row * 4 + col] or '-'
                        html += (f'<td style="padding: 0.3em; font-size: {font_size}px;">'
                                 f'{course_name}</td>')
                    html += '</tr>'
            html += '</table>'

            return html

        items = self._get_shelf_items()

        for i, (name, course_names) in enumerate(items):
            assert len(course_names) % 16 == 0

            shelf_item_widget = QtWidgets.QWidget()
            shelf_item_layout = QtWidgets.QVBoxLayout(shelf_item_widget)
            shelf_item_layout.addWidget(QtWidgets.QLabel(generate_html(course_names)))

            delete_button = QtWidgets.QPushButton('Delete')
            delete_button.clicked.connect(lambda _checked=False, i=i: self._delete_shelf_item(i))
            load_button = QtWidgets.QPushButton('Load')
            load_button.clicked.connect(lambda _checked=False, i=i: self._load_shelf_item(i))
            load_button.clicked.connect(shelf_menu.close)
            buttons_layout = QtWidgets.QHBoxLayout()
            buttons_layout.addStretch()
            buttons_layout.addWidget(delete_button)
            buttons_layout.addWidget(load_button)

            shelf_item_layout.addLayout(buttons_layout)

            shelf_item_menu = shelf_menu.addMenu(name)
            shelf_item_widget_action = QtWidgets.QWidgetAction(shelf_item_menu)
            shelf_item_widget_action.setDefaultWidget(shelf_item_widget)
            shelf_item_menu.addAction(shelf_item_widget_action)

        if items:
            shelf_menu.addSeparator()

        create_action = shelf_menu.addAction('Create Shelf Item...')
        create_action.triggered.connect(self._create_shelf_item)

    def _build(self):
        if self._log_table.get_clear_log_before_each_run():
            self._log_table.setRowCount(0)

        error_message = None
        exception_info = None
        try:
            input_path = self._input_iso_file_edit.get_path()
            output_path = self._output_iso_file_edit.get_path()

            if not input_path:
                raise mkdd_extender.MKDDExtenderError(
                    'Path to the input ISO file has not been specified.')
            if not output_path:
                raise mkdd_extender.MKDDExtenderError(
                    'Path to the output ISO file has not been specified.')

            if input_path == output_path:
                raise mkdd_extender.MKDDExtenderError('Input and output paths cannot be identical.')

            args = argparse.Namespace()
            args.input = input_path
            args.output = output_path
            args.tracks = []

            extra_page_count = self._get_configured_extra_page_count()

            for item in self._get_page_items()[:extra_page_count * 16]:
                path = self._item_text_to_path.get(item.text())
                if path:
                    args.tracks.append(path)
                else:
                    args.tracks.append('')

            slots_unassigned = len([None for t in args.tracks if not t])
            slots_assigned = len(args.tracks) - slots_unassigned

            if slots_unassigned > 0:
                mkdd_extender.log.warning(f'Only {slots_assigned} slots have been assigned. Empty '
                                          f'slots ({slots_unassigned}) will be provided with a '
                                          'placeholder.')

                args.tracks = [t or placeholder_course_dir for t in args.tracks]

            assert len(args.tracks) % 16 == 0

            for _group_name, group_options in mkdd_extender.OPTIONAL_ARGUMENTS.items():
                for option_label, _option_type, _option_help in group_options:
                    option_variable_name = mkdd_extender.option_label_as_variable_name(option_label)
                    option_member_name = f'_{option_variable_name}'
                    option_value = getattr(self, option_member_name) or None
                    setattr(args, option_variable_name, option_value)

            progress_dialog = ProgressDialog('Building ISO file...',
                                             lambda: mkdd_extender.extend_game(args), self)
            progress_dialog.execute_and_wait()

        except mkdd_extender.MKDDExtenderError as e:
            error_message = str(e)
            mkdd_extender.log.error(error_message)
        except AssertionError as e:
            error_message = str(e) or 'Assertion error.'
            mkdd_extender.log.exception(error_message)
            exception_info = traceback.format_exc()
        except Exception as e:
            error_message = str(e) or 'Unknown error'
            mkdd_extender.log.exception(error_message)
            exception_info = traceback.format_exc()

        if error_message is not None:
            icon_name = 'error'
            title = 'Error'
            text = error_message
            detailed_text = exception_info
        else:
            icon_name = 'success'
            title = 'Success!!'
            text = 'ISO file has been generated successfully.'
            detailed_text = ''

            if not args.extended_memory:
                iso_size = os.path.getsize(output_path)
                if iso_size > mkdd_extender.MAX_ISO_SIZE:
                    icon_name = 'successwarning'
                    text += (
                        '<br/><br/><hr><br/>'
                        f'The generated ISO file (<code>{iso_size} bytes</code>) is larger than '
                        'the size that GameCube or Wii can support (<code>'
                        f'{mkdd_extender.MAX_ISO_SIZE} bytes</code>). The game will work on '
                        'Dolphin, but will likely <em>not</em> work on real hardware.<br/><br/>'
                        'Suggested actions that can be taken to reduce the ISO file size:'
                        '<ul style="white-space: nowrap;">'
                        '<li>Lower the sample rate in the <b>Sample Rate</b> option (e.g. to '
                        '<code>24000 Hz</code>)</li>'
                        '<li>Mark the <b>Use Auxiliary Audio Track</b> option to reuse stock audio '
                        'tracks for custom tracks<br/>that define the '
                        '<code>auxiliary_audio_track</code> field.</li>'
                        '<li>Mark the <b>Use Replacee Audio Track</b> option to use the stock '
                        'audio tracks for all tracks.</li>'
                        '</ul>')

        show_message(icon_name, title, text, detailed_text, self)


def run() -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)

    set_dark_theme(app)

    window = MKDDExtenderWindow()
    window.show()

    return app.exec_()
