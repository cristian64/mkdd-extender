"""
Graphical user interface for the MKDD Extender.
"""
import argparse
import collections
import contextlib
import json
import os
import re
import signal
import sys
import textwrap
import threading
import traceback

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

import mkdd_extender

FONT_FAMILIES = 'Liberation Mono, FreeMono, Nimbus Mono, Consolas, Courier New'

script_path = os.path.realpath(__file__)
script_dir = os.path.dirname(script_path)
tools_dir = os.path.join(script_dir, 'tools')
data_dir = os.path.join(script_dir, 'data')


def set_dark_theme(app: QtWidgets.QApplication):
    app.setStyle(QtWidgets.QStyleFactory.create('Fusion'))

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
    role_colors.append((QtGui.QPalette.BrightText, QtCore.Qt.red))
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


def show_message(icon_name: str,
                 title: str,
                 text: str,
                 detailed_text: str = None,
                 parent: QtWidgets.QWidget = None):
    # Since it seems impossible to set a style sheet that affects the <code> and <pre> tags, the
    # style attribute will be embedded in the text. Padding doesn't seem to work either; a space in
    # inserted instead. Also, border doesn't seem to work, hence that is has not been added.
    code_style_attr = 'style="background: #555; color: #CCC"'
    text = text.replace('<code>', f'<code {code_style_attr}>&nbsp;')
    text = text.replace('</code>', f'&nbsp;</code>')
    pre_style_attr = 'style="background: #555; color: #CCC"'
    text = text.replace('<pre>', f'<pre {pre_style_attr}>')

    # For convenience, also add nowrap to <b> tags here with another replace action.
    b_style_attr = 'style="white-space: nowrap;"'
    text = text.replace('<b>', f'<b {b_style_attr}>')

    message_box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.NoIcon, title, text,
                                        QtWidgets.QMessageBox.NoButton, parent)

    icon_path = os.path.join(data_dir, 'gui', f'{icon_name}.svg')
    icon = QtGui.QIcon(icon_path)
    char_width = message_box.fontMetrics().averageCharWidth()
    icon_size = char_width * 6
    message_box.setIconPixmap(icon.pixmap(icon.actualSize(QtCore.QSize(icon_size, icon_size))))

    if detailed_text:
        message_box.setDetailedText(detailed_text)

        # In order to customize the detailed text, it is assumed that QTextEdit is used, and that
        # a button with the action role is present.

        font_size = round(message_box.font().pointSize() * 0.75)
        for text_edit in message_box.findChildren(QtWidgets.QTextEdit):
            text_edit.setStyleSheet(
                f'QTextEdit {{ font-family: {FONT_FAMILIES}; font-size: {font_size}pt; }}')

            # If a detailed message is present, make sure the width is sufficient to show a few
            # words per line (e.g. astack traces).
            text_edit.setMinimumWidth(char_width * 60)

        for button in message_box.buttons():
            if message_box.buttonRole(button) == QtWidgets.QMessageBox.ActionRole:
                button.click()
                QtCore.QTimer.singleShot(0, button.hide)

    message_box.addButton(QtWidgets.QPushButton('Close', message_box),
                          QtWidgets.QMessageBox.AcceptRole)

    message_box.exec()


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


class SelectionStyledItemDelegate(QtWidgets.QStyledItemDelegate):

    def initStyleOption(self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex):
        super().initStyleOption(option, index)

        selected = option.state & QtWidgets.QStyle.State_Selected
        if selected:
            option.backgroundBrush = option.palette.highlight().color().darker()
            option.showDecorationSelected = True
            option.state = option.state & ~QtWidgets.QStyle.State_Selected & ~QtWidgets.QStyle.State_HasFocus


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
                    min_row = min([mi.row() for mi in dropping_model_indexes])
                    min_column = min([mi.column() for mi in dropping_model_indexes])
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
            raise exc_info[1].with_traceback(exc_info[2])

        return result


