
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
)
from PyQt6.QtGui import QIcon, QGuiApplication
from PyQt6.QtCore import QSize




from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

from functional.class_icons import ICON_MAP, Icons


# class IconBrowser(QWidget):

#     def __init__(self):
#         super().__init__()

#         self.setWindowTitle("Icon Browser")
#         self.resize(1200, 700)

#         layout = QVBoxLayout(self)

#         self.filter = QLineEdit()
#         self.filter.setPlaceholderText(
#             "Filter by alias, id, filename..."
#         )

#         self.table = QTableWidget()
#         self.table.setColumnCount(4)
#         self.table.setHorizontalHeaderLabels(
#             ["Icon", "ID", "Alias", "Resource"]
#         )

#         self.table.verticalHeader().hide()
#         self.table.setIconSize(QtCore.QSize(32, 32))
#         self.table.horizontalHeader().setSectionResizeMode(
#             3,
#             QHeaderView.ResizeMode.Stretch
#         )

#         layout.addWidget(self.filter)
#         layout.addWidget(self.table)

#         self.filter.textChanged.connect(self.populate)

#         self.populate()

#     def build_alias_lookup(self):
#         lookup = {}

#         for alias, resource in Icons._paths.items():
#             lookup.setdefault(resource, []).append(alias)

#         return lookup

#     def populate(self):

#         alias_lookup = self.build_alias_lookup()

#         text = self.filter.text().lower()

#         rows = []

#         for icon_id, resource in ICON_MAP.items():

#             aliases = alias_lookup.get(resource, [])

#             filename = resource.split("/")[-1]

#             search_text = (
#                 icon_id +
#                 filename +
#                 resource +
#                 " ".join(aliases)
#             ).lower()

#             if text and text not in search_text:
#                 continue

#             rows.append(
#                 (
#                     icon_id,
#                     aliases,
#                     resource
#                 )
#             )

#         self.table.setRowCount(len(rows))

#         for r, (icon_id, aliases, resource) in enumerate(rows):

#             icon_item = QTableWidgetItem()
#             icon_item.setIcon(QIcon(resource))

#             self.table.setItem(r, 0, icon_item)
#             self.table.setItem(r, 1,
#                                QTableWidgetItem(icon_id))
#             self.table.setItem(r, 2,
#                                QTableWidgetItem(
#                                    ", ".join(aliases)))
#             self.table.setItem(r, 3,
#                                QTableWidgetItem(resource))

class IconBrowser(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Icon Browser")
        self.resize(1200, 800)

        layout = QVBoxLayout(self)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText(
            "Filter filename or id..."
        )

        self.info = QLabel(
            "Click an icon to copy resource path."
        )

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setIconSize(QSize(64, 64))
        self.list.setGridSize(QSize(140, 110))
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)

        layout.addWidget(self.filter)
        layout.addWidget(self.info)
        layout.addWidget(self.list)

        self.filter.textChanged.connect(self.populate)
        self.list.itemClicked.connect(self.on_clicked)

        self.populate()

    def populate(self):
        self.list.clear()

        text = self.filter.text().lower().strip()

        for icon_id, resource in ICON_MAP.items():

            filename = resource.split("/")[-1]

            if text:
                search = f"{icon_id} {filename} {resource}".lower()
                if text not in search:
                    continue

            item = QListWidgetItem()
            item.setIcon(QIcon(resource))
            item.setText(f"{icon_id}\n{filename}")

            item.setData(1000, icon_id)
            item.setData(1001, resource)

            self.list.addItem(item)

    def on_clicked(self, item):

        icon_id = item.data(1000)
        resource = item.data(1001)

        msg = (
            f"ID: {icon_id}\n"
            f"Resource: {resource}"
        )

        print(msg)

        QGuiApplication.clipboard().setText(resource)

        self.info.setText(
            f"Copied: {resource}"
        )


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    w = IconBrowser()
    w.show()

    sys.exit(app.exec())