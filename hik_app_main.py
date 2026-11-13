#
# QMainWindow
# │
# ├── MenuBar
# │   ├── File
# │   ├── Tools
# │   └── Help
# │
# ├── ToolBar
# │
# ├── Central Widget
# │   └── Vertical Layout
# │
# │       ├── Splitter
# │       │
# │       ├── Property Tree (placeholder)
# │       │
# │       └── Camera Viewer
# │
# │       ├── Button Bar
# │       │
# │       ├── Logger
# │       │
# │       └── StatusBar
from PyQt6 import QtWidgets, QtGui, QtCore
import platform


from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

import cv2
import numpy as np
from datetime import datetime

from class_hikmicro_native import *

#Configure logger before importing classes (so they become child loggers)
from functional.class_LogHandler import *
log_file = None # do stream handler
LM = init_logger_manager(log_file,emit_record = True)
log = LM.get_logger(__name__)
log.info("Application starting...")

SHOW_DEBUG = False
__version__ = "1.0.0 beta"
__author__ = "Federico Garcia"
__creationdate__="3.11.2026"
__gitaccount__= "https://github.com/fedetony"
__CRstatement__ = """
<p>
Permission is granted to use, copy, modify and distribute this software<br>
for personal, educational and non-commercial purposes.
</p>
<p>
Modified versions remain subject to the terms of PolyForm NonCommercial 
1.0.0 license.
</p>
<p>
Commercial use, including incorporation into commercial products,<br>
services, or internal business operations, is prohibited without <br>
written permission from the author.
</p>
<p>
This software is provided "as is", without warranty of any kind.
</p>
"""
__ACKNOWLEDGEMENTS__ = """
<p>
This software includes ideas, resources and third-party assets from:<br>
• <a href="https://heroicons.com/">Heroicons</a> icon library <br>
• PyQt6 / Qt Framework<br>
• OpenCV<br>
• NumPy
</p>
<p>
Special thanks to the Linux and open-source community whose shared<br>
knowledge and examples helped solve platform-specific issues during<br>
development. 
</p>
<p>
Special thanks to creator72 for his work on hikmicro-thermal, which <br>
was a valuable technical reference for understanding HIKMICRO thermal <br>
camera acquisition under Linux.<br>
<a href="https://github.com/creator72/hikmicro-thermal/tree/main">
        Copyright © creator72 </a><br>
Licensed under the MIT License.
</p>
"""


from functional.class_treeview_functions import *
from functional.class_struct_conditioner import ConditionEngine
from class_hikstruct_builder import HIKStructBuilder
import functional.resources
from functional.class_icons import Icons
from functional.class_File_Dialogs import Dialogs
from functional.class_tracker_plot import (TrackerPlot, 
    TrackerPlotsContainer, TrackerPlotsContainerControls, TrackerWindow)


