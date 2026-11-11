from PyQt6 import QtGui
import pyqtgraph as pg

from PyQt6 import QtWidgets, QtCore
from PyQt6 import QtWidgets, QtCore

from functional.class_icons import Icons
icons=Icons()

class TrackerPlotsContainerControls(QtWidgets.QWidget):
    """
    A compact control bar for tracker plots.
    Contains:
      - Show/Hide Tracker Window button
    Does NOT contain the actual plots.
    """

    showTrackerWindowRequested = QtCore.pyqtSignal()
    hideTrackerWindowRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_icons_dict = {
                            "Show_tracker": icons.icon("tv"),
                            }
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Sort label + combo
        layout.addWidget(QtWidgets.QLabel("Trackers:"))
        layout.addStretch()

        self.icon_on  = self._tint_icon(self.all_icons_dict["Show_tracker"], QtGui.QColor("#00cc66"))
        self.icon_off = self.all_icons_dict["Show_tracker"] 
        #self._tint_icon(self.all_icons_dict["Show_tracker"], QtGui.QColor("#888888"))

        # Show/Hide button
        self.toggle_button = QtWidgets.QPushButton()
        self.toggle_button.setToolTip("Show Tracker Window")
        self.toggle_button.setIcon(self.icon_off)
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self.on_toggle)
        layout.addWidget(self.toggle_button)

    # ---------------------------------------------------------
    # Button toggles between show/hide
    # ---------------------------------------------------------
    def on_toggle(self, checked):
        if checked:
            self.toggle_button.setIcon(self.icon_on)
            self.toggle_button.setToolTip("Hide Tracker Window")
            self.showTrackerWindowRequested.emit()
        else:
            self.toggle_button.setIcon(self.icon_off)
            self.toggle_button.setToolTip("Show Tracker Window")
            self.hideTrackerWindowRequested.emit()

    
    def _tint_icon(self, icon: QtGui.QIcon, color: QtGui.QColor):
        pixmap = icon.pixmap(32, 32)
        tinted = QtGui.QPixmap(pixmap.size())
        tinted.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(tinted)
        painter.drawPixmap(0, 0, pixmap)

        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()

        return QtGui.QIcon(tinted)


    # ---------------------------------------------------------
    # External API to sync button state
    # ---------------------------------------------------------
    def set_window_visible(self, visible: bool):
        self.toggle_button.setChecked(visible)

