#################
# Dialog Class Helper
# Morernized: 02.01.2026
# With coffee and love by F.G 
################
from PyQt6 import QtWidgets

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.QtWidgets import QMessageBox, QPushButton
import os

class Dialogs(QWidget):
    def __init__(self):
        super().__init__()
        self.options = QFileDialog.Option.DontUseNativeDialog

        # Start in user's home directory
        self.dir = os.path.expanduser("~")
        self.default_file_name = None

        # Centralized filter definitions
        self.filter_map = {
            0: ("All Files (*);;Gcode Files (*.gcode);;Linux Gcode Files (*.ngc);;Linux Gcode Files (*.nc)",
                "Gcode Files (*.gcode)"),
            1: ("All Files (*);;Images (*.png *.xpm *.jpg *.bmp)",
                "Images (*.png *.xpm *.jpg *.bmp)"),
            2: ("All Files (*);;Text Files (*.txt)",
                "Text Files (*.txt)"),
            3: ("All Files (*);;Yaml Files (*.yml);;Json Files (*.json)",
                "Yaml Files (*.yml)"),
            4: ("All Files (*);;Gcode Files (*.gcode);;Linux Gcode Files (*.ngc);;Linux Gcode Files (*.nc);;Action Files (*.acode)",
                "Gcode Files (*.gcode)"),
            5: ("All Files (*);;Batton Configuration Files (*.btncfg)",
                "Batton Configuration Files (*.btncfg)"),
            6: ("Json Files (*.json)",
                "Json Files (*.json)"),
            7: ("Yaml Files (*.yml)",
                "Yaml Files (*.yml)"),
            8: ("All Files (*);;SVG Files (*.svg)",
                "SVG Files (*.svg)"),
            9: ("All Files (*);;NPZ Recording Files (*.npz)",
                "NPZ Recording Files (*.npz)"),
            10: ("All Files (*);;MP4 Video Files (*.mp4)",
                "MP4 Video Files (*.mp4)"),
            11: ("NumPy Files (*.npy)", "NumPy Files (*.npy)"),
            12: ("CSV Files (*.csv)", "CSV Files (*.csv)"),
        }

        self.default_filter = ("All Files (*)", "All Files (*)")
        self.last_paths = {}

    # ---------------------------------------------------------
    # Internal helper: get filter tuple
    # ---------------------------------------------------------
    def get_filter(self, filter_id):
        return self.filter_map.get(filter_id, self.default_filter)

    # ---------------------------------------------------------
    # Internal helper: update last-used directory
    # ---------------------------------------------------------
    def _update_last_dir(self, filter_id, path):
        if not path:
            return
        directory = os.path.dirname(path)
        if os.path.isdir(directory):
            self.last_paths[filter_id] = directory
            self.dir = directory  #  update global fallback too

    # ---------------------------------------------------------
    # Unified dialog handler
    # ---------------------------------------------------------
    def _open_dialog(self, mode, filter_id=0, title=None):
        filters, selected = self.get_filter(filter_id)

        # Determine starting directory
        start_dir = self.last_paths.get(filter_id, self.dir)

        # Validate directory
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = self.dir
        
        if not start_dir or not os.path.isdir(start_dir):
            start_dir = os.path.expanduser("~")  # final fallback

        # --- OPEN SINGLE FILE ---
        if mode == "open_single":
            if title is None:
                title = "Open File"
            fileName, _ = QFileDialog.getOpenFileName(
                self, title, start_dir, filters, selected, options=self.options
            )
            if fileName:
                self._update_last_dir(filter_id, fileName)
            return fileName or None

        # --- OPEN MULTIPLE FILES ---
        if mode == "open_multi":
            if title is None:
                title = "Open Files"
            files, _ = QFileDialog.getOpenFileNames(
                self, title, start_dir, filters, selected, options=self.options
            )
            if files:
                self._update_last_dir(filter_id, files[0])
            return files or None

        # --- SAVE FILE ---
        if mode == "save":
            if title is None:
                title = "Save File"
            if self.default_file_name:
                start_dir=os.path.join(start_dir,self.default_file_name)
                self.default_file_name = None
            fileName, _ = QFileDialog.getSaveFileName(
                self, title, start_dir, filters, selected, options=self.options
            )
            if fileName:
                self._update_last_dir(filter_id, fileName)
            return fileName or None

        return None

    # ---------------------------------------------------------
    # Public API for files
    # ---------------------------------------------------------
    def openFileNameDialog(self, filter=0,title=None):
        """Opens a one File dialog"""
        return self._open_dialog("open_single", filter, title)

    def openFileNamesDialog(self, filter=0, title=None):
        """Opens multiple File dialog"""
        return self._open_dialog("open_multi", filter, title)

    def saveFileDialog(self, filter=0, title=None):
        """Opens a save File dialog"""
        return self._open_dialog("save", filter, title)

    # ---------------------------------------------------------
    # Public API for folders
    # ---------------------------------------------------------
    def openFolderDialog(self):
        """Opens a Folder selection"""
        start_dir = self.last_paths.get("folder", self.dir)
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", start_dir, options=self.options
        )
        if folder:
            self._update_last_dir("folder", folder)
        return folder or None

    def openFolderUrlDialog(self):
        """Opens URLS Example:
        result = dialogs.openFolderUrlDialog()
        if result:
            print("Folder path:", result["path"])
            print("Folder URL:", result["url"])
        
        Returns:
            dict: results
        """
        start_dir = self.last_paths.get("folder", self.dir)
        url = QFileDialog.getExistingDirectoryUrl(
            self,
            "Select Folder",
            QUrl.fromLocalFile(start_dir),
            options=self.options
        )
        if not url.isValid():
            return None
        folder_path = url.toLocalFile()
        # update last directory
        self._update_last_dir("folder", folder_path)
        return {
            "path": folder_path,
            "url": url
        }
    
    def openFoldersUrlDialog(self):
        """Opens URLS Example:
        result = dialogs.openFoldersUrlDialog()
        if result:
            print(result["paths"])
            print(result["urls"])

        Returns:
            dict: results
        """
        start_dir = self.last_paths.get("folder", self.dir)
        urls = QFileDialog.getExistingDirectoriesUrl(
            self,
            "Select Folders",
            QUrl.fromLocalFile(start_dir),
            options=self.options
        )
        if not urls:
            return None
        folders = [u.toLocalFile() for u in urls]
        # update last directory using the first folder
        self._update_last_dir("folder", folders[0])
        return {
            "paths": folders,
            "urls": urls
        }