class CameraViewer(QWidget):

    mousePressed = pyqtSignal(int, int, Qt.MouseButton, Qt.KeyboardModifier)
    mouseReleased = pyqtSignal(int, int, Qt.MouseButton, Qt.KeyboardModifier)
    mouseMoved = pyqtSignal(int, int, Qt.KeyboardModifier)
    wheelMoved = pyqtSignal(int, int, int)

    def __init__(self, keep_aspect=True):
        super().__init__()
        self.setMouseTracking(True)
        self.keep_aspect = keep_aspect
        self.frame = None
        self.image_x = 0
        self.image_y = 0
        self.image_width = 0
        self.image_height = 0
        self.pixmap = None

    def set_frame(self, frame):
        if frame is None:
            return
        self.frame=frame
        self.frame_height = frame.shape[0]
        self.frame_width = frame.shape[1]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        image = QImage(rgb.data, w, h, ch * w,
            QImage.Format.Format_RGB888)

        self.pixmap = QPixmap.fromImage(image)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        if self.pixmap is None:
            return
        
        if self.keep_aspect:
            scaled = self.pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
        else:
            scaled = self.pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

        self.image_width = scaled.width()
        self.image_height = scaled.height()

        self.image_x = (self.width() - self.image_width) // 2
        self.image_y = (self.height() - self.image_height) // 2

        painter.drawPixmap(self.image_x, self.image_y, scaled)

    def widget_to_image(self, x, y):
        x -= self.image_x
        y -= self.image_y

        if (
            x < 0 or
            y < 0 or
            x >= self.image_width or
            y >= self.image_height
        ):
            return None

        # Convert back to original frame coordinates
        img_x = int(x * self.frame_width / self.image_width)
        img_y = int(y * self.frame_height / self.image_height)
        return img_x, img_y

    def mousePressEvent(self, event):
        pos = self.widget_to_image(
            int(event.position().x()),
            int(event.position().y())
        )

        if pos is None:
            return

        self.mousePressed.emit(
            pos[0], pos[1], event.button(), event.modifiers())

    def mouseReleaseEvent(self, event):
        pos = self.widget_to_image(
            int(event.position().x()),
            int(event.position().y()))

        if pos is None:
            return
        self.mouseReleased.emit(
            pos[0], pos[1], event.button(), event.modifiers())

    def mouseMoveEvent(self, event):
        pos = self.widget_to_image(
            int(event.position().x()),
            int(event.position().y()))
        if pos is None:
            return
        self.mouseMoved.emit(pos[0], pos[1], event.modifiers())

    def wheelEvent(self, event):
        pos = self.widget_to_image(
            int(event.position().x()),
            int(event.position().y()))
        if pos is None:
            return
        self.wheelMoved.emit(pos[0], pos[1], event.angleDelta().y())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.icons = Icons()
        self.dialogs = Dialogs()
        self.me_title = "HIKMICRO Native"
        self.setWindowTitle(self.me_title)
        self.resize(1400, 900)
        self.iconMain = self.icons.icon("fire solid")
        try:
            # Load About box image
            self.iconMainpixmap = QPixmap("img/hik_main.png")
        except:
            self.iconMainpixmap = None

        self.setWindowIcon(self.iconMain)
        
        self.last_log = ""
        self._last_size=None
        self.last_cam_state=None
        self.is_logging_enabled=False
        self.is_video_rec_enabled=False
        self.is_exporting_video = False
        self.event_trigger_handler={}
        self.change_origin = OriginType.NONE

        self.output_path = Path.cwd()
        self.hik_struct={'Configuration': {'value': "", 'type': 'str', 'subtype': '', 
                                          'meta': {'editable': True}}
                        }
        self.plot_trackers = {}
        self.struct_builder=HIKStructBuilder(self.hik_struct, self)
        self.all_icons_dict={}
        self._build_trackers()
        self._build_ui()
        self._build_conf_tree()
        self._connect_ui()
    
    def _build_trackers(self):
        # Tracker controls in lower panel
        self.tracker_controls = TrackerPlotsContainerControls()
        # Plot storage
        self.plot_trackers = {}
        # Floating tracker window
        self.tracker_window = TrackerWindow(
            tracker_controls=self.tracker_controls)
        
    def _build_conf_tree(self):
        self._do_evaluation=False
        self.hik_tv= TreeviewFunctions(self.hik_tree,
                                     self.hik_struct,
                                     self.struct_builder.FIELDS)
        # attach delegate to VALUE column (1)
        delegate = TypedItemDelegate(self.hik_tv)
        self.hik_tree.setItemDelegateForColumn(1, delegate)
        self.hik_tv.data_change[list,object,str,str].connect(self.on_tree_item_edited)
        self.hik_tv.struct_data_change[list,object,str,str].connect(self.on_struct_item_edited)
        #self.hik_tv.expand_to_depth(2) #333) #Expand all
        # Condition Engine
        self.hik_ce=ConditionEngine(self.hik_tv.tracker)
        self._evaluate_conditions()
        
        # Add cache tooltip, icons, backgrounds, styles
        self.hik_tv.set_icons_cache(self.all_icons_dict)
        self.hik_tv.set_style_cache(self.struct_builder.style_dict)

        # Right click Menu 
        self.hik_tv.treeviewobj.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.hik_tv.treeviewobj.customContextMenuRequested.connect(self.hik_tv._on_context_menu)
        #self.hik_tv.item_right_clicked.connect(self.on_item_right_clicked)
        
        self.hik_tv.do_refresh()

    @property
    def tracker(self):
        return self.hik_ce.tracker

    def _build_ui(self):
        #Treeview
        self.hik_tree = QtWidgets.QTreeView(self)
        
        treeGroup = QGroupBox("Configuration")
        treeLayout = QVBoxLayout()
        treeLayout.addWidget(self.hik_tree)
        treeLayout.addWidget(self.tracker_controls)
        treeGroup.setLayout(treeLayout)

        # Camera Viewer
        self.rulerH = CameraViewer(keep_aspect=False)
        self.rulerV = CameraViewer(keep_aspect=False)
        self.viewer = CameraViewer(keep_aspect=True)
        self.scaleH = CameraViewer(keep_aspect=True)
        self.scaleV = CameraViewer(keep_aspect=True)

        camera_grid = QGridLayout()
        camera_grid.addWidget(self.rulerH,0,1)
        camera_grid.addWidget(self.rulerV,1,0)
        camera_grid.addWidget(self.viewer,1,1)
        camera_grid.addWidget(self.scaleV,1,2)
        camera_grid.addWidget(self.scaleH,2,1)
        self.scaleV.setFixedWidth(120)
        self.scaleH.setFixedHeight(80)
        self.rulerV.setFixedWidth(50)
        self.rulerH.setFixedHeight(50)
 
        self.viewer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.viewerGroup = QGroupBox("Thermal Camera")
        viewerLayout = QVBoxLayout()
        viewerLayout.addLayout(camera_grid)
        self.viewerGroup.setLayout(viewerLayout)

        # Log area
        self.logger = QTextEdit()
        self.logger.setReadOnly(True)
        #self.logger.setMaximumBlockCount(1000)
        self.cam = None

        #buttons
        self.btnStartLog = QPushButton("Start Log")
        self.btnStartLog.setIcon(self.icons.icon("play"))
        self.btnStopLog = QPushButton("Stop Log")
        self.btnStopLog.setIcon(self.icons.icon("stop"))
        
        self.btnStartVidRec = QPushButton("Start Video Rec")
        self.btnStartVidRec.setIcon(self.icons.icon("video camera"))
        self.btnStopVidRec = QPushButton("Stop Video Rec")
        self.btnStopVidRec.setIcon(self.icons.icon("video camera slash"))
        self.btnExportVid = QPushButton("Export Video")
        self.btnExportVid.setIcon(self.icons.icon("tv solid"))

        buttons = QHBoxLayout()
        buttons.addWidget(self.btnStartLog)
        buttons.addWidget(self.btnStopLog)
        buttons.addStretch(1)
        buttons.addWidget(self.btnStartVidRec)
        buttons.addWidget(self.btnStopVidRec)
        buttons.addSpacing(20)
        buttons.addWidget(self.btnExportVid)

        buttons.addStretch()

        buttonsFrame = QFrame()
        buttonsnloglayout = QVBoxLayout()
        buttonsnloglayout.addLayout(buttons)
        buttonsnloglayout.addWidget(self.logger)
        buttonsFrame.setLayout(buttonsnloglayout)
        
        # Central Layout
        
        # Horizontal splitter
        viewer_splitter = QSplitter(Qt.Orientation.Horizontal)

        viewer_splitter.addWidget(treeGroup)
        viewer_splitter.addWidget(self.viewerGroup)

        viewer_splitter.setSizes([
            500,    # tree
            700    # viewer
            ])
        
        viewer_splitter.setStretchFactor(0, 0)
        viewer_splitter.setStretchFactor(1, 1)

        # Vertical splitter
        log_splitter = QSplitter(Qt.Orientation.Vertical)
        log_splitter.addWidget(viewer_splitter)
        log_splitter.addWidget(buttonsFrame)
        log_splitter.setSizes([
            600,    # tree/viewer
            300    # log buttons
            ])        
        log_splitter.setStretchFactor(0, 0)
        log_splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(log_splitter)
        central.setLayout(layout)
        self.setCentralWidget(central)

        # statusbar
        self.statusBar().showMessage("Ready")
        self.lbl_record = QLabel()
        self.lbl_log = QLabel()
        self.lbl_zoom = QLabel()
        self.lbl_probecnt = QLabel()
        self.lbl_maskcnt = QLabel()
        self.lbl_alarms = QLabel()
        self.lbl_calibration = QLabel()
        self.lbl_love = QLabel( "☕ & ❤️")
        
        self.statusBar().addPermanentWidget(self.lbl_alarms)
        self.statusBar().addPermanentWidget(self.lbl_record)
        self.statusBar().addPermanentWidget(self.lbl_log)
        self.statusBar().addPermanentWidget(self.lbl_zoom)
        self.statusBar().addPermanentWidget(self.lbl_probecnt)
        self.statusBar().addPermanentWidget(self.lbl_maskcnt)
        self.statusBar().addPermanentWidget(self.lbl_calibration)
        self.statusBar().addPermanentWidget(self.lbl_love)
        
        #Menus
        self.build_menus()
        
        #Toolbar
        self.build_toolbar()
        
        # Update Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_camera)
        self.timer.start(40)
    
    def sizeHint(self):
        return QSize(800,600)
    
    def _connect_ui(self):
        self.tracker_controls.showTrackerWindowRequested.connect(
            self._show_tracker_window
        )
        self.tracker_controls.hideTrackerWindowRequested.connect(
            self._hide_tracker_window
        )

        self.viewer.mousePressed.connect(self.on_mouse_press)
        self.viewer.mouseReleased.connect(self.on_mouse_release)
        self.viewer.mouseMoved.connect(self.on_mouse_move)
        self.viewer.wheelMoved.connect(self.on_mouse_wheel)
        self.btnStartLog.clicked.connect(lambda: self.enable_logging(True))
        self.btnStopLog.clicked.connect(lambda: self.enable_logging(False))
        self.btnStartVidRec.clicked.connect(lambda: self.enable_video_recording(True))
        self.btnStopVidRec.clicked.connect(lambda: self.enable_video_recording(False))
        self.btnExportVid.clicked.connect(self.on_export_video)
    
    def _show_tracker_window(self):
        self.tracker_window.show()
        self.tracker_window.raise_()
        self.tracker_window.activateWindow()

    def _hide_tracker_window(self):
        self.tracker_window.hide()


    @QtCore.pyqtSlot(list, object, object, str, str)
    def on_tree_item_edited_old_new(self, track, old_value, new_value, typestr, subtype):
        # Decide what to do with item value changed from user with old value
        pass

    @QtCore.pyqtSlot(list, object, str, str)
    def on_tree_item_edited(self, track, value, typestr, subtype):
        # Decide what to do with item value changed from user
        print(">>>>>>>Debug Entered Data Changed")
        if self.change_origin in ( OriginType.CAM,):
            return
        print("Debug Data Changed: ",track, value, typestr, subtype)
        self.change_origin = OriginType.QT
        try:
            self.apply_tree_change(track, value, typestr, subtype)
        finally:
            self.change_origin = OriginType.NONE
    
    @QtCore.pyqtSlot(list, object, str, str)
    def on_struct_item_edited(self, track, value, typestr, subtype):
        # Decide what to do with item value changed from code
        print(">>>>>>>>Debug Entered Internal Data Changed")
        if self.change_origin in ( OriginType.QT, OriginType.NONE):
            return
        # self.change_origin = OriginType.CAM
        self.change_origin = OriginType.NONE
        print("Debug Internal Data Changed: ",track, value, typestr, subtype)
        try:
            self._do_evaluation, self.hik_struct = self.hik_tv.set_tracked_value_to_dict(
                track,value,self.hik_tv.main_struct,subtype,False)
            if self._do_evaluation:
                self._evaluate_conditions()
        finally:
            self.change_origin = OriginType.NONE
    
    def _evaluate_conditions(self):
        """Evaluate conditions if changes were applied refresh treeview"""
        do_eval=self._do_evaluation
        self._do_evaluation=False
        
        evaluated = self.hik_ce.evaluate_conditions_in_a_node(self.hik_tv.tracker.get_root())
        if evaluated or do_eval:
            expanded = self.hik_tv.get_expanded_paths()
            selected = self.hik_tv.get_selected_paths()

            # Delay the refresh AND the restore
            def delayed_refresh():
                self.hik_tv.do_refresh()
                self.hik_tv.restore_expanded_paths(expanded)
                self.hik_tv.restore_selected_paths(selected)
                self.hik_tv.treeview_fit_to_contents(0)
                # Important Clear circular reference flag
                self.hik_tv.tracker.remove_property_from_all_nodes(self.hik_tv.tracker.get_root(),"__conditions__applied__")
            # Need to wait until all data changes are applied.
            QtCore.QTimer.singleShot(0, delayed_refresh)
    
    def apply_tree_change(self, track, value, typestr, subtype):
        if not self.cam:
            return
        # get json conf
        c_m=self.cam.configuration_manager
        conf = c_m.export_camera(self.cam)
        # Convert structure -> json conf
        path = self.struct_builder.track_to_config_path(track)
        if typestr == "color":
            value=self.struct_builder.treecolor_to_rgb(value)
        self.struct_builder.apply_dict_path(conf, path, value)
        # apply configuration
        c_m.data = conf
        c_m.apply(self.cam)
        self.change_origin = OriginType.NONE
    
    def _change_setting_trigger_evaluate_conditions(self, track, value):
        """Set a tracked value and re-evaluate conditions if the update succeeds.

        Returns True if the value was applied to the tracker.
        """
        self._do_evaluation=False
        was_set=self.hik_tv.tracker.set_value(track,value)
        if was_set:
            self._evaluate_conditions()
        # self._do_evaluation=False
        return was_set

    def refresh_struct_and_load_to_tree(self):
        ############################
        # Here is the issue, struct changes-> tracker is with initial struct... 
        # if set to old struct... cant evaluate conditions correctly.
        ############################
        self.change_origin == OriginType.QT
        self.hik_struct=self.struct_builder.build(self.cam)
        self.hik_tv.main_struct=self.hik_struct
        # self.hik_tv.tracker=TreeStructTracker(self.hik_struct)
        
        #get current expansion/selection of tree
        expanded = self.hik_tv.get_expanded_paths()
        selected = self.hik_tv.get_selected_paths()
        
        self.hik_tv.tracker.struct=self.hik_struct
        self.hik_ce.tracker=self.hik_tv.tracker
        self.hik_tv.main_struct_import_data_to_tree(self.hik_struct,self.hik_tv.modelobj,self.hik_tree)
        self._do_evaluation=True
        # Evaluates conditions and refreshes tree
        self._evaluate_conditions()
        self.delayed_restore_tree_state(expanded,selected)

    def on_mouse_move(self, x, y, modifiers):
        if self.cam is None:
            return
        # shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        # control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        # update cursor position
        self.cam.mouse_x = x
        self.cam.mouse_y = y
        # continue mask creation
        if self.cam.is_drawing_mask:
            self.cam.creating_mask(x, y)
        # continue probe creation
        elif self.cam.is_drawing_probe:
            self.cam.creating_probe(x, y)
        
    def on_mouse_wheel(self, x, y, delta):
        if self.cam is None:
            return
        # self.cam.cursor_tx=x
        # self.cam.cursor_ty=y
        self.cam.mousewheeling(x, y, delta)
    
    def on_mouse_press(self, x, y, button, modifiers):
        if self.cam is None:
            return
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        # SHIFT + LEFT = start mask
        if (button == Qt.MouseButton.LeftButton
            and shift):
            self.cam.drag_mode = "MASK"
            self.cam.begin_mask(x, y)

        # LEFT = start probe
        elif (button == Qt.MouseButton.LeftButton
              and control):
            self.cam.drag_mode = "PROBE"
            self.cam.begin_probe(x, y)

        # SHIFT + RIGHT = remove mask
        elif (button == Qt.MouseButton.RightButton
            and shift):
            self.cam.removing_mask(x, y)

        # RIGHT = remove probe
        elif (button == Qt.MouseButton.RightButton 
              and control):
            self.cam.removing_probe(x, y)
    
    def on_mouse_release(self, x, y, button, modifiers):
        if self.cam is None:
            return
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        # finish mask/probe
        if button == Qt.MouseButton.LeftButton:
            if self.cam.drag_mode == "MASK":
                self.cam.finish_mask(x, y)
            elif self.cam.drag_mode == "PROBE":
                self.cam.finish_probe(x, y)
            self.cam.drag_mode = None

    def enable_video_recording(self,enable:bool):
        if not self.cam:
            self.is_video_rec_enabled=False
            return
        else:
            self.is_video_rec_enabled = (
                self.cam.video_settings.enabled)

        if self.is_video_rec_enabled != enable:
            if enable:
                self.cam.start_video_recording() 
            else:
                self.cam.stop_video_recording()     
            self.is_video_rec_enabled = (
                self.cam.video_settings.enabled)

    def enable_logging(self,enable:bool):
        if not self.cam:
            self.is_logging_enabled=False
            return
        else:
            self.is_logging_enabled = (
                self.cam.logging_settings.enabled)

        if self.is_logging_enabled != enable:
            if enable:
                self.cam.start_logging() 
            else:
                self.cam.stop_logging()     
            self.is_logging_enabled = (
                self.cam.logging_settings.enabled)

    def build_menus(self):
        menu_file = self.menuBar().addMenu("&File")
        menu_tools = self.menuBar().addMenu("&Tools")
        menu_help = self.menuBar().addMenu("&About")

        # File menu
        connectCam = QAction("Connect Camera", self)
        connectCam.setIcon(self.icons.icon("link"))
        connectCam.triggered.connect(self.connect_camera)
        menu_file.addAction(connectCam)

        disconnectCam = QAction("Disconnect Camera", self)
        disconnectCam.setIcon(self.icons.icon("link slash"))
        disconnectCam.triggered.connect(self.disconnect_camera)
        menu_file.addAction(disconnectCam)

        menu_file.addSeparator()     
        
        outputPath = QAction("Set Output Path", self)
        outputPath.triggered.connect(self.set_output_path)
        outputPath.setIcon(self.icons.icon("folder arrow down"))
        menu_file.addAction(outputPath)

        menu_file.addSeparator()

        saveConfig = QAction("Save Configuration", self)
        saveConfig.triggered.connect(self.save_configuration)
        saveConfig.setIcon(self.icons.icon("arrow down tray"))
        menu_file.addAction(saveConfig)

        loadConfig = QAction("Load Configuration", self)
        loadConfig.triggered.connect(self.load_configuration)
        loadConfig.setIcon(self.icons.icon("arrow up tray"))
        menu_file.addAction(loadConfig)

        menu_file.addSeparator()
        actLoadPolynomial = QAction("Load Polynomial Calibration",self)
        actLoadPolynomial.triggered.connect(self.load_polynomial)
        actLoadPolynomial.setIcon(self.icons.icon("presentation chart line"))
        menu_file.addAction(actLoadPolynomial)

        actLoadTable = QAction("Load Table Calibration",self)
        actLoadTable.triggered.connect(self.load_table)
        actLoadTable.setIcon(self.icons.icon("presentation chart bar"))
        menu_file.addAction(actLoadTable)

        actsaveCalib = QAction("Save Calibration",self)
        actsaveCalib.triggered.connect(self.save_calibration)
        actsaveCalib.setIcon(self.icons.icon("document chart bar"))
        menu_file.addAction(actsaveCalib)

        menu_file.addSeparator()

        actExit = QAction("Exit", self)
        actExit.triggered.connect(self.close)
        actExit.setIcon(self.icons.icon("x circle"))
        menu_file.addAction(actExit)
        
        # Tools menu
        actSnapshot = QAction("Snapshot", self)
        actSnapshot.triggered.connect(self.snapshot)
        menu_tools.addAction(actSnapshot)
        actSnapshot.setIcon(self.icons.icon("photo"))
        menu_tools.addSeparator()

        self.add_toggle_action(
            menu_tools, "Grid", self.toggle_grid, "hashtag solid")

        self.add_toggle_action(
            menu_tools, "Hotspot", self.toggle_hotspot, "chevron up")

        self.add_toggle_action(
            menu_tools, "Coldspot", self.toggle_coldspot, "chevron down")

        self.add_toggle_action(
            menu_tools, "Cursor", self.toggle_cursor, "cursor arrow rays solid")

        self.add_toggle_action(
            menu_tools, "Masks", self.toggle_masks, "face smile")

        self.add_toggle_action(
            menu_tools, "Probes", self.toggle_probes, "eye dropper")

        self.add_toggle_action(
            menu_tools, "Center Cross", self.toggle_center_cross, "plus small")
        if SHOW_DEBUG:
            actDebugStruct = QAction("DO DEBUG", self)
            actDebugStruct.triggered.connect(self.do_debug)
            menu_tools.addAction(actDebugStruct)
        
        actAbout = QAction("About", self)
        actAbout.triggered.connect(self.show_aboutbox)
        actAbout.setIcon(self.icons.icon("fire solid"))
        menu_help.addAction(actAbout)
    
    
    def toggle_grid(self):
        if not self.cam:
            return
        self.cam.toggle_grid()
        
    def toggle_hotspot(self):
        if not self.cam:
            return
        self.cam.toggle_hotspot()
        
    def toggle_coldspot(self):
        if not self.cam:
            return
        self.cam.toggle_coldspot()
        
    def toggle_cursor(self):
        if not self.cam:
            return
        self.cam.toggle_cursor()
        
    def toggle_masks(self):
        if not self.cam:
            return
        self.cam.toggle_masks()
        
    def toggle_probes(self):
        if not self.cam:
            return
        self.cam.toggle_probes()
        
    def toggle_center_cross(self):
        if not self.cam:
            return
        self.cam.toggle_center_cross()

    @staticmethod
    def available_cameras():
        temp = HIKMICRO_NATIVE.__new__(HIKMICRO_NATIVE)
        return temp.find_correct_camera()
    
    def connect_camera(self):
        try:
            self.cam = HIKMICRO_NATIVE(log_callback=self.log)
            self.cam.set_event_callback(self.on_camera_event)
            self.log("Camera connected")
            self.last_cam_state = self.cam.state
            self.set_output_path_to_cam()
            self.refresh_struct_and_load_to_tree()
        except Exception as ex:
            self.log(f"Error while connecting: {ex}")
    
    def connect_virtual_camera(self):
        try:
            self.cam = HIKMICRO_NATIVE(camera_index = -1, log_callback=self.log)
            self.cam.set_event_callback(self.on_camera_event)
            self.log("Virtual Camera Connected")
            self.last_cam_state = self.cam.state
            self.set_output_path_to_cam()
            self.refresh_struct_and_load_to_tree()
        except Exception as ex:
            self.log(f"Error while connecting: {ex}")
    
    def disconnect_camera(self):
        if self.cam:
            self.struct_builder.clear()
            #self.refresh_struct_and_load_to_tree()
            self.hik_tv.do_refresh()
            self.cam.release()
            self.cam = None
            self.last_cam_state=None
            self.log("Camera disconnected")
    
    def disconnect_virtual_camera(self):
        if self.cam:
            self.struct_builder.clear()
            #self.refresh_struct_and_load_to_tree()
            self.hik_tv.do_refresh()
            self.cam.release()
            self.log("Virtual Camera disconnected")
            del(self.cam)
            self.cam = None
            self.last_cam_state=None

    def build_toolbar(self):
        tb = self.addToolBar("Tools")
        tb.addAction(self.icons.icon("photo solid"),"Snapshot", self.snapshot)
        tb.addSeparator()
        tb.addAction(self.icons.icon("magnifying glass plus"),"Zoom +", self.zoom_in)
        tb.addAction(self.icons.icon("magnifying glass minus"),"Zoom -", self.zoom_out)
        tb.addAction(self.icons.icon("arrows pointing out"),"Fit", self.fit_view)
    
    def zoom_in(self):
        if not self.cam:
            return
        self.cam.zoom_in()
    
    def zoom_out(self):
        if not self.cam:
            return
        self.cam.zoom_out()
    
    def fit_view(self):
        if not self.cam:
            return
        self.cam.fit_view()

    def log(self, *args):
        text = " ".join(str(x) for x in args)
        if self.last_log != text:
            self.logger.append(text)
            self.last_log = text

    def on_camera_event(self, event:EngineEvent):
        if not self.cam:
            return
        if self.change_origin == OriginType.QT:
            return
        self.change_origin = OriginType.CAM
        if event.event_type==CameraEvent.FRAME_READY:
            self.change_origin = OriginType.NONE
            return  
        if event.event_type in (CameraEvent.PROBE_ADDED,
                              CameraEvent.PROBE_REMOVED,
                              CameraEvent.MASK_ADDED,
                              CameraEvent.MASK_REMOVED,
                              #CameraEvent.CALIBRATION_CHANGED,
                              ):
            self.cam.state.probes_changed = False
            self.cam.state.masks_changed = False
            self.refresh_struct_and_load_to_tree()
            self.change_origin = OriginType.NONE
            return  
        #get current expansion/selection of tree
        expanded = self.hik_tv.get_expanded_paths()
        selected = self.hik_tv.get_selected_paths()
        try:
            eho = EventHandler(event,
                         "cam",
                         time.time(),
                         self.last_cam_state,
                         self.cam.state)
            
            self._do_evaluation=self.struct_builder.on_camera_event(
                        cam=self.cam, 
                        eho=eho,
                        st=self.tracker,
                        #self.hik_tv.main_struct,
                        log_callback=self.log)
            if self._do_evaluation:
                self._evaluate_conditions()
        finally:
            self.change_origin = OriginType.NONE
        
        c_st=self.cam.state
        if c_st.view_changed:
            self.log(event.event_type.value)

        if c_st.alarm_triggered_l:
            self.log(event.event_type.value)

        if c_st.alarm_triggered_h:
            self.log(event.event_type.value)
        
        if c_st.calibration_changed:
            self.log(event.event_type.value)
        
        if c_st.error_changed:
            self.log(event.event_type.value)
        
        if c_st.frame_ready:
            pass

        if c_st.masks_changed:
            self.log(event.event_type.value)
        
        self.delayed_restore_tree_state(expanded,selected)

    def update_camera(self):
        if self.cam is None:
            return
        try:
            # w = max(1, self.viewer.image_width)
            # h = max(1, self.viewer.image_height)
            w = max(1, self.viewer.width())
            h = max(1, self.viewer.height())
            if self._last_size != (w, h):
                self.log(f"Viewer image size: {w}x{h}")
                self.log(
                    f"widget={self.viewer.width()}x{self.viewer.height()} "
                    f"image={self.viewer.image_width}x{self.viewer.image_height}"
                )
                self._last_size=(w, h)
            self.cam.view_settings.display_height=h
            self.cam.view_settings.display_width=w
            frame = self.cam.create_display_frame(w,h)

            self.viewer.set_frame(frame)
            if self.cam.video_recorder.is_recording:
                self.cam.video_recorder.process_frame(frame)

            if self.cam.view_settings.show_scale_bar_v:
                self.scaleV.show()
                scale = self.cam.create_scale_bar(width=80, height=h, vertical=True)
                self.scaleV.set_frame(scale)
                info = self.cam.get_engine_info()
            else:
                self.scaleV.hide()
            
            if self.cam.view_settings.show_scale_bar_h:
                self.scaleH.show()
                scale = self.cam.create_scale_bar(width=w, height=80, vertical=False)
                self.scaleH.set_frame(scale)
                info = self.cam.get_engine_info()
            else:
                self.scaleH.hide()
            
            if self.cam.view_settings.show_ruler_v:
                ruler = self.cam.create_pixel_ruler_vertical(
                        display_height=self.viewer.height(),
                        width=self.rulerV.width(),
                        spacing=self.cam.view_settings.grid_spacing
                    )
                self.rulerV.set_frame(ruler)
                self.rulerV.show()
            else:
                self.rulerV.hide()
            
            if self.cam.view_settings.show_ruler_h:
                ruler = self.cam.create_pixel_ruler_horizontal(
                        display_width=self.viewer.width(), 
                        height=self.rulerH.height(), 
                        spacing=self.cam.view_settings.grid_spacing)
                self.rulerH.set_frame(ruler)
                self.rulerH.show()
            else:
                self.rulerH.hide()
            
            self.lbl_zoom.setText(f"🔍 Zoom {info['zoom']:.2f}")
            self.lbl_probecnt.setText(f"📍 Probes {info['probe_count']}")
            self.lbl_maskcnt.setText(f"🎭 Masks {info['mask_count']}")
            if info['calibration_enabled']:
                self.lbl_calibration.setText(f"🌡️ Calibration {info['calibration_type']}")
            else:
                self.lbl_calibration.setText("🌡️ Calibration OFF")

            if self.is_logging_enabled:
                elapsed = time.time()  - self.cam.log_start_time
                self.lbl_log.setText(f"📝 Logging {elapsed:.1f}s")
            else:
                self.lbl_log.setText("")
                
            if self.is_video_rec_enabled:
                elapsed = time.time() - self.cam.video_recorder.start_time
                self.lbl_record.setText(f"🔴 Recording {elapsed:.1f}s")
            else:
                self.lbl_record.setText("") 
            
            alarm_ticon={"OFF":"✅", 
                         "ON":"⚠️",
                        "HIGH":"🔥", 
                        "LOW":"🧊"}
            alarm_msg=""
            has_low_alarm=self.cam.has_low_alarms()
            has_high_alarm=self.cam.has_high_alarms()
            if has_low_alarm or has_high_alarm:
                alarm_msg = f"{alarm_ticon['ON']} ALARM "
                if has_low_alarm:
                    alarm_msg += f"{alarm_ticon['LOW']}"
                if has_high_alarm:
                    alarm_msg += f"{alarm_ticon['HIGH']}"    
                # trigger alarm routine
            else:
                alarm_msg = f"{alarm_ticon['OFF']}"
            self.lbl_alarms.setText(alarm_msg)

            # self.statusBar().showMessage(msg)
            for probe_name, probe in self.cam.probes.items():
                if isinstance(probe,ProbeArea):
                    if probe.tracker_settings.enabled:
                        self.update_probe_tracker(probe)
                    else:
                        self.remove_probe_tracker(probe_name)
            
            for tracker_name in self.plot_trackers.keys():
                if tracker_name not in list(self.cam.probes.keys()):
                    self.remove_probe_tracker(tracker_name)

        except Exception as ex:
            self.log("Camera:", ex)
    
    
    # def actual_image_size(self):
    #     return (self.image_width, self.image_height)
    
    def set_output_path(self):
        path = self.dialogs.openFolderDialog()

        if path:
            self.output_path = Path(path)
            self.set_output_path_to_cam()
            self.log("Output Path:", self.output_path)

    def set_output_path_to_cam(self):
        if self.cam:
            # self.change_origin = OriginType.CAM
            # track=self.struct_builder.get_camera_output_file_track()
            track=self.struct_builder.set_camera_output_file(
                self.cam,str(self.output_path),self.tracker)
            self.hik_tv.set_tracked_value_to_dict(track,str(self.output_path),self.hik_struct,'',True)
        msg= f"Output Path: {str(self.output_path)}"
        self.statusBar().showMessage(msg)
            # self.on_tree_item_edited(track,str(self.output_path),'str','')

    def build_snapshot_menu(self):
        snapshotMenu = QMenu(self)
        snapshotMenu.addAction("Sensor Raw", self.snapshot_sensor)
        snapshotMenu.addAction("Thermal Image", self.snapshot_image)
        snapshotMenu.addAction("Display Image", self.snapshot_display)
        snapshotMenu.addAction("Camera Report", self.snapshot_camera_report)
        snapshotMenu.addAction("Full Workspace", self.snapshot_workspace)
        return snapshotMenu
    
    @staticmethod
    def get_timestamped_filename(filename):
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{stem}_{timestamp}{suffix}"

    def snapshot(self):
        snapshotMenu = self.build_snapshot_menu()
        snapshotMenu.exec(QCursor.pos())
    
    def snapshot_sensor(self):
        if not self.cam:
            return
        filename = (self.output_path / "sensor_raw.npy")
        filename = self.get_timestamped_filename(filename)
        self.cam.snapshot_sensor(str(filename))
        self.log("Saved", filename)
    
    def snapshot_image(self):
        if not self.cam:
            return
        # filename = (self.output_path / f"thermal_{int(time.time())}.png")
        filename = (self.output_path / "thermal.png")
        filename = self.get_timestamped_filename(filename)
        self.cam.snapshot_raw(str(filename))
        self.log("Saved", filename)
    
    def snapshot_display(self):
        if not self.cam:
            return
        #filename = (self.output_path / f"display_{int(time.time())}.png")
        filename = (self.output_path / "display.png")
        filename = self.get_timestamped_filename(filename)
        self.cam.snapshot_report(str(filename))
        self.log("Saved", filename)
    
    def snapshot_camera_report(self):
        if not self.cam:
            return
        #filename = (self.output_path / f"camera_report_{int(time.time())}.png")
        filename = (self.output_path / "camera_report.png")
        filename = self.get_timestamped_filename(filename)
        # viewer image
        self.cam.snapshot_camera_report(str(filename))
        self.log("Saved",filename)

    def snapshot_workspace(self):
        #filename = (self.output_path / f"workspace_{int(time.time())}.png")
        filename = (self.output_path / "workspace.png")
        filename = self.get_timestamped_filename(filename)
        pixmap = self.centralWidget().grab()
        pixmap.save(str(filename))
        self.log("Saved", filename)

    def save_calibration(self):
        if not self.cam:
            return
        save_filter = None
        if self.cam.calibration.calibration_type == "POLYNOMIAL":
            save_filter = 11
        elif self.cam.calibration.calibration_type == "TABLE":
            save_filter = 12 
        if save_filter is not None:
            filename = self.dialogs.saveFileDialog(
                filter=save_filter,
                title="Save Configuration"
            )
            self.cam.save_calibration(filename)

    def load_polynomial(self):
        if not self.cam:
            return
        filename = self.dialogs.openFileNameDialog(
            filter=11,  # Or add a dedicated NPY filter
            title="Load Polynomial"
        )

        if filename:
            self.cam.load_calibration_polynomial(filename)
            self.log("Loaded polynomial", filename)

    def load_table(self):
        if not self.cam:
            return
        filename = self.dialogs.openFileNameDialog(
            filter=12,
            title="Load Table"
        )

        if filename:
            self.cam.load_calibration_table(filename)
            self.log("Loaded table", filename)

    def toggle_attr(self, attr):
        value = getattr(self.cam, attr)
        setattr(self.cam, attr, not value)
        self.cam.notify_settings_changed()

    def add_toggle_action(self, menu, text, callback,icon_name=''):
        act = QAction(text,self)
        if icon_name:
            act.setIcon(self.icons.icon(icon_name))
        act.triggered.connect(callback)
        menu.addAction(act)

    def save_configuration(self):
        if self.cam is None:
            return
        filename = self.dialogs.saveFileDialog(
            filter=6,
            title="Save Configuration"
        )
        if not filename:
            return
        try:
            self.cam.save_config(filename)
            self.log(f"Configuration saved: {filename}")
        except Exception as ex:
            self.log(f"Error saving configuration: {ex}")
    
    def load_configuration(self):
        if self.cam is None:
            return

        filename = self.dialogs.openFileNameDialog(
            filter=6,
            title="Load Configuration"
        )

        if not filename:
            return

        try:
            self.cam.load_config(filename)
            self.log(f"Configuration loaded: {filename}")
            self.refresh_struct_and_load_to_tree()
        except Exception as ex:
            self.log(f"Error loading configuration: {ex}")
    
    def delayed_restore_tree_state(self, expanded, selected):
        #self.hik_tv.do_refresh()
        # restore selection expansion
        n_expanded=[]
        for path in expanded:
            if self.tracker.get_value(path):
                n_expanded.append(path)
        self.hik_tv.restore_expanded_paths(n_expanded)
        n_selected=[]
        for path in selected:
            if self.tracker.get_value(path):
                n_selected.append(path)

        QtCore.QTimer.singleShot(
            33,
            lambda: self._restore_tree_state(n_expanded, n_selected)
        )

    def _restore_tree_state(self, expanded, selected):
        self.hik_tv.restore_expanded_paths(expanded)
        self.hik_tv.restore_selected_paths(selected)
        self.hik_tv.treeview_fit_to_contents(0)
    
    def do_debug(self):
        if not self.cam:
            print("No cam")
            return
        # root = QtCore.QModelIndex()
        # model = self.hik_tv.modelobj
        # rows = model.rowCount(root)
        # print("expanded root:", self.hik_tv.treeviewobj.isExpanded(root),f"rows: {rows}")
        # for r in range(rows):
        #         child = model.index(r, 0, root)
        #         name = model.data(child, QtCore.Qt.ItemDataRole.DisplayRole)
        #         print(child, [name])
        
        
        # idx = self.hik_tv.treeviewobj.currentIndex()
        
        # print("current:", idx.data())
        # print("expanded:", self.hik_tv.treeviewobj.isExpanded(idx))

        # expanded = self.hik_tv.get_expanded_paths()
        # print("------------------- Debug Expanded:",expanded)
        # model = self.hik_tv.modelobj
        # for row in range(model.rowCount()):
        #     idx = model.index(row, 0)
        #     print(
        #         idx.data(),
        #         "expanded =", self.hik_tv.treeviewobj.isExpanded(idx)
        #     )
        
        # test= [['Configuration'], ['Configuration', 'Logging'], ['Configuration', 'Calibration']]
        # self.hik_tv.restore_expanded_paths(test)
        print("Horizontal\n",
            "viewer.width()", self.viewer.width(),
            "image_width", self.viewer.image_width,
            "rulerH.width()", self.rulerH.width()
        )
        print("Vertical\n",
            "viewer.height()", self.viewer.height(),
            "image_height", self.viewer.image_height,
            "rulerV.height()", self.rulerV.height()
        )
    


    def show_aboutbox(self):

        year = datetime.now().year

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"About {self.me_title}")
        dlg.setWindowIcon(self.iconMain)

        layout = QtWidgets.QVBoxLayout(dlg)

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        header = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel()
        if self.iconMainpixmap:
            icon_label.setPixmap(
                self.iconMainpixmap.scaled(
                    128,
                    128,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
            )

        header.addWidget(icon_label)

        info = QtWidgets.QLabel(
            f"""
            <h2>{self.me_title}</h2>
            <p><b>Version:</b> {__version__}</p>
            <p><b>Author:</b> {__author__}</p>
            <p><b>Created:</b> {__creationdate__}</p>
            <p>
                <a href="{__gitaccount__}">
                    GitHub
                </a>
            </p>
            """
        )

        info.setOpenExternalLinks(True)

        header.addWidget(info)
        header.addStretch()

        layout.addLayout(header)

        # -------------------------------------------------
        # Description
        # -------------------------------------------------

        text = QtWidgets.QLabel("""
            <p>
            With coffee and love ❤️ by F.G.
            </p>

            <p>
            Thank you for using this application.
            </p>
        """)

        text.setWordWrap(True)

        layout.addWidget(text)

        # -------------------------------------------------
        # Technical info
        # -------------------------------------------------

        tech = QtWidgets.QTextEdit()
        tech.setReadOnly(True)
        tech.setMaximumHeight(120)

        tech.setPlainText(
            f"""
    Application : {self.me_title}
    Version     : {__version__}
    Python      : {platform.python_version()}
    Qt          : {QtCore.QT_VERSION_STR}
    PyQt        : {QtCore.PYQT_VERSION_STR}
    Platform    : {platform.platform()}
    """
        )

        layout.addWidget(tech)

        # -------------------------------------------------
        # Footer
        # -------------------------------------------------

        footer = QtWidgets.QLabel(
            f"""
            <small>
            <b>Copyright © {year} {__author__}</b><br>
            <b>All Rights Reserved</b><br>
            {__CRstatement__}
            <b>ACKNOWLEDGEMENTS:</b>
            {__ACKNOWLEDGEMENTS__}
            </small>
            """
        )

        footer.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(footer)

        # -------------------------------------------------

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
        )

        buttons.accepted.connect(dlg.accept)

        layout.addWidget(buttons)

        dlg.resize(550, 400)

        dlg.exec()
    
    def on_export_video(self):
        no_cam=False
        if not self.cam:
            self.log("You need a camara acative to extract the export settings!")
            no_cam=True
            self.connect_virtual_camera()
            self.load_configuration()

        npz_file = self.dialogs.openFileNameDialog(
            filter=9,
            title="Open Recording"
        )

        if not npz_file:
            return
        # set default name
        self.dialogs.default_file_name=npz_file.replace(".npz", ".mp4")
        
        mp4_file = self.dialogs.saveFileDialog(
            filter=10,
            title="Export Video"
        )

        if not mp4_file:
            return
        try:
            self.is_exporting_video=True
            self.log(
                f"Exporting:\n"
                f"{npz_file}\n->\n"
                f"{mp4_file}"
            )
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.cam.export_video(npz_file, mp4_file)
            self.log(f"Export complete:\n{mp4_file}")

        except Exception as ex:
            self.log(f"Video export failed:\n{ex}")

        finally:
            QApplication.restoreOverrideCursor()
            self.is_exporting_video=False
            if no_cam:
                self.disconnect_virtual_camera()
    # -------------------------------------------------
    # Trackers
    # -------------------------------------------------
    def create_probe_tracker(self, probe:ProbeArea):
        plot = TrackerPlot()
        plot.set_title(probe.name)
        plot.set_x_label("Time", "s")
        plot.set_y_label(probe.tracker_settings.label, 
                         probe.text_settings.unit)

        ts = probe.tracker_settings
        plot.ensure_curve(probe.name, "Average",
            self._to_qcolor(ts.color_avg), 
            ts.line_width, ts.line_style)

        plot.ensure_curve(probe.name, "Minimum", 
            self._to_qcolor(ts.color_min), 
            ts.line_width, ts.line_style)

        plot.ensure_curve(probe.name, "Maximum",
            self._to_qcolor(ts.color_max), 
            ts.line_width, ts.line_style)
        
        self.tracker_window.container.add_plot(plot)
        self.plot_trackers[probe.name] = plot
        self.load_probe_history(plot, probe)

        return plot
    
    def load_probe_history(self, plot:TrackerPlot, probe:ProbeArea):
        if not probe.history:
            return
        history = list(probe.history)
        if not history:
            return
        t0 = history[0][0]
        for ts, avg, mn, mx in history:
            t = ts - t0
            avg, mn, mx = self._calibrate_point(avg, mn, mx, probe)
            plot.add_point(probe.name, "Average", t, avg)
            plot.add_point(probe.name, "Minimum", t, mn)
            plot.add_point(probe.name, "Maximum", t, mx)
    
    def refresh_probe_tracker(self, probe:ProbeArea):
        if not probe.history:
            return
        plot = self.plot_trackers.get(probe.name)

        if plot is None:
            plot = self.create_probe_tracker(probe)
        plot.clear_data()
        t0 = probe.history[0][0]
        for ts, avg, mn, mx in probe.history:
            t = ts - t0
            avg, mn, mx = self._calibrate_point(avg, mn, mx, probe)
            plot.add_point(probe.name, "Average", t, avg)
            plot.add_point(probe.name, "Minimum", t, mn)
            plot.add_point(probe.name, "Maximum", t, mx)
    
    def update_probe_tracker(self, probe:ProbeArea):
        if not probe.history:
            return
        plot = self.plot_trackers.get(probe.name)
        if plot is None:
            plot = self.create_probe_tracker(probe)
        ts, avg, mn, mx = probe.history[-1]
        avg, mn, mx = self._calibrate_point(avg, mn, mx, probe)

        if not hasattr(plot, "_t0"):
            plot._t0 = ts
        t = ts - plot._t0

        plot.add_point(probe.name, "Average", t, avg)
        plot.add_point(probe.name, "Minimum", t, mn)
        plot.add_point(probe.name, "Maximum", t, mx)
        
        self.apply_probe_tracker_style(plot,probe)
    
    def _calibrate_point(self,avg, mn, mx, probe:ProbeArea):
        if (not probe.tracker_settings.apply_calibration 
            or probe.text_settings.unit == "Raw"):
            return avg, mn, mx
        cavg = self.cam.raw_to_celsius(avg)
        cavg = self.cam.celsius_to_unit(cavg,probe.text_settings.unit)
        cmn = self.cam.raw_to_celsius(mn)
        cmn = self.cam.celsius_to_unit(cmn,probe.text_settings.unit)
        cmx = self.cam.raw_to_celsius(mx)
        cmx = self.cam.celsius_to_unit(cmx,probe.text_settings.unit)
        return cavg, cmn, cmx
    
    def remove_probe_tracker(self, probe_name):
        plot = self.plot_trackers.pop(probe_name, None)
        if plot:
            self.tracker_window.container.remove_plot(plot)
    
    def apply_probe_tracker_style(self, 
            plot: TrackerPlot, probe: ProbeArea):

        ts = probe.tracker_settings
        if probe.high_alarm.active and probe.high_alarm.enabled:
            plot.update_curve_style(
                probe.name,
                "Average",
                color=self._to_qcolor(probe.high_alarm.color),
                width=ts.line_width+2,
                style="dash" if probe.high_alarm.blink else ts.line_style
            )
            plot.set_title(probe.name)
        elif probe.low_alarm.active and probe.low_alarm.enabled:
            plot.update_curve_style(
                probe.name,
                "Average",
                color=self._to_qcolor(probe.low_alarm.color),
                width=ts.line_width+2,
                style="dash" if probe.low_alarm.blink else ts.line_style
            )
        else:
            plot.update_curve_style(
                probe.name,
                "Average",
                color=self._to_qcolor(ts.color_avg),
                width=ts.line_width,
                style=ts.line_style
            )
        title=probe.name
        if probe.high_alarm.active and probe.high_alarm.enabled:
            title += f" {probe.high_alarm.alarm_type}({probe.high_alarm.message})" 
        if probe.low_alarm.active and probe.low_alarm.enabled:
            title += f" {probe.low_alarm.alarm_type}({probe.low_alarm.message})"

        plot.set_title(title)

        plot.update_curve_style(
            probe.name,
            "Minimum",
            color=self._to_qcolor(ts.color_min),
            width=ts.line_width,
            style=ts.line_style
        )

        plot.update_curve_style(
            probe.name,
            "Maximum",
            color=self._to_qcolor(ts.color_max),
            width=ts.line_width,
            style=ts.line_style
        )
        
        plot.set_y_label(probe.tracker_settings.label, 
                         probe.text_settings.unit)
        
    
    
    def _to_qcolor(self,color):
        color=self.struct_builder.rgb_to_treecolor(color)
        if isinstance(color, QtGui.QColor):
            return color

        if isinstance(color, str):
            return QtGui.QColor(color)

        if isinstance(color, (tuple, list)):
            if len(color) == 3:
                return QtGui.QColor(*color)

            if len(color) == 4:
                return QtGui.QColor(*color)

        return QtGui.QColor("black")

        
        

if __name__ == "__main__":

    app = QApplication([])
    win = MainWindow()
    win.show()
    app.exec()