class MKDDExtenderWindow(QtWidgets.QMainWindow):

    def __init__(self,
                 parent: QtWidgets.QWidget = None,
                 flags: QtCore.Qt.WindowFlags = QtCore.Qt.WindowFlags()):
        super().__init__(parent=parent, flags=flags)

        self._red_color = QtGui.QColor(215, 40, 40)
        self._yellow_color = QtGui.QColor(239, 204, 0)

        organization = application = 'mkdd-extender'
        self._settings = QtCore.QSettings(QtCore.QSettings.IniFormat, QtCore.QSettings.UserScope,
                                          organization, application)

        self.resize(1100, 700)
        self.setWindowTitle('MKDD Extender')
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        logo_icon_path = os.path.join(data_dir, 'gui', 'logo.svg')
        logo_icon = QtGui.QIcon(logo_icon_path)
        self.setWindowIcon(logo_icon)

        error_icon_path = os.path.join(data_dir, 'gui', 'error.svg')
        self._error_icon = QtGui.QIcon(error_icon_path)
        warning_icon_path = os.path.join(data_dir, 'gui', 'warning.svg')
        self._warning_icon = QtGui.QIcon(warning_icon_path)

        menu = self.menuBar()
        file_menu = menu.addMenu('File')
        quit_action = file_menu.addAction('Quit')
        quit_action.triggered.connect(self.close)
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

        self._custom_tracks_table = QtWidgets.QTableWidget()
        self._custom_tracks_table.setItemDelegate(
            SelectionStyledItemDelegate(self._custom_tracks_table))
        self._custom_tracks_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._custom_tracks_table.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)
        self._custom_tracks_table.setColumnCount(1)
        self._custom_tracks_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch)
        self._custom_tracks_table.horizontalHeader().setSectionsClickable(False)
        self._custom_tracks_table.horizontalHeader().setSectionsMovable(False)
        self._custom_tracks_table.verticalHeader().hide()
        self._custom_tracks_table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents)
        self._custom_tracks_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self._custom_tracks_table.setWordWrap(False)
        self._custom_tracks_table_label = 'Custom Tracks'
        self._custom_tracks_table.setHorizontalHeaderLabels([self._custom_tracks_table_label])
        pages_widget = QtWidgets.QWidget()
        pages_layout = QtWidgets.QVBoxLayout(pages_widget)
        pages_layout.setContentsMargins(0, 0, 0, 0)

        PAGE_NAMES = ('Up Page', 'Down Page', 'Left Page')
        PAGE_ICON_ROTATION_ANGLES = (-90, 90, 180)
        HEADER_LABELS = ('Mushroom Cup', 'Flower Cup', 'Star Cup', 'Special Cup')

        self._page_tables = []
        for i, page_name in enumerate(PAGE_NAMES):
            dpad_icon_path = os.path.join(data_dir, 'gui', 'dpad.svg')
            dpad_icon = QtGui.QIcon(dpad_icon_path)
            page_icon = IconWidget(dpad_icon, PAGE_ICON_ROTATION_ANGLES[i])
            page_label = QtWidgets.QLabel(page_name)
            page_label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
            page_label.setAlignment(QtCore.Qt.AlignCenter)
            page_label_layout = QtWidgets.QHBoxLayout()
            page_label_layout.addStretch()
            page_label_layout.addWidget(page_icon)
            page_label_layout.addWidget(page_label)
            page_label_layout.addStretch()
            page_table = DragDropTableWidget(4, 4)
            page_table.setItemDelegate(SelectionStyledItemDelegate(page_table))
            self._page_tables.append(page_table)
            page_table.setHorizontalHeaderLabels(HEADER_LABELS)
            page_table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
            page_table.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
            page_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            page_table.horizontalHeader().setSectionsClickable(False)
            page_table.horizontalHeader().setSectionsMovable(False)
            page_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            page_table.verticalHeader().hide()
            pages_layout.addLayout(page_label_layout)
            pages_layout.addWidget(page_table)
        for page_table in self._page_tables:
            for other_page_table in self._page_tables:
                if page_table != other_page_table:
                    page_table.add_companion_table(other_page_table)
            page_table.add_companion_table(self._custom_tracks_table)
        self._splitter = QtWidgets.QSplitter()
        self._splitter.addWidget(self._custom_tracks_table)
        self._splitter.addWidget(pages_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                     QtWidgets.QSizePolicy.Expanding)

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

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addLayout(input_form_layout)
        layout.addWidget(self._splitter)
        layout.addLayout(bottom_layout)

        self.setCentralWidget(widget)

        self._restore_settings()

        self._input_iso_file_edit.textChanged.connect(self._initialize_output_filepath)
        self._custom_tracks_directory_edit.textChanged.connect(self._load_custom_tracks_directory)
        self._custom_tracks_table.itemSelectionChanged.connect(self._on_tables_itemSelectionChanged)
        for page_table in self._page_tables:
            page_table.itemSelectionChanged.connect(self._on_tables_itemSelectionChanged)
            page_table.itemChanged.connect(self._on_page_table_itemChanged)

        self._load_custom_tracks_directory(self._custom_tracks_directory_edit.get_path())

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._save_settings()

        super().closeEvent(event)

    def _save_settings(self):
        self._settings.setValue('window/geometry', self.saveGeometry())
        self._settings.setValue('window/state', self.saveState())
        self._settings.setValue('window/splitter', self._splitter.saveState())

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

        page_item_values = self._get_page_item_values()
        self._settings.setValue('miscellaneous/page_item_values', json.dumps(page_item_values))

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

        page_item_values = self._settings.value('miscellaneous/page_item_values')
        if page_item_values:
            try:
                page_item_values = json.loads(page_item_values)
            except json.decoder.JSONDecodeError:
                pass
            else:
                self._set_page_item_values(page_item_values, also_selected_state=False)

    def _open_instructions_dialog(self):
        text = textwrap.dedent(f"""\
            <h1>Instructions</h1>
            <p><h3>1. Input ISO file</h3>
            Select the path to the retail ISO file of Mario Kart: Double Dash!!.
            <br/>
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
            <a href="https://mkdd.miraheze.org">Custom Mario Kart: Double Dash Wiki!!</a>.
            </p>
            <p><h3>4. Assign custom tracks</h3>
            Once the custom tracks directory has been selected, the
            <b>{self._custom_tracks_table_label}</b> list on the left-hand side will be populated.
            Drag & drop the custom tracks onto the slots on each of the course pages
            (<b>Up Page</b>, <b>Down Page</b>, or <b>Left Page</b>) on the right-hand side.
            <br/>
            <br/>
            All the 48 slots must be filled in.
            </p>
            <p><h3>5. Build ISO file</h3>
            When ready, press the <b>{self._build_button.text()}</b> button to generate the extended
            ISO file.
            </p>
            <p><h3>6. Play</h3>
            Start the game in GameCube, Wii, or Dolphin.
            </p>
            <p><h3>7. In-game course page selection</h3>
            Use <code>Z + D-pad &lt;direction&gt;</code> while in the <b>SELECT COURSE</b> or
            <b>SELECT CUP</b> screens to switch between the different course pages.
            </p>
        """)
        show_message('info', 'Instructions', text, '', self)

    def _open_about_dialog(self):
        text = textwrap.dedent(f"""\
            <h1 style="white-space: nowrap">MKDD Extender {mkdd_extender.__version__}</h1>
            <br/>
            <small><a href="https://github.com/cristian64/mkdd-extender">
                github.com/cristian64/mkdd-extender
            </a></small>
            <br/><br/>
            {mkdd_extender.__doc__}
        """)
        show_message('logo', 'About MKDD Extender', text, '', self)

    def _initialize_output_filepath(self, text: str):
        if not text or self._output_iso_file_edit.get_path():
            return
        root, ext = os.path.splitext(text)
        if os.path.isfile(text) and ext in ('.iso', '.gcm'):
            self._output_iso_file_edit.set_path(f'{root}_extended.iso')

    def _load_custom_tracks_directory(self, dirpath: str):
        self._custom_tracks_table.setEnabled(False)
        self._custom_tracks_table.setRowCount(0)

        if dirpath:
            try:
                names = sorted(os.listdir(dirpath))
            except Exception:
                names = None

            if not names:
                if names is None:
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
                self._custom_tracks_table.setRowCount(len(names))
                for i, name in enumerate(names):
                    self._custom_tracks_table.setItem(i, 0, QtWidgets.QTableWidgetItem(name))
                self._custom_tracks_table.setEnabled(True)

        self._sync_emblems()

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

    def _on_page_table_itemChanged(self, item: QtWidgets.QTableWidgetItem):
        _ = item
        self._sync_emblems()

    def _build(self):
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

            custom_tracks = self._get_custom_track_names()
            names = []
            for item in self._get_page_items():
                name = item.text()
                if name and name in custom_tracks:
                    names.append(name)
            if len(names) != 48:
                raise mkdd_extender.MKDDExtenderError(
                    'Please make sure that all slots have been assigned to a valid custom track.')

            args = argparse.Namespace()
            args.input = input_path
            args.output = output_path
            args.tracks = []
            tracks_dirpath = self._custom_tracks_directory_edit.get_path()
            for name in names:
                args.tracks.append(os.path.join(tracks_dirpath, name))

            args.skip_banner = None
            args.skip_menu_titles = None
            args.skip_cup_names = None
            args.mix_to_mono = None
            args.sample_rate = None
            args.use_auxiliary_audio_track = None
            args.extended_memory = None
            args.skip_dol_checksum_check = None
            args.skip_filesize_check = None

            progress_dialog = ProgressDialog('Building ISO file...',
                                             lambda: mkdd_extender.extend_game(args), self)
            progress_dialog.execute_and_wait()

        except mkdd_extender.MKDDExtenderError as e:
            error_message = str(e)
        except Exception as e:
            error_message = str(e)
            exception_info = traceback.format_exc()

        if error_message is not None:
            error_message = error_message or 'Unknown error'
            mkdd_extender.log.error(error_message)

            icon_name = 'error'
            title = 'Error'
            text = error_message
            detailed_text = exception_info
        else:
            icon_name = 'success'
            title = 'Success!!'
            text = 'ISO file has been generated sucessfully.'
            detailed_text = ''

        show_message(icon_name, title, text, detailed_text, self)


def run() -> int:
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtWidgets.QApplication(sys.argv)

    set_dark_theme(app)

    window = MKDDExtenderWindow()
    window.show()

    return app.exec_()