class MsgBoxHelper(QWidget):
    def __init__(self):
        super().__init__()

    def show(
        self,
        title,
        text,
        icon=QMessageBox.Icon.Information,
        buttons=None,
        default=None,
        detailed_text=None,
        informative_text=None,
    ):
        """
        buttons: list of tuples -> [("OK", AcceptRole), ("Cancel", RejectRole)]
        default: label of default button
        returns: (label, role)
        """

        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(icon)
        msg.setText(text)

        if informative_text:
            msg.setInformativeText(informative_text)

        if detailed_text:
            msg.setDetailedText(detailed_text)

        btn_map = {}

        # Add custom buttons
        if buttons:
            for label, role in buttons:
                b = QPushButton(label)
                msg.addButton(b, role)
                btn_map[b] = (label, role)

                if default and label == default:
                    msg.setDefaultButton(b)

        else:
            # If no buttons provided → default OK
            b = QPushButton("OK")
            msg.addButton(b, QMessageBox.ButtonRole.AcceptRole)
            btn_map[b] = ("OK", QMessageBox.ButtonRole.AcceptRole)
            msg.setDefaultButton(b)

        msg.exec()

        clicked = msg.clickedButton()
        return btn_map.get(clicked, (None, None))



class DeleteConfirmDialog(QtWidgets.QDialog):
    def __init__(self, name, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Delete Interface")
        self.setModal(True)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Horizontal layout for icon + text
        top_layout = QtWidgets.QHBoxLayout()

        # Warning icon (same as QMessageBox)
        icon_label = QtWidgets.QLabel()
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(48, 48))
        top_layout.addWidget(icon_label)

        # Message text
        text_label = QtWidgets.QLabel(
            f"To delete '<b>{name}</b>', type <b>DELETE</b> below:"
        )
        text_label.setWordWrap(True)
        top_layout.addWidget(text_label)

        layout.addLayout(top_layout)

        # Input field
        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setPlaceholderText("Type DELETE to confirm")
        self.line_edit.setMinimumWidth(300)
        self.line_edit.setMinimumHeight(28)
        layout.addWidget(self.line_edit)

        # OK / Cancel buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def confirmed(self):
        """Return True only if user typed DELETE."""
        return self.line_edit.text().strip().upper() == "DELETE"