class TrackerWindow(QtWidgets.QMainWindow):
    def __init__(self,tracker_controls:TrackerPlotsContainerControls=None):
        super().__init__()
        self.setWindowTitle("Trackers")
        self.resize(500, 600)
        self.tracker_controls=tracker_controls

        # The real plot container
        self.container = TrackerPlotsContainer()
        self.setCentralWidget(self.container)

        # Make it behave like a tool window
        self.setWindowFlags(
            self.windowFlags() |
            QtCore.Qt.WindowType.Tool |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
    
    def closeEvent(self, event):
        # Notify controls that the window is no longer visible
        if isinstance(self.tracker_controls,TrackerPlotsContainerControls):
            self.tracker_controls.set_window_visible(False)
        # if hasattr(self.parent(), "tracker_controls"):
        #    self.parent().tracker_controls.set_window_visible(False)
        super().closeEvent(event)


class TrackerPlotsContainer(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        # Optional header with sort options
        self.header = QtWidgets.QHBoxLayout()
        self.header.setContentsMargins(4, 4, 4, 4)
        self.header.setSpacing(6)

        # Sort dropdown
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["Creation order", "Title A→Z", "Title Z→A"])
        self.creation_order = []
        self.sort_combo.currentIndexChanged.connect(self.sort_plots)
        self.header.addWidget(QtWidgets.QLabel("Sort:"))
        self.header.addWidget(self.sort_combo)
        self.header.addStretch()

        self.layout.addLayout(self.header)

        # Placeholder
        self.placeholder = QtWidgets.QLabel("No tracker plots loaded")
        self.placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #666; font-style: italic;")
        self.layout.addWidget(self.placeholder)

        # Internal list of plot widgets
        self.plots = []

    # ---------------------------------------------------------
    # Add a plot
    # ---------------------------------------------------------
    def add_plot(self, plot_widget):
        if self.placeholder is not None:
            self.layout.removeWidget(self.placeholder)
            self.placeholder.deleteLater()
            self.placeholder = None

        self.plots.append(plot_widget)
        self.creation_order.append(plot_widget)
        self.layout.addWidget(plot_widget)

    # ---------------------------------------------------------
    # Remove a specific plot
    # ---------------------------------------------------------
    def remove_plot(self, plot_widget):
        if plot_widget in self.plots:
            self.plots.remove(plot_widget)
            self.creation_order.remove(plot_widget)
            self.layout.removeWidget(plot_widget)
            plot_widget.setParent(None)

        if not self.plots:
            self._restore_placeholder()

    # ---------------------------------------------------------
    # Remove by index
    # ---------------------------------------------------------
    def remove_plot_by_index(self, index):
        if 0 <= index < len(self.plots):
            self.remove_plot(self.plots[index])

    # ---------------------------------------------------------
    # Clear all plots
    # ---------------------------------------------------------
    def clear(self):
        for plot in self.plots:
            self.layout.removeWidget(plot)
            plot.setParent(None)

        self.plots.clear()
        self.creation_order.clear()
        self._restore_placeholder()

    # ---------------------------------------------------------
    # Sorting logic
    # ---------------------------------------------------------
    def sort_plots(self):
        if not self.plots:
            return

        mode = self.sort_combo.currentText()

        if mode == "Creation order":
            # Restore original order
            self.plots = self.creation_order.copy()

        elif mode == "Title A→Z":
            self.plots.sort(key=lambda p: p.title)

        elif mode == "Title Z→A":
            self.plots.sort(key=lambda p: p.title, reverse=True)

        # Rebuild layout
        for plot in self.plots:
            self.layout.removeWidget(plot)
            self.layout.addWidget(plot)



    # ---------------------------------------------------------
    # Restore placeholder
    # ---------------------------------------------------------
    def _restore_placeholder(self):
        self.placeholder = QtWidgets.QLabel("No tracker plots loaded")
        self.placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #666; font-style: italic;")
        self.layout.addWidget(self.placeholder)


class TrackerPlot(pg.PlotWidget):
    """
    A general-purpose multi-object, multi-property tracker plot.
    Dynamically add/remove curves, change styles, and feed data in real time.
    """

    def __init__(self, parent=None, max_points=500):
        super().__init__(parent)

        # --- Outer layout ---
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # --- The actual plot widget ---
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Value")
        layout.addWidget(self.plot, stretch=4)

        # --- Legend placed OUTSIDE the plot ---
        self.legend = pg.LegendItem()
        self.legend.setFixedWidth(120)

        # Legend must live inside a QGraphicsView
        legend_view = QtWidgets.QGraphicsView()
        legend_view.setScene(QtWidgets.QGraphicsScene())
        legend_view.scene().addItem(self.legend)
        legend_view.setFixedWidth(140)
        legend_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        legend_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(legend_view, stretch=1)

        # --- Data storage ---
        self.max_points = max_points
        self.curves = {}
        self.data = {}
        self.styles = {}
        
    # ---------------------------------------------------------
    # Background
    # ---------------------------------------------------------
    def set_background(self, color=None):
        if color is not None:
            self.setBackground(QtGui.QColor(color))

    # ---------------------------------------------------------
    # Curve creation
    # ---------------------------------------------------------
    def ensure_curve(self, obj_id, prop, color="#000000", width=2, style="solid"):
        """Adds or creates object and property with the style if it does not exist"""
        if obj_id not in self.curves:
            self.curves[obj_id] = {}
            self.data[obj_id] = {}
            self.styles[obj_id] = {}

        if prop not in self.curves[obj_id]:
            pen = self._make_pen(color, width, style)
            curve_name = f"{obj_id}:{prop}"

            curve = self.plot.plot(pen=pen, name=curve_name)

            self.curves[obj_id][prop] = curve
            self.data[obj_id][prop] = {"x": [], "y": []}
            self.styles[obj_id][prop] = {"color": color, "width": width, "style": style}

            # Add to legend (legend already exists)
            self.legend.addItem(curve, curve_name)

    # ---------------------------------------------------------
    # Add data
    # ---------------------------------------------------------
    def add_point(self, obj_id, prop, t, value):
        sty = self.styles.get(obj_id, {}).get(prop, {"color":"#000000","width":2,"style":"solid"})
        self.ensure_curve(obj_id, prop, sty["color"], sty["width"], sty["style"])

        d = self.data[obj_id][prop]
        d["x"].append(t)
        d["y"].append(value)

        # Moving window
        if len(d["x"]) > self.max_points:
            d["x"] = d["x"][-self.max_points:]
            d["y"] = d["y"][-self.max_points:]

        self.curves[obj_id][prop].setData(d["x"], d["y"])
    
    def clear_data(self):
        for obj_id in self.data:
            for prop in self.data[obj_id]:
                self.data[obj_id][prop]["x"].clear()
                self.data[obj_id][prop]["y"].clear()

                self.curves[obj_id][prop].setData([], [])

    # ---------------------------------------------------------
    # Remove a single curve
    # ---------------------------------------------------------
    def remove_curve(self, obj_id: str, prop: str):
        """
        Remove a single property curve from an object.
        """

        if obj_id in self.curves and prop in self.curves[obj_id]:
            curve = self.curves[obj_id][prop]
            curve_name = f"{obj_id}:{prop}"

            # Remove curve from the plot
            self.plot.removeItem(curve)

            # Remove from legend
            try:
                self.legend.removeItem(curve_name)
            except Exception:
                pass  # Safe fallback

            # Remove stored data
            del self.curves[obj_id][prop]
            del self.data[obj_id][prop]
            del self.styles[obj_id][prop]

            # Clean up empty object groups
            if not self.curves[obj_id]:
                del self.curves[obj_id]
                del self.data[obj_id]
                del self.styles[obj_id]


    # ---------------------------------------------------------
    # Remove all curves for an object
    # ---------------------------------------------------------
    def remove_object(self, obj_id: str):
        """
        Remove all curves belonging to a specific object.
        """
        if obj_id in self.curves:
            for prop, curve in list(self.curves[obj_id].items()):
                self.plot.removeItem(curve)
                curve_name = f"{obj_id}:{prop}"
                try:
                    self.legend.removeItem(curve_name)
                except Exception:
                    pass

            del self.curves[obj_id]
            del self.data[obj_id]
            del self.styles[obj_id]


    # ---------------------------------------------------------
    # Style controls
    # ---------------------------------------------------------
    def set_title(self, title: str):
        self.plot.setTitle(title)

    def set_y_label(self, y_label: str, units: str = ""):
        self.plot.setLabel("left", y_label, units=units)

    def set_x_label(self, x_label: str, units: str = ""):
        self.plot.setLabel("bottom", x_label, units=units)

    def set_grid(self, x: bool = True, y: bool = True):
        self.plot.showGrid(x=x, y=y)

    def update_curve_style(self, obj_id: str, prop: str,
                       color=None, width=None, style=None):
        if obj_id not in self.curves or prop not in self.curves[obj_id]:
            return
        curve = self.curves[obj_id][prop]
        pen = curve.opts["pen"]

        # Update pen + internal style storage
        if color is not None:
            pen.setColor(QtGui.QColor(color))
            self.styles[obj_id][prop]["color"] = color

        if width is not None:
            pen.setWidth(width)
            self.styles[obj_id][prop]["width"] = width

        if style is not None:
            pen.setStyle(self._qt_style(style))
            self.styles[obj_id][prop]["style"] = style

        curve.setPen(pen)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    @property
    def title(self):
        return self.plot.getPlotItem().titleLabel.text

    def get_last_x(self, obj_id, prop):
        if obj_id not in self.data or prop not in self.data[obj_id]:
            return 0
        d = self.data[obj_id][prop]["x"]
        return d[-1] if d else 0

    def get_last_y(self, obj_id, prop):
        if obj_id not in self.data or prop not in self.data[obj_id]:
            return 0
        d = self.data[obj_id][prop]["y"]
        return d[-1] if d else 0

    def _make_pen(self, color, width, style):
        return pg.mkPen(
            color=color,
            width=width,
            style=self._qt_style(style)
        )

    def _qt_style(self, style: str):
        from PyQt6.QtCore import Qt

        styles = {
            "solid": Qt.PenStyle.SolidLine,
            "dash": Qt.PenStyle.DashLine,
            "dot": Qt.PenStyle.DotLine,
            "dashdot": Qt.PenStyle.DashDotLine,
        }
        return styles.get(style, Qt.PenStyle.SolidLine)
