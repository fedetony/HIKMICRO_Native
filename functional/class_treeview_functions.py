# -*- coding: utf-8 -*-
#*********************************
# Author :F. Garcia
# Created 17.01.2026
#*********************************

import logging
from multiprocessing.sharedctypes import Value
from xmlrpc.client import boolean
from PyQt6 import QtCore, QtGui, QtWidgets
import re

tv_fun_name = "Treeview Functions"
# Add logger
try:
    from functional.class_LogHandler import get_appPath, LM
    log = LM.get_logger_with_handler(tv_fun_name,
                                     "debug",
                                     True,
                                     "%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
    log.info(f"{tv_fun_name} Logger started")
except (AttributeError, ImportError):
    # set up logging to file - see previous section for more details
    log = logging.getLogger(tv_fun_name) #'' for root logger
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s [%(levelname)s] (%(threadName)-10s) %(message)s',
                        datefmt='%y-%m-%d %H:%M')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    tvconsole = logging.StreamHandler()
    tvconsole.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('[%(levelname)s] (%(threadName)-10s) %(message)s')
    # tell the handler to use this format
    tvconsole.setFormatter(formatter)
    # add the handler to the root logger
    log.addHandler(tvconsole)
    log.info(f"{tv_fun_name} Local Logger started")

from typing import Dict, Any, List, Optional
from typing import Any, Dict, List, Tuple, Optional
from functional.class_struct_tracker import *

USER_ROLE = int(QtCore.Qt.ItemDataRole.UserRole)
# Architectural Notes:
# • 	Single source of truth () — avoids drift and duplication.
# • 	Metadata per item in  — makes validation, styling and updates deterministic.
# • 	Model-backed view () — good separation of UI and data.
# • 	Centralized validation and conversion — easier to reason about and test.
# • 	Style merging and caching idea — reduces intermittent UI failures.
class TreeviewFunctions(QtWidgets.QWidget):
    # signal: track (list path), value, valtype, subtype
    data_change = QtCore.pyqtSignal(list, object, str, str)
    # signal: track (list path), old_value, new_value, valtype, subtype
    data_change_old_new = QtCore.pyqtSignal(list, object ,object, str, str)
    # signal: track (list path), value, valtype, subtype
    struct_data_change = QtCore.pyqtSignal(list, object, str, str)
    # signal on click: item, index, stored
    item_clicked = QtCore.pyqtSignal(QtGui.QStandardItem, QtCore.QModelIndex, dict) 
    # signal on right click:  index, stored
    item_right_clicked = QtCore.pyqtSignal(QtCore.QModelIndex, dict, QtCore.QPoint)  

    roles_map={
            "DisplayRole":(QtCore.Qt.ItemDataRole.DisplayRole,str), 
            "ToolTipRole":(QtCore.Qt.ItemDataRole.ToolTipRole,str),
            "StatusTipRole":(QtCore.Qt.ItemDataRole.StatusTipRole,str),
            "WhatsThisRole":(QtCore.Qt.ItemDataRole.WhatsThisRole,str),
            "DecorationRole":(QtCore.Qt.ItemDataRole.DecorationRole,QtGui.QIcon),
            "ForegroundRole":(QtCore.Qt.ItemDataRole.ForegroundRole,QtGui.QColor),
            "BackgroundRole":(QtCore.Qt.ItemDataRole.BackgroundRole,QtGui.QColor),
            "FontRole":(QtCore.Qt.ItemDataRole.FontRole,QtGui.QFont),
            "TextAlignmentRole":(QtCore.Qt.ItemDataRole.TextAlignmentRole,QtCore.Qt.AlignmentFlag),
            "CheckStateRole":(QtCore.Qt.ItemDataRole.CheckStateRole,QtCore.Qt.CheckState),
            "SizeHintRole":(QtCore.Qt.ItemDataRole.SizeHintRole,QtCore.QSize),
            }
    
    def __init__(self,
                 treeviewobj: QtWidgets.QTreeView,
                 to_tree_struct: Dict[str, Any],
                 fields: Optional[List[dict]] = None,
                 *args, **kwargs):
        """
        treeviewobj: QTreeView instance to attach the model to
        to_tree_struct: single canonical dict with data + metadata
        fields: additional header fields to show 
        example:
            [{"name": "ITEM",  "editable": False, "selectable": True,  "hidden": False},
            {"name": "VALUE", "editable": True,  "selectable": True,  "hidden": False}]
        """
        super().__init__(*args, **kwargs)
        self.__name__ = tv_fun_name

        # validate view
        if not isinstance(treeviewobj, QtWidgets.QTreeView):
            raise TypeError(f"treeviewobj must be QTreeView, got {type(treeviewobj)}")
        self.treeviewobj = treeviewobj

        # model fields (columns)
        self.model_fields_properties = self.normalize_fields(fields)
        self.model_fields = [f["name"] for f in self.model_fields_properties]

        # canonical structure (single source of truth)
        self.main_struct = to_tree_struct or {}

        # UI state
        self._last_value_selected = None

        # caches (optional)
        self.icon_dict = {}
        self.style_dict = {}
        self.tooltip_dict = {}
        self.backgroundcolor_dict = {}
        self.foregroundcolor_dict = {}
        # flags
        self._populating = False

        # create model and attach to view
        self.modelobj = self.create_model_treeview(self.treeviewobj)
        self.treeviewobj.setModel(self.modelobj)
        self.enable_model_change_handler(self.modelobj)

        # populate model from main_struct
        self.refresh_treeview(self.main_struct, self.modelobj, self.treeviewobj)

        # connect view signals
        self.treeviewobj.clicked.connect(self.treeview_OnClick)
        self.treeviewobj.expanded.connect(self.treeview_fit_to_contents)
        self.treeviewobj.collapsed.connect(self.treeview_fit_to_contents)

        # expand a reasonable depth (wait until is populated and trigger the expansion)
        self.expansion_depth = 1
        QtCore.QTimer.singleShot(0, lambda: self.expand_to_depth_manual(self.expansion_depth))  
        #Set tracker
        self.tracker = TreeStructTracker(self.main_struct)
        self.tracker.data_changed.connect(self._signal_data_change)
        self._add_missing_fields_to_main_struct()

    def _add_missing_fields_to_main_struct(self):
        """Adds empty strings to all non‑existing properties in main_struct."""
        for field in self.model_fields:
            prop = self._get_field_properties(field)
            name = prop.get("name")
            if name and name != 'item':
                self.tracker.add_property_to_all_nodes(self.main_struct, name, "")  
        # print(self.main_struct)
    
    def on_data_change(self, path, value, typestr, subtype):
        """print when coming from delegate"""
        print("delegate data_change:", path, value, typestr, subtype)
        

    # -------------------------
    # Model creation
    # -------------------------
    def normalize_fields(self, fields):
        """gets normalized fields minimum ITEM, VALUE"""
        # base schema
        normalized = [
            {"name": "ITEM",  "editable": False, "selectable": True,  "hidden": False},
            {"name": "VALUE", "editable": True,  "selectable": True,  "hidden": False},
        ]

        if not fields:
            return normalized

        existing = {f["name"] for f in normalized}

        for f in fields:
            if isinstance(f, str):
                name = f.upper()
                if name.lower() in ["meta","children"]:
                    raise ValueError(f"Field {f} is reserved for canonical structure!")
                if name not in existing:
                    normalized.append({
                        "name": name,
                        "editable": (name == "VALUE"),
                        "selectable": True,
                        "hidden": False,
                    })
                    existing.add(name)

            elif isinstance(f, dict):
                name = str(f.get("name", "")).upper()
                if name.lower() in ["meta","children"]:
                    raise ValueError(f"Field {f} is reserved for canonical structure!")
                if name not in existing:
                    normalized.append({
                        "name": name,
                        "editable": f.get("editable", False),
                        "selectable": f.get("selectable", True),
                        "hidden": f.get("hidden", False),
                    })
                    existing.add(name)

        return normalized

    def create_model_treeview(self, treeviewparent: QtWidgets.QTreeView) -> QtGui.QStandardItemModel:
        """Create a standard model with columns defined by self.model_fields."""
        cols = len(self.model_fields)
        model = QtGui.QStandardItemModel(0, cols, treeviewparent)
        for col_index, name in enumerate(self.model_fields):
            model.setHeaderData(col_index, QtCore.Qt.Orientation.Horizontal, str(name))
        treeviewparent.setModel(model)

        return model
    
    def create_model_headers(self, model):
        """Set up column count and headers on an existing model."""
        model.setColumnCount(len(self.model_fields))

        for col, field in enumerate(self.model_fields):
            model.setHeaderData(col, QtCore.Qt.Orientation.Horizontal, field)

    def apply_column_hidden_properties(self, treeview):
        for col, field in enumerate(self.model_fields_properties):
            treeview.setColumnHidden(col, field.get("hidden", False))

    def _get_field_column_by_name(self,name:str)->int:
        """Gets the column for the field"""
        for col, field in enumerate(self.model_fields_properties):
            if name.upper() == field.get("name"):
                return col
        return None
    
    def _get_field_name_by_column(self,column)->str:
        """Gets header name (upper case) for a column"""
        for col, field in enumerate(self.model_fields_properties):
            if col == column:
                return field.get("name")
        return None
    
    def _get_property_name_by_column(self,column):
        """Gets property name (lower case) for a column"""
        name = self._get_field_name_by_column(column)
        if name:
            return name.lower()
        return None
    
    def _get_field_properties(self,name:str):
        properties={}
        for col, field in enumerate(self.model_fields_properties):
            if name.lower() == str(field.get("name")).lower():
                properties={
                "header": name.upper(),
                "name": name.lower(),
                "editable": field.get("editable", False),
                "selectable": field.get("selectable", True),
                "hidden": field.get("hidden", False),
                "column": col
                }
                break
        return properties

    # -------------------------
    # Refresh / populate
    # -------------------------
    def do_refresh(self):
        """Refresh with self.main_struct,self.modelobj,self.treeviewobj
        """
        self.refresh_treeview(self.main_struct,self.modelobj,self.treeviewobj)

    def refresh_treeview(self, dict_struct:dict, 
                         modelobj: QtGui.QStandardItemModel, 
                         treeviewobj:QtWidgets.QTreeView):
        if not isinstance(treeviewobj, QtWidgets.QTreeView):
            raise TypeError("treeviewobj must be QTreeView")
        self._populating = True
        modelobj.clear()
        self.create_model_headers(modelobj)
        self.enable_model_change_handler(modelobj) #->uses self.model_fields
        self.main_struct_import_data_to_tree(dict_struct, modelobj, treeviewobj)
        # Editability Flags
        self.apply_editability_recursive(modelobj)
        self.apply_column_hidden_properties(treeviewobj)
        self.set_treeview_styles(modelobj)
        self._populating = False
        self.treeview_fit_to_contents(0)

    def apply_editability_recursive(self, model):
        """
        Apply editability/selectability rules to every cell in the model,
        using schema defaults from model_fields_properties and per-item
        overrides from node['meta'] (VALUE column only).
        """
        col_props = self.model_fields_properties
        def recurse(item,hidden=False):
            if item is None:
                return
            parent = item.parent()
            row = item.row()
            # Determine number of columns in this row
            if parent:
                cols = parent.columnCount()
            else:
                cols = model.columnCount()
            # Retrieve node metadata
            stored = item.index().data(USER_ROLE)
            meta = self._get_meta(stored) or {}
            # Apply flags for each column
            for c in range(cols):
                cell = parent.child(row, c) if parent else model.item(row, c)
                if not cell:
                    continue
                props = col_props[c]  # schema for this column
                flags = cell.flags()
                # --- EDITABLE ---
                # Schema default
                editable = props["editable"]
                # Meta overrides only apply to VALUE column
                if props["name"] == "VALUE":
                    editable = meta.get("editable", editable)
                if editable:
                    flags |= QtCore.Qt.ItemFlag.ItemIsEditable
                else:
                    flags &= ~QtCore.Qt.ItemFlag.ItemIsEditable
                # --- SELECTABLE ---
                selectable = props["selectable"]
                if props["name"] == "VALUE":
                    selectable = meta.get("selectable", selectable)
                if selectable:
                    flags |= QtCore.Qt.ItemFlag.ItemIsSelectable
                else:
                    flags &= ~QtCore.Qt.ItemFlag.ItemIsSelectable
                cell.setFlags(flags)
            hidden = meta.get("hidden", hidden)   
            self.hide_item(hidden,item) 
            # Recurse into children (column 0)
            for r in range(item.rowCount()):
                recurse(item.child(r, 0),hidden)
        # Start at root
        for r in range(model.rowCount()):
            recurse(model.item(r, 0),False)
        
    def lock_column_recursive(self, model: QtGui.QStandardItemModel, column: int = 0):
        """Recursively lock a specific column (usually ITEM = column 0)."""
        def recurse(item):
            if item is None:
                return
            # lock this item's column
            item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            # recurse only through column 0 (tree structure)
            for r in range(item.rowCount()):
                child = item.child(r, 0)  # always follow column 0 for tree hierarchy
                recurse(child)
        # start recursion at root level
        for r in range(model.rowCount()):
            recurse(model.item(r, column))  

    def main_struct_import_data_to_tree(self, data: Any, modelobj: QtGui.QStandardItemModel,
                                treeviewobj: QtWidgets.QTreeView):
        """Accepts dict or list and delegates to dict_to_Tree."""
        if not isinstance(treeviewobj, QtWidgets.QTreeView):
            raise TypeError("treeviewobj must be QTreeView")

        modelobj.setRowCount(0)

        if self.is_list(data):
            # if list of dicts with IDs, convert to keyed dict
            for adict in data:
                newdict = {}
                try:
                    newdict.update({adict['ID']: adict})
                except Exception:
                    # fallback: skip or try to use index as key
                    continue
                self.dict_to_Tree(newdict, modelobj, treeviewobj, parent_item=None)
            return
        elif self.is_dict(data):
            self.dict_to_Tree(data, modelobj, treeviewobj, parent_item=None)
            return
        else:
            # nothing to import
            return

    def dict_to_Tree(self, node_dict, model, treeview, parent_item=None, parent_path=None):
        """
        Populate a QStandardItemModel tree from a canonical dictionary structure,
        using the column schema defined in `self.model_fields_properties`.
        - Columns are created dynamically based on `model_fields_properties`
        (e.g., ITEM, VALUE, TYPE, etc.).
        - Each column's editability, selectability, and visibility are controlled
        by the schema (editable/selectable/hidden flags).
        
        Parameters
        ----------
        node_dict : dict
            A dictionary containing exactly one key representing the node name.
            The value may be:
                - a dict with a "value" field (leaf node)
                - a dict with a "children" list (branch node)
                - a list of child nodes (branch node)
        model : QStandardItemModel
            The model being populated.
        treeview : QTreeView
            The view associated with the model (used for cosmetic resizing).
        parent_item : QStandardItem or None
            The parent item in the tree. If None, items are appended to the root.
        parent_path : list or None
            The hierarchical path to this node, used for USER_ROLE storage.

        Behavior
        --------
        - Creates one row per node, with as many columns as defined in the schema.
        - Column 0 (ITEM) always contains the node name.
        - VALUE column displays the node's value (if leaf), formatted via
        `_value_to_display()`.
        - TYPE column displays the node's declared type (default "str").
        - Additional schema-defined columns are filled with metadata or left blank.
        - Each cell stores a USER_ROLE dict: {"path": [...], "node": <ref>} so
        itemChanged handlers can update the canonical structure.
        - Boolean values automatically become checkboxes.
        - Decorations (icons, colors, tooltips) are applied via `decorate_item()`.
        - Recursively processes children for branch nodes.

        Notes
        -----
        - The function is safe to call during refresh, as long as `_populating`
        is set to True to suppress itemChanged events.
        """
        if parent_path is None:
            parent_path = []
        # node_dict always contains exactly one key
        for name, content in node_dict.items():
            # Determine node type
            is_branch = isinstance(content, list) or (isinstance(content, dict) and "children" in content)
            is_leaf = isinstance(content, dict) and "value" in content
            node_ref = content
            my_path = parent_path + [name]
            # Prepare USER_ROLE payload
            stored = {"path": my_path, "node": node_ref}
            # Build row_items dynamically based on model_fields_properties
            row_items = []
            for col, field in enumerate(self.model_fields_properties):
                field_name = field["name"]  # e.g. ITEM, VALUE, TYPE, META, etc.
                # --- ITEM column ---
                if field_name == "ITEM":
                    item = QtGui.QStandardItem(name)
                # --- VALUE column ---
                elif field_name == "VALUE":
                    if is_leaf:
                        val = content.get("value")
                        val_text = self._value_to_display(val)
                    else:
                        val_text = ""
                    item = QtGui.QStandardItem(val_text)
                    # checkbox for booleans
                    if is_leaf and isinstance(content.get("value"), bool):
                        item.setCheckable(True)
                        self.set_checkbox_value(item, content["value"])
                # --- TYPE column ---
                elif field_name == "TYPE":
                    type_text = content.get("type", "str") if "type" in content else "str"
                    item = QtGui.QStandardItem(type_text)
                # --- ANY OTHER FIELD COLUMN ---
                else:
                    _text = content.get(field_name.lower(), "") if field_name.lower() in content else ""
                    item = QtGui.QStandardItem(_text)
                # Store USER_ROLE
                item.setData(stored, USER_ROLE)
                if isinstance(content,dict):
                    meta=content.get("meta")
                    if isinstance(meta,dict):
                        # Apply editability from schema
                        flags = item.flags()
                        editable=meta.get("editable",field.get("editable",True))
                        if editable:
                            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
                        else:
                            flags &= ~QtCore.Qt.ItemFlag.ItemIsEditable
                        selectable=meta.get("selectable",field.get("selectable",True))
                        if selectable:
                            flags |= QtCore.Qt.ItemFlag.ItemIsSelectable
                        else:
                            flags &= ~QtCore.Qt.ItemFlag.ItemIsSelectable
                        item.setFlags(flags)       
                row_items.append(item)
            # Append row to model
            if parent_item is None:
                model.invisibleRootItem().appendRow(row_items)
            else:
                parent_item.appendRow(row_items)
            # Recurse into children
            if is_branch:
                children = content if isinstance(content, list) else content.get("children", [])
                for child in children:
                    self.dict_to_Tree(child, model, treeview, row_items[0], my_path)

    def hide_item(self,hidden:bool,item: QtGui.QStandardItem):
        """Hide or show an item. True hides, False Shows"""
        idx = item.index()                  
        if idx.isValid():
            self.treeviewobj.setRowHidden(idx.row(), idx.parent(), hidden)
        # if hidden:
        #     print("got hidden")
        

    # -------------------------
    # Helpers and utilities
    # -------------------------
    def _get_meta(self,stored):
        """Helper to get meta dictionary"""
        if isinstance(stored, dict):
            node = stored.get("node")
            if not isinstance(node,dict):
                return {}
            return node.get("meta", {})
        return {}
    
    def _get_type_subtype(self,stored):
        """Helper to get type and subtype 
        Returns:
         tuple: valtype,subtype
         """
        node = stored.get("node")
        meta=self._get_meta(stored)
        valtype = node.get("type", "str") or meta.get("subtype", "str")
        subtype = node.get("subtype", "") or meta.get("subtype", "")
        return valtype,subtype

    def _value_to_display(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ", ".join(str(x) for x in value)
        return str(value)
    
    @staticmethod
    def is_dict(v: Any) -> bool:
        return isinstance(v, dict)

    @staticmethod
    def is_list(v: Any) -> bool:
        return isinstance(v, list)

    @staticmethod
    def is_bool(v: Any) -> bool:
        return isinstance(v, bool)
    
    @staticmethod
    def get_dict_key_list(d: Dict[str, Any]) -> List[str]:
        # preserve insertion order; you can customize sorting here
        return list(d.keys())

    def set_checkbox_value(self, item: QtGui.QStandardItem, checked: bool):
        item.setCheckState(QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked)

    # -------------------------
    # View interactions
    # -------------------------
    def _on_context_menu(self, pos: QtCore.QPoint):
        # pos is in view coordinates
        proxy_index = self.treeviewobj.indexAt(pos)            # proxy index if view uses proxy
        if not proxy_index.isValid():
            return

        # if using a proxy model, map to source
        source_model = self.treeviewobj.model()
        if isinstance(source_model, QtCore.QSortFilterProxyModel):
            src_idx = source_model.mapToSource(proxy_index)
        else:
            src_idx = proxy_index

        if not src_idx.isValid():
            return

        # optionally extract the stored node info (USER_ROLE)
        stored = src_idx.data(USER_ROLE)
        # emit the source index or the stored data for the main to build the menu
        self.item_right_clicked.emit(src_idx,stored,pos)

    def treeview_fit_to_contents(self, index: QtCore.QModelIndex):
        """Optional: handle expand/collapse events (placeholder)."""
        # You can update UI caches or lazy-load children here
        if self._populating:
            return
        try:
            self.treeviewobj.resizeColumnToContents(0)
        except Exception:
            pass

    def expand_to_depth_manual(self, depth: int):
        """Expand tree to a given depth (non-blocking recursive)."""
        def recurse(idx: QtCore.QModelIndex, level: int):
            if level > depth:
                return
            self.treeviewobj.expand(idx)
            model = self.modelobj
            rows = model.rowCount(idx)
            for r in range(rows):
                child = model.index(r, 0, idx)
                self.expansion_depth=max(self.expansion_depth,level)
                recurse(child, level + 1)
        recurse(QtCore.QModelIndex(), 0)
        

    def expand_to_depth(self, depth: int):
        """
        Expand the tree view to the requested depth.
        - Uses get_dict_max_depth(self.main_struct) to determine maximum depth.
        - If depth < 0: collapse all. If depth >= maxdepth: expand all.
        - Otherwise call QTreeView.expandToDepth(depth).
        """
        try:
            maxdepth = self.get_dict_max_depth(self.main_struct)
        except Exception:
            # fallback: expand all if we cannot compute depth
            try:
                self.treeviewobj.expandAll()
                self.expansion_depth=maxdepth
            except Exception:
                pass
            return

        if depth < 0:
            try:
                self.treeviewobj.collapseAll()
                self.expansion_depth=0
            except Exception:
                pass
            return

        if depth >= maxdepth:
            try:
                self.treeviewobj.expandAll()
                self.expansion_depth=maxdepth
            except Exception:
                pass
        else:
            try:
                # QTreeView.expandToDepth expects an int depth
                self.treeviewobj.expandToDepth(int(depth))
                self.expansion_depth=depth
            except Exception:
                # fallback to expanding root children up to depth manually
                self.treeviewobj.expandAll()

    def get_selected_paths(self) ->list[str]:
        """Gets a list of first column indexes that are selected

        Returns:
            list[str]: list of indexes
        """
        selected = []
        for idx in self.treeviewobj.selectedIndexes():
            if idx.column() != 0:
                continue
            path = self.get_path_for_index(idx)
            selected.append(path)
        return selected


    def get_expanded_paths(self)->list:
        """Makes a list of the paths which are expanded

        Returns:
            list: Expanded
        """
        paths = []
        def recurse(idx, path):
            if self.treeviewobj.isExpanded(idx):
                paths.append(path[:])

            model = self.modelobj
            rows = model.rowCount(idx)
            for r in range(rows):
                child = model.index(r, 0, idx)
                name = model.data(child, QtCore.Qt.ItemDataRole.DisplayRole)
                recurse(child, path + [name])

        root = QtCore.QModelIndex()
        recurse(root, [])
        return paths
    
    def restore_expanded_paths(self, paths:list):
        """Restores the expansion of the list of paths

        Args:
            paths (list): list of paths
        """
        for path in paths:
            idx = self.find_index_by_path(path)
            if idx.isValid():
                self.treeviewobj.expand(idx)
    
    def restore_selected_paths(self, paths):
        """Restores the selected items

        Args:
            paths (list): list of paths
        """
        selection_model = self.treeviewobj.selectionModel()
        selection_model.clearSelection()

        for path in paths:
            idx = self.find_index_by_path(path)
            if idx.isValid():
                selection_model.select(
                    idx,
                    QtCore.QItemSelectionModel.SelectionFlag.Select |
                    QtCore.QItemSelectionModel.SelectionFlag.Rows
                )
    
    def find_index_by_path(self, path):
        """Helper to navigate model"""
        model = self.modelobj
        idx = QtCore.QModelIndex()
        for name in path:
            found = None
            rows = model.rowCount(idx)
            for r in range(rows):
                child = model.index(r, 0, idx)
                if model.data(child, QtCore.Qt.ItemDataRole.DisplayRole) == name:
                    found = child
                    break
            if found is None:
                return QtCore.QModelIndex()
            idx = found
        return idx
    
    def get_path_for_index(self, idx):
        model = self.modelobj
        path = []
        while idx.isValid():
            name = model.data(idx, QtCore.Qt.ItemDataRole.DisplayRole)
            path.insert(0, name)
            idx = idx.parent()
        return path


    # # -------------------------
    # # Styling pass (apply icons/backgrounds after model built)
    # # -------------------------

    def set_treeview_styles(self, modelobj: QtCore.QAbstractItemModel):
        """
        Entry point: apply styles to all items in the model.
        Accepts either a QStandardItemModel or any QAbstractItemModel that supports
        itemFromIndex (we convert indexes to QStandardItem where possible).
        """
        try:
            if isinstance(modelobj, QtCore.QAbstractItemModel):
                # Start from the invisible root index
                root_index = QtCore.QModelIndex()
                self._set_style_to_all_items(modelobj, root_index)
        except Exception as e:
            # Replace 'log' with your logger or print
            try:
                log.error(f"Set treeview styles: {e}")
            except Exception:
                print(f"Set treeview styles error: {e}")


    def _set_style_to_all_items(self, model: QtCore.QAbstractItemModel, parent_index: QtCore.QModelIndex):
        """
        Recursively walk children of parent_index and apply style to each row's first column item.
        Works with QStandardItemModel by converting index -> itemFromIndex.
        """
        row_count = model.rowCount(parent_index)
        for row in range(row_count):
            idx = model.index(row, 0, parent_index)  # first column index for this row
            if not idx.isValid():
                continue

            # If we couldn't get a QStandardItem, we can still set roles on the model directly
            # using setData(index, value, role). Prefer item when available.
            self.set_item_style( model, idx)  # item, model, idx)

            # Recurse into children
            if model.hasChildren(idx):
                self._set_style_to_all_items(model, idx)

    def set_item_colors_by_track(self, modelobj: QtCore.QAbstractItemModel, track: List[str], color: Optional[QtGui.QColor] = None):
        """Set background color for the item identified by track. Uses model.setData(index, brush, BackgroundRole)."""
        try:
            if color is None:
                color = QtGui.QColor(255, 0, 0, 50)  # semi-transparent red
            itm, itmindex, _, _ = self.get_item_from_track(modelobj, track)
            if itmindex is None or not itmindex.isValid():
                return
            brush = QtGui.QBrush(color)
            # set on the model for the first column index
            modelobj.setData(itmindex, brush, int(QtCore.Qt.ItemDataRole.BackgroundRole))
            # if you want to set for value column too:
            val_index = itmindex.sibling(itmindex.row(), 1) if modelobj.columnCount() > 1 else None
            if val_index and val_index.isValid():
                modelobj.setData(val_index, brush, int(QtCore.Qt.ItemDataRole.BackgroundRole))
        except Exception as e:
            try:
                log.error(f"set_item_colors_by_track: {e}")
            except Exception:
                print(f"set_item_colors_by_track: {e}")

    def set_item_style(self, model: QtCore.QAbstractItemModel, index: QtCore.QModelIndex):
        """
        Apply icon, background, tooltip, and style to the item at index,
        using the new reference-based metadata and the centralized caches.
        """
        if not index.isValid():
            return
        # Try to get the QStandardItem (preferred)
        try:
            item = model.itemFromIndex(index)
        except Exception:
            item = None
        # Retrieve stored reference
        stored = index.data(USER_ROLE)
        if not isinstance(stored, dict):
            return
        node = stored.get("node", {})
        if not isinstance(node, dict):
            return

        # ---------------------------------------------------------
        # ICON via icon_key
        # ---------------------------------------------------------
        icon_key = node.get("icon_key")
        if icon_key and icon_key in self.icon_dict:
            icon = self.icon_dict[icon_key]
            self._set_role_item_index(model,icon,item,index,QtCore.Qt.ItemDataRole.DecorationRole)

        # ---------------------------------------------------------
        # BACKGROUND via bg_key
        # ---------------------------------------------------------
        bg_key = node.get("bg_key")
        if bg_key and bg_key in self.backgroundcolor_dict:
            color = self.backgroundcolor_dict[bg_key]
            brush = QtGui.QBrush(QtGui.QColor(color))
            self._set_role_item_index(model,brush,item,index,QtCore.Qt.ItemDataRole.BackgroundRole)
        
        # ---------------------------------------------------------
        # FOREGROUND via fg_key
        # ---------------------------------------------------------
        fg_key = node.get("fg_key")
        if fg_key and fg_key in self.foregroundcolor_dict:
            color = self.foregroundcolor_dict[fg_key]
            brush = QtGui.QBrush(QtGui.QColor(color))
            self._set_role_item_index(model,brush,item,index,QtCore.Qt.ItemDataRole.ForegroundRole)
            
        # ---------------------------------------------------------
        # STYLE via style_key (e.g., {"ForegroundRole": QtGui.QBrush(QtGui.QColor("#ffaa00"))})
        # ---------------------------------------------------------
        style_key = node.get("style_key")
        if style_key and style_key in self.style_dict:
            cached_style = self.style_dict[style_key]
            if isinstance(cached_style, dict):
                all_styles = [cached_style]
            elif isinstance(cached_style, list):
                all_styles = cached_style
            else:
                all_styles = []

            for style in all_styles:    
                if "field" in style:
                    col = self._get_column_from_fields_name(style["field"])
                    if col is not None:
                        idx = index.sibling(index.row(), col)
                    else:
                        idx = index    
                else:
                    idx = index
                if "bg" in style:
                    brush = QtGui.QBrush(QtGui.QColor(style["bg"]))
                    self._set_role_item_index(model,brush,None,idx,QtCore.Qt.ItemDataRole.BackgroundRole)
                if "fg" in style:
                    brush = QtGui.QBrush(QtGui.QColor(style["fg"]))
                    self._set_role_item_index(model,brush,None,idx,QtCore.Qt.ItemDataRole.ForegroundRole)
                for role_txt,(role, role_type) in self.roles_map.items():
                    if role_txt in style:
                        if isinstance(style[role_txt],role_type):
                            self._set_role_item_index(model,style[role_txt],None,idx,role)

        # ---------------------------------------------------------
        # TOOLTIP via tooltip_key
        # ---------------------------------------------------------
        tooltip_key = node.get("tooltip_key")
        if tooltip_key and tooltip_key in self.tooltip_dict:
            tip = self.tooltip_dict[tooltip_key]
            self._set_role_item_index(model,tip,item,index,QtCore.Qt.ItemDataRole.ToolTipRole)
            return  # tooltip resolved

        # ---------------------------------------------------------
        # OPTIONAL: fallback to restriction-based tooltip
        # ---------------------------------------------------------
        try:
            reslist, resvallist, _ = self.get_item_restriction_resval(index)
            parts = []
            for res, resval in zip(reslist, resvallist):
                if res in ('limited_selection', 'is_list_item_limited_selection'):
                    parts.append(f"Options: {resval}")
                elif res == 'minmax':
                    parts.append(f"Range: {resval}")
            if parts:
                tip = "; ".join(parts)
                self._set_role_item_index(model,tip,item,index,QtCore.Qt.ItemDataRole.ToolTipRole)
                return
        except Exception:
            pass
        meta=self._get_meta(stored)
        options=meta.get("options")
        if isinstance(options,list):
            tip=f"Options: {', '.join(options)}"
            self._set_role_item_index(model,tip,item,index,QtCore.Qt.ItemDataRole.ToolTipRole)
            
    def _set_role_item_index(self,model: QtCore.QAbstractItemModel,
                             obj:object,item:QtGui.QStandardItem,
                             index: QtCore.QModelIndex,
                             role:QtCore.Qt.ItemDataRole):
        """Set role helper"""
        if item is not None:
            item.setData(obj, role)
        else:
            model.setData(index, obj, role)

    ## ---- cache getters ----
    def set_tooltip_cache(self, tooltip_dict: Dict[str, Any]):
        """
        Set the reference cache for tooltips.

        Nodes do not store tooltip text directly. Instead, each node may specify
        a "tooltip_key" field, and this cache maps that key to the actual tooltip
        string that will be applied to the item.

        Example:
            self.set_tooltip_cache({
                "threshold_info": "This value controls the detection threshold",
                "count_info": "Number of items to process"
            })

        Args:
            tooltip_dict (Dict[str, Any]): Mapping of tooltip_key -> tooltip text.
        """
        self.tooltip_dict = tooltip_dict or {}
        self.do_refresh()

    def set_icons_cache(self, icondict: Dict[str, Any]):
        """
        Set the reference cache for icons.

        The tree items do not store QIcon objects directly. Instead, each node
        may specify an "icon_key" field, and this cache maps that key to the
        actual QIcon instance (or a path that will be converted to a QIcon).

        Example:
            self.set_icons_cache({
                "folder": QIcon("icons/folder.png"),
                "warning": QIcon("icons/warning.png")
            })

        Args:
            icondict (Dict[str, Any]): Mapping of icon_key -> QIcon or icon path.
        """
        self.icon_dict = icondict or {}
        self.do_refresh()
    
    def set_style_cache(self, style_dict: Dict[str, Any]):
        """
        Set the reference cache for item styles.

        Nodes store only a ``style_key``; the cache maps that key to either
        a style dictionary or a list of style dictionaries. Each style may
        optionally specify ``field`` to target another column else is applied to column 0.

        Example:
            {
                "Device Map": [
                    {"field": "MAPTYPE", "ForegroundRole": QtGui.QColor("#3498db")},
                    {"field": "MAPTYPE", "DecorationRole": device_map_icon},
                ],
                "Warning": {"field": "MAPTYPE", "ForegroundRole": QtGui.QColor("#e67e22")},
            }

        Role -> Type
        --------------
            DisplayRole         -> str
            ToolTipRole         -> str
            StatusTipRole       -> str
            WhatsThisRole       -> str
            DecorationRole      -> QIcon | QPixmap
            ForegroundRole      -> QColor | QBrush
            BackgroundRole      -> QColor | QBrush
            FontRole            -> QFont
            TextAlignmentRole   -> Qt.AlignmentFlag
            CheckStateRole      -> Qt.CheckState
            SizeHintRole        -> QSize
            UserRole+N          -> anything

        Args:
            style_dict: Mapping of style_key to a style dict or list of styles.
        """
        self.style_dict = style_dict or {}
        self.do_refresh()

    def set_backgroundcolor_cache(self, backgroundcolor_dict: Dict[str, Any]):
        """
        Set the reference cache for background colors.

        Nodes may specify a "bg_key" field, and this cache maps that key to a
        color string (e.g. "#ff0000") or a QBrush instance. This is a simpler
        alternative to style_dict when only background color is needed.

        Example:
            self.set_backgroundcolor_cache({
                "error": "#ffcccc",
                "disabled": "#dddddd"
            })

        Args:
            backgroundcolor_dict (Dict[str, Any]): Mapping of bg_key -> color string or QBrush.
        """
        self.backgroundcolor_dict = backgroundcolor_dict or {}
        self.do_refresh()
    
    def set_foregroundcolor_cache(self, foregroundcolor_dict: Dict[str, Any]):
        """
        Set the reference cache for foreground colors.

        Nodes may specify a "fg_key" field, and this cache maps that key to a
        color string (e.g. "#ff0000") or a QBrush instance. This is a simpler
        alternative to style_dict when only background color is needed.

        Example:
            self.set_backgroundcolor_cache({
                "error": "#ffcccc",
                "disabled": "#dddddd"
            })

        Args:
            Foregroundcolor_dict (Dict[str, Any]): Mapping of bg_key -> color string or QBrush.
        """
        self.foregroundcolor_dict = foregroundcolor_dict or {}
        self.do_refresh()

    def set_icon_to_item(self, itm: QtGui.QStandardItem):
        """Backward-compatible helper: set icon for a single QStandardItem using icon_dict."""
        if itm is None:
            return
        self.apply_icon(itm)


    def set_backgroundcolor_to_item(self, itm: QtGui.QStandardItem):
        """Backward-compatible helper: set background for a single QStandardItem using backgroundcolor_dict."""
        if itm is None:
            return
        self.apply_background(itm)
    
    def set_foregroundcolor_to_item(self, itm: QtGui.QStandardItem):
        """Backward-compatible helper: set foreground for a single QStandardItem using foregroundcolor_dict."""
        if itm is None:
            return
        self.apply_foreground(itm)


    def set_tooltiptext(self, index: QtCore.QModelIndex):
        """
        Old behavior: set tooltip based on restriction results.
        This uses get_item_restriction_resval(index) which should return:
        (reslist, resvallist, other)
        Implement that function to consult your mask/schema.
        """
        try:
            reslist, resvallist, _ = self.get_item_restriction_resval(index)
        except Exception:
            return

        # get the item (prefer QStandardItem)
        try:
            itm = index.model().itemFromIndex(index)
        except Exception:
            itm = None

        for res, resval in zip(reslist, resvallist):
            if res in ['limited_selection', 'is_list_item_limited_selection']:
                tip = f"Options: {resval}"
                if itm is not None:
                    itm.setToolTip(tip)
                else:
                    index.model().setData(index, tip, int(QtCore.Qt.ItemDataRole.ToolTipRole))
                # if you want to show multiple restriction lines, accumulate them instead

    def treeview_OnClick(self, index: QtCore.QModelIndex):
        """Handle clicks: decorate key item and start editing value column based on node metadata."""
        if not index.isValid():
            return

        # Retrieve all column-related info
        key_map_dict = self._get_index_key_for_item(index)

        # Safe extraction helpers
        def safe_get(field, key):
            entry = key_map_dict.get(field)
            return entry.get(key) if isinstance(entry, dict) else None

        key_item = safe_get("ITEM", "item")
        val_item = safe_get("VALUE", "item")
        # print(key_map_dict["ITEM"])
        # print(key_map_dict["VALUE"])
        idx_val  = safe_get("VALUE", "index")
        if val_item and key_item:
            self.item_clicked.emit(key_item,index,val_item.data(USER_ROLE))
        # Make key non-editable
        if key_item:
            key_item.setEditable(False)
            # Decorate only the key item (icon, style, tooltip, background)
            self.decorate_item(key_item,True,index)

        # If no value column or click is not on value column, nothing more to do
        if not (idx_val and index.column() == idx_val.column() and val_item):
            return

        # Read node metadata from USER_ROLE
        stored = val_item.data(USER_ROLE)
        node = stored.get("node") if isinstance(stored, dict) else None

        # Default assumptions
        editable = True
        is_bool = False
        is_branch = False
        current_value = None

        if isinstance(node, dict):
            node_type,node_subtype = self._get_type_subtype(stored)
            meta = self._get_meta(stored)
            editable = meta.get("editable", True)
            current_value = node.get("value")
            is_bool = isinstance(current_value, bool)
            # branch if it has children
            is_branch = "children" in node

        elif isinstance(node, list):
            # pure list branch
            is_branch = True
            editable = False

        # Checkbox logic for booleans
        if is_bool:
            val_item.setCheckable(True)
            self.set_checkbox_value(val_item, bool(current_value))
        else:
            val_item.setCheckable(False)

        # Branches are not editable
        if is_branch:
            val_item.setEditable(False)
        else:
            val_item.setEditable(editable)

        # Start editing the value cell
        # self.treeviewobj.setCurrentIndex(idx_val)
        # print("Clicked index (row,col):", idx_val.row(), idx_val.column())
        # self.treeviewobj.edit(idx_val)

    def get_column_from_fields_name(self, name: str) -> int | None:
        """Return column number in model"""
        return self._get_column_from_fields_name(name)

    def _get_column_from_fields_name(self, name: str) -> int | None:
        """Return column number in model"""
        try:
            return self.model_fields.index(name)
        except ValueError:
            return None
    
    def _get_index_key_for_item(self, index: QtCore.QModelIndex):
        """
        Return a dict mapping each field name to:
            - "column": its column index
            - "index": the QModelIndex for that column
            - "model": the correct model (source model)
            - "item": the QStandardItem (or None)
        """
        key_dict = {}

        for name in self.model_fields:
            col = self._get_column_from_fields_name(name)
            idx = index.sibling(index.row(), col)

            # Map through proxy if needed
            model = idx.model()
            if model is not self.modelobj:
                try:
                    idx_src = model.mapToSource(idx)
                    model = self.modelobj
                    idx = idx_src
                except Exception:
                    # Not a proxy, fallback
                    pass

            item = model.itemFromIndex(idx) if idx.isValid() else None

            key_dict[name] = {
                "column": col,
                "index": idx,
                "model": model,
                "item": item
            }

        return key_dict
            
    def enable_model_change_handler(self, modelobj: QtGui.QStandardItemModel):
        """Call once during init to connect a single handler for item changes."""
        # Connect once; avoid multiple connects
        try:
            modelobj.itemChanged.disconnect(self._on_item_changed)
        except Exception:
            pass
        modelobj.itemChanged.connect(self._on_item_changed)

    def track_key_tree(self, item: QtGui.QStandardItem) -> List[str]:
        """Return path (list of keys) from root to the given QStandardItem."""
        if item is None:
            return []
        path = []
        cur = item
        while cur is not None:
            path.append(cur.text())
            cur = cur.parent()
        path.reverse()
        return path

    def get_item_from_track(self, modelobj: QtCore.QAbstractItemModel, track: List[str]):
        """
        Find the QStandardItem and its index for a given track (list of keys).
        Returns (item, index, item_list, index_list) or (None, None, [], []) if not found.
        Works by walking children; robust to missing nodes.
        """
        if not isinstance(modelobj, QtCore.QAbstractItemModel) or not track:
            return None, None, [], []

        item_list = []
        index_list = []
        parent_index = QtCore.QModelIndex()

        for key in track:
            found = False
            rows = modelobj.rowCount(parent_index)
            for r in range(rows):
                idx = modelobj.index(r, 0, parent_index)
                if not idx.isValid():
                    continue
                itm = None
                try:
                    itm = modelobj.itemFromIndex(idx)
                except Exception:
                    # fallback: read display text from model
                    txt = idx.data(QtCore.Qt.ItemDataRole.DisplayRole)
                    if txt == key:
                        found = True
                        item_list.append(None)
                        index_list.append(idx)
                        parent_index = idx
                        break
                    continue
                if itm is None:
                    continue
                if itm.text() == key:
                    found = True
                    item_list.append(itm)
                    index_list.append(idx)
                    parent_index = idx
                    break
            if not found:
                return None, None, item_list, index_list

        # return last found item and index plus lists
        return (item_list[-1] if item_list else None,
                index_list[-1] if index_list else None,
                item_list, index_list)

    def _on_item_changed(self, item: QtGui.QStandardItem):
        """
        Central handler for item changes. Validates, converts, updates main_struct,
        and emits data_change. Reverts item text on validation failure.
        """
        if getattr(self, "_populating", False):
            return

        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            path = stored.get("path", [])
            node = stored.get("node", {})
            if not isinstance(node,dict):
                return
            meta = self._get_meta(stored)

            # raw text from the edited item
            new_text = item.text()
            index = item.index()
            property_name=self._get_property_from_index(index)
            old_value = node.get(property_name)

            # If nothing changed, ignore
            if self._values_equal_text(old_value, new_text, meta):
                return
            # Retrieve all column-related info
            key_map_dict = self._get_index_key_for_item(index)

            # Safe extraction helpers
            def safe_get(field, key):
                entry = key_map_dict.get(field)
                return entry.get(key) if isinstance(entry, dict) else None

            key_item = safe_get("ITEM", "item")
            val_item = safe_get("VALUE", "item")
            idx_val  = safe_get("VALUE", "index")
            
            # If no value column or click is not on value column, nothing more to do
            if property_name == "value":
                ok, converted = self.validate_and_convert(new_text, stored)
                # print("Validation ->",ok)
                if (idx_val and index.column() == idx_val.column() and val_item):
                    ok &= self.check_item_value_for_edit(index, new_text, True, True)
                    # print("Checkitem ->",ok)
                if meta.get("restore_value"):
                    ok=False
                if not ok:
                    # revert UI to previous canonical value
                    item.setText(self._value_to_display(old_value))
                    if meta.get("type") == "bool":
                        self.set_checkbox_value(item, bool(old_value))
                    return

                # update canonical structure
                self.update_main_struct_by_path(path+["value"], converted)

                # update node
                node["value"] = converted
                valtype, subtype = self._get_type_subtype(stored)
            else: 
                if meta.get("restore_all_properties",False) or meta.get("restore_"+property_name,False):
                    converted = old_value   
                    # revert UI to previous canonical value
                    item.setText(old_value)
                    return 
                else:
                    converted = new_text
                node[property_name] = converted
                valtype, subtype = ("str","")
            # write back full node
            item.setData({"path": path, "node": node}, USER_ROLE)

            # refresh subtree if needed
            if meta.get("refresh_on_change", False):
                self.refresh_treeview(self.main_struct, self.modelobj, self.treeviewobj)
            
            if node.get("type") == "bool":
                self.set_checkbox_value(item, bool(converted))

            # emit signal
            if str(old_value) != str(converted):
                self.data_change_old_new.emit(path+[property_name], old_value ,converted, str(valtype), str(subtype))
                self.data_change.emit(path+[property_name], converted, str(valtype), str(subtype))

        except Exception as e:
            log.error(f"_on_item_changed: {e}")
        
    def validate_and_convert(self, text: str, stored: dict) -> tuple[bool, object]:
        """
        Validate text against meta and convert to the proper Python value.
        stored expected keys:
        - type: 'int'|'float'|'bool'|'list'|'coords'|'str'
        - subtype: for list items, e.g. 'int' or ['float','int']
        - constraints: dict with optional 'min','max','regex','arity'
        Returns (ok, converted_value)
        """
        t,subtype = self._get_type_subtype(stored)
        meta=self._get_meta(stored)
        constraints = meta.get("constraints", {}) or {}

        # Helper: numeric range check
        def in_range(v):
            mn = constraints.get("min")
            mx = constraints.get("max")
            try:
                if mn is not None and v < mn: return False
                if mx is not None and v > mx: return False
            except Exception:
                return False
            return True

        # STR
        if t == "str":
            regex = constraints.get("regex")
            if regex:
                import re
                if not re.fullmatch(regex, text):
                    return False, None
            return True, text

        # INT
        if t == "int":
            try:
                v = int(text)
            except Exception:
                return False, None
            if not in_range(v): return False, None
            return True, v

        # FLOAT
        if t == "float":
            try:
                v = float(text)
            except Exception:
                return False, None
            if not in_range(v): return False, None
            return True, v

        # BOOL
        if t == "bool":
            low = text.strip().lower()
            if low in ("1","true","yes","y"):
                return True, True
            if low in ("0","false","no","n"):
                return True, False
            return False, None

        # LIST or COORDS (comma separated)
        if t in ("list","coords"):
            parts = [p.strip() for p in text.split(",") if p.strip() != ""]
            arity = constraints.get("arity")
            if arity is not None and len(parts) != int(arity):
                return False, None
            converted = []
            for p in parts:
                if subtype == "int":
                    try:
                        converted.append(int(p))
                    except Exception:
                        return False, None
                elif subtype == "float":
                    try:
                        converted.append(float(p))
                    except Exception:
                        return False, None
                else:
                    converted.append(p)
            # range check for coords if min/max are lists
            if t == "coords":
                mn = constraints.get("min")
                mx = constraints.get("max")
                if mn or mx:
                    for i, val in enumerate(converted):
                        if mn and i < len(mn) and val < mn[i]: return False, None
                        if mx and i < len(mx) and val > mx[i]: return False, None
            return True, converted

        # fallback
        return True, text
    
    def update_main_struct_by_path(self, path: list, value) -> bool:
        """
        Walk self.main_struct and set the 'value' (or plain key) at the final path.
        Returns True on success.
        """
        return self.tracker.set_value(path,value)
    
    def _values_equal_text(self, old_value, new_text, meta):
        """Compare old_value to new_text considering meta type to avoid false positives."""
        t = meta.get("type", "str")
        if t in ("list", "coords"):
            # normalize both to comma-joined strings
            old_text = self._value_to_display(old_value)
            return old_text == new_text
        if t == "bool":
            low = new_text.strip().lower()
            new_bool = low in ("1","true","yes","y")
            return bool(old_value) == new_bool
        # numeric compare
        try:
            if t == "int":
                return int(old_value) == int(new_text)
            if t == "float":
                return float(old_value) == float(new_text)
        except Exception:
            pass
        return str(old_value) == new_text

    def track_from_index(self, index):
        """Generates the track for the item at index

        Args:
            index (_type_): _description_

        Returns:
            _type_: _description_
        """
        if not index.isValid():
            return []
        item = self.modelobj.itemFromIndex(index)
        if item is None:
            return []
        stored = item.data(USER_ROLE)
        if not isinstance(stored, dict):
            return []
        col = index.column()
        prop=self._get_property_name_by_column(col)
        if prop:
            path=stored.get("path", [])
            return path+[prop]    
        return stored.get("path", [])
    
    def index_from_track(self, track, parent_index=QtCore.QModelIndex()):
        """Finds index of track recursively"""
        rows = self.modelobj.rowCount(parent_index)

        for row in range(rows):
            idx = self.modelobj.index(row, 0, parent_index)
            item = self.modelobj.itemFromIndex(idx)

            stored = item.data(USER_ROLE)
            if isinstance(stored, dict):
                if stored.get("path") == track:
                    return idx

            # recurse into children
            child_idx = self.index_from_track(track, idx)
            if child_idx.isValid():
                return child_idx

        return QtCore.QModelIndex()
    
    def _get_property_from_index(self,index):
        """get propety from the index"""
        # track=self.track_from_index(index)
        # node_path = track[:-1]
        # prop = track[-1]
        col = index.column()
        prop = self._get_property_name_by_column(col)
        return prop
    
    def set_tracked_value_to_dict(self, track, val, dict_struct, subtype='', emitsignal=True):
        """
        Backwards‑compatible wrapper for updating a value in a canonical structure.

        - If dict_struct is self.main_struct:
            Uses the persistent tracker, emits signals, refreshes the UI.
        - If dict_struct is external:
            Creates a temporary tracker, emits signals, does NOT refresh the UI.

        Returns:
            (updated: bool, dict_struct: dict)
        """

        # Decide which tracker to use
        if dict_struct is self.main_struct:
            tracker = self.tracker
            do_refresh = True
        else:
            # Temporary tracker for external structures
            tracker = TreeStructTracker(dict_struct)
            if  emitsignal:
                tracker.data_changed.connect(self._signal_data_change)
            do_refresh = False

        # Perform the update
        updated = tracker.set_value(track, val, subtype=subtype)

        # Refresh only when modifying the main structure
        if updated and do_refresh:
            self.do_refresh()

        return updated, dict_struct

    def _signal_data_change(self,track:list, value:object, a_type:str, subtype:str):
        """ Emits signal: track (list path), value, valtype, subtype"""
        self.struct_data_change.emit(track,value,a_type,subtype)

    def check_item_value_for_edit(self, index: QtCore.QModelIndex, value: any, isok: bool = True, do_log: bool=True):
        """
        Centralized check: first by declared type, then by mask/constraints.
        Returns boolean.
        """
        # 1) by type/format (uses metadata stored in USER_ROLE)
        isok = self.check_item_by_type(index, value, isok, do_log)
        if not isok:
            return isok
        # 2) by mask/constraints (your existing mask logic)
        isok = self.check_item_by_mask(index, value, isok, do_log)

        return isok

    def get_item_restriction_resval(self, index: QtCore.QModelIndex):
        """
        Return three parallel lists:
        reslist: list of restriction keys (e.g., 'limited_selection')
        resvallist: primary values for each restriction
        resvalaltlist: optional alternate values (or None)
        Lookup order:
        1) metadata stored in USER_ROLE on the item (meta.get('mask'))
        2) global mask via self.get_mask_for_item(path)
        """
        # get stored metadata if present
        stored = index.data(USER_ROLE)
        path = []
        if isinstance(stored, dict):
            path = stored.get("path", []) or []
            meta = self._get_meta(stored)
        else:
            meta = {}

        # try mask in node metadata first
        itmmask = meta.get("mask", {}) or {}

        # if not present, try global mask lookup by path
        if not itmmask:
            path = path or self.track_key_tree(index.model().itemFromIndex(index))
            itmmask = self.get_mask_for_item(path) or {}

        reslist, resvallist, resvalaltlist = [], [], []
        if itmmask:
            for key, val in itmmask.items():
                k = str(key)
                if "__m__" in k:
                    # primary value key
                    restriction = itmmask.get(k)
                    primary_key = k.replace("__m__", "__mv__")
                    alt_key = k.replace("__m__", "__ma__")
                    primary_val = itmmask.get(primary_key)
                    alt_val = itmmask.get(alt_key, None)
                    reslist.append(restriction)
                    resvallist.append(primary_val)
                    resvalaltlist.append(alt_val)
        return reslist, resvallist, resvalaltlist
    
    def check_item_by_mask(self, index: QtCore.QModelIndex, val, isok=True, do_log: bool=True):
        """
        Evaluate all mask entries for the item at `index`. Returns boolean.
        Uses get_item_restriction_resval to obtain restrictions.
        """
        try:
            reslist, resvallist, resvalaltlist = self.get_item_restriction_resval(index)
        except Exception:
            return isok

        # quick exit if no restrictions
        if not reslist:
            return isok

        # evaluate each restriction; if any fails, return False
        for restriction, primary, alt in zip(reslist, resvallist, resvalaltlist):
            ok_primary = self.checkitem_value_with_mask(restriction, primary, val)
            ok_alt = ok_primary
            if alt is not None:
                ok_alt = self.checkitem_value_with_mask(restriction, alt, val)
            isok = isok and (ok_primary or ok_alt)

            # special-case unique ID check (keeps your original behavior)
            if restriction == "is_unique" and "ID" in (index.data(USER_ROLE) or {}).get("path", []):
                idlist = self.get_ID_list()
                if val in idlist:
                    isok = False

            if not isok and do_log:
                # Extract item name (from ITEM column)
                stored = index.data(USER_ROLE)
                path = stored.get("path", [])
                # ITEM column is always column 0 in your model_fields
                item_name = str(path)               
                # Build readable restriction description
                if alt is not None:
                    expected = f"{primary} or {alt}"
                else:
                    expected = f"{primary}"
                log.info(
                    f'Item "{item_name}" failed restriction "{restriction}": {expected}, got {val}'
                )
            if not isok:
                break

        return isok
    
    def checkitem_value_with_mask(self, restriction, restrictionval, value) -> bool:
        """
        Unified evaluator for mask restrictions. Returns True if `value` satisfies `restriction`.
        Supports the full set of restrictions from your original code.
        """
        try:
            # Normalize list-like inputs
            alist = self._to_list(value)

            # Numeric comparisons on list items
            if restriction in (
                "is_list_item_value_LT", "is_list_item_value_GT", "is_list_item_value_EQ",
                "is_list_item_value_LTEQ", "is_list_item_value_GTEQ", "is_list_item_value_NEQ"
            ):
                try:
                    cmp_val = float(restrictionval)
                except Exception:
                    return False
                for item in alist:
                    num = self._to_float(item)
                    if num is None:
                        return False
                    if restriction == "is_list_item_value_LT" and not (num < cmp_val):
                        return False
                    if restriction == "is_list_item_value_GT" and not (num > cmp_val):
                        return False
                    if restriction == "is_list_item_value_EQ" and not (num == cmp_val):
                        return False
                    if restriction == "is_list_item_value_LTEQ" and not (num <= cmp_val):
                        return False
                    if restriction == "is_list_item_value_GTEQ" and not (num >= cmp_val):
                        return False
                    if restriction == "is_list_item_value_NEQ" and not (num != cmp_val):
                        return False
                return True

            # List length checks
            if restriction == "is_list_length":
                return len(alist) == int(restrictionval)
            if restriction == "is_list_lengthGT":
                return len(alist) > int(restrictionval)
            if restriction == "is_list_lengthLT":
                return len(alist) < int(restrictionval)

            # Type checks for list items
            if restriction == "is_list_item_type":
                for item in alist:
                    if not self._check_single_type(item, restrictionval):
                        return False
                return True

            # Selection checks
            if restriction == "limited_selection":
                return str(value) in set(restrictionval)
            if restriction == "is_list_item_limited_selection":
                allowed = set(restrictionval)
                for item in alist:
                    if str(item) not in allowed:
                        return False
                return True

            # Format / regex checks
            if restriction == "is_list_item_format":
                for item in alist:
                    if item == "":
                        continue
                    if not self._matches_regex(item, restrictionval):
                        return False
                return True
            if restriction == "is_format":
                if value == "":
                    return False
                return self._matches_regex(value, restrictionval)

            # Single-value numeric comparisons
            if restriction in ("is_value_LT", "is_value_GT", "is_value_EQ",
                            "is_value_LTEQ", "is_value_GTEQ", "is_value_NEQ"):
                try:
                    num = float(value)
                    cmp_val = float(restrictionval)
                except Exception:
                    return False
                if restriction == "is_value_LT":
                    return num < cmp_val
                if restriction == "is_value_GT":
                    return num > cmp_val
                if restriction == "is_value_EQ":
                    return num == cmp_val
                if restriction == "is_value_LTEQ":
                    return num <= cmp_val
                if restriction == "is_value_GTEQ":
                    return num >= cmp_val
                if restriction == "is_value_NEQ":
                    return num != cmp_val

            # Unchangeable / uniqueness / special cases
            if restriction == "is_unique":
                # caller handles uniqueness in context (needs ID list), treat as pass here
                return True
            if restriction == "is_not_change":
                return False

            # Value type check (legacy support for str(type(...)) or short names)
            if restriction == "is_value_type":
                return self._check_single_type(value, restrictionval)

            # Fallback: accept unknown restrictions
            return True

        except Exception:
            return False


    # --- Helpers to include in the same class ---

    def _to_list(self, value):
        """Normalize value to a list of items."""
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, str):
            # preserve empty items if present; change filter if you want to drop empties
            return [p.strip() for p in value.split(",")]
        return [value]

    def _str_to_bool_or_none(self,astr):
        if self.is_bool(astr)==True:
            return astr
        elif type(astr)==type(''):
            if astr.lower() in ['true']:   
                return True
            elif astr.lower() in ['false']:   
                return False
            else:
                return None
        else:
            return None

    def _to_float(self, s):
        """Convert to float or return None."""
        try:
            return float(s)
        except Exception:
            return None

    def _matches_regex(self, text, pattern) -> bool:
        """Return True if text fully matches pattern (pattern can be a regex string)."""
        try:
            import re
            return re.fullmatch(str(pattern), str(text)) is not None
        except Exception:
            return False

    def _check_single_type(self, item, type_spec) -> bool:
        """
        Check a single item against a type specification.
        Supports Python types, short names ('int','float','bool','list','str'),
        and legacy str(type(...)) values.
        """
        # Normalize type_spec to short name
        if isinstance(type_spec, type):
            tname = type_spec.__name__
        else:
            ts = str(type_spec)
            if "int" in ts and "float" not in ts:
                tname = "int"
            elif "float" in ts:
                tname = "float"
            elif "bool" in ts:
                tname = "bool"
            elif "list" in ts:
                tname = "list"
            else:
                tname = ts.strip().lower()

        if tname == "int":
            return self._to_float(item) is not None and float(item).is_integer()
        if tname == "float":
            return self._to_float(item) is not None
        if tname == "bool":
            return self._str_to_bool_or_none(item) is not None
        if tname == "list":
            return isinstance(item, (list, tuple)) or (isinstance(item, str) and "," in item)
        # default accept for 'str' or unknown
        return True


    # -------------------------
    # get_mask_for_item
    # -------------------------
    def get_mask_for_item(self, track:list)->dict:
        """Get mask from main_struct in meta information

        Args:
            track (list): item track path

        Returns:
            dict: dictionary with masks "__m#__","__ma#__","__mav#__" and "__mv#__"
        """
        mask = self.tracker.get_value(track + ["meta[mask]"])
        return mask if isinstance(mask, dict) else {}

    # -------------------------
    # check_item_by_type
    # -------------------------
    def check_item_by_type(self, index: QtCore.QModelIndex, val: Any, isok: bool = True, do_log: bool=True) -> bool:
        """
        Validate value by declared type. Prefer metadata stored in USER_ROLE (meta['type']),
        otherwise read the TYPE column (column 2).
        """
        # try to read metadata from USER_ROLE
        try:
            stored = index.data(USER_ROLE)
        except Exception:
            stored = None

        the_type = None
        if isinstance(stored, dict):
            the_type,_ =self._get_type_subtype(stored)
        # if not the_type:
            # # fallback to TYPE column text
            # col=self._get_column_from_fields_name("TYPE")
            # if col:
            #     type_idx = index.sibling(index.row(), col) if index.isValid() else None
            #     if type_idx and type_idx.isValid():
            #         try:
            #             type_item = type_idx.model().itemFromIndex(type_idx)
            #             the_type = type_item.text() if type_item is not None else type_idx.data(QtCore.Qt.ItemDataRole.DisplayRole)
            #         except Exception:
            #             the_type = type_idx.data(QtCore.Qt.ItemDataRole.DisplayRole)
        
        # normalize type string if needed
        if isinstance(the_type, str):
            the_type = the_type.strip().lower()
        
        isok=self.check_type(the_type, val, isok)

        if not isok and do_log:
            # Extract item name (from ITEM column)
            stored = index.data(USER_ROLE)
            path = stored.get("path", [])
            # ITEM column is always column 0 in your model_fields
            item_name = str(path)               
            # Build readable restriction description
            log.info(
                f'Item "{item_name}" failed type restriction "{the_type}"'
            )
        return isok

    # -------------------------
    # check_type
    # -------------------------
    def check_type(self, the_type: Optional[str], val: Any, isok: bool = True) -> bool:
        """
        Validate `val` against a normalized type name:
        'int', 'float', 'bool', 'str', 'list', 'dict'
        Accepts legacy str(type(...)) values as well.
        Returns True if val matches the_type, else False.
        """
        if the_type is None:
            return isok

        # Normalize legacy str(type(...)) patterns to short names
        t = str(the_type)
        if "int" in t and "float" not in t:
            tname = "int"
        elif "float" in t:
            tname = "float"
        elif "bool" in t:
            tname = "bool"
        elif "list" in t:
            tname = "list"
        elif "dict" in t:
            tname = "dict"
        elif "str" in t or t == "":
            tname = "str"
        else:
            tname = t.lower()

        try:
            if tname == "int":
                # allow numeric strings with optional whitespace
                if isinstance(val, int):
                    return True
                if isinstance(val, float) and val.is_integer():
                    return True
                if isinstance(val, str):
                    return re.fullmatch(r"[-+]?\d+", val.strip()) is not None
                return False

            if tname == "float":
                if isinstance(val, (int, float)):
                    return True
                if isinstance(val, str):
                    try:
                        float(val.strip())
                        return True
                    except Exception:
                        return False
                return False

            if tname == "bool":
                # accept Python bool or common textual forms
                if isinstance(val, bool):
                    return True
                if isinstance(val, str):
                    return val.strip().lower() in ("1", "0", "true", "false", "yes", "no", "y", "n")
                return False

            if tname == "str":
                # everything can be represented as string; accept unless you want stricter rules
                return True

            if tname == "dict":
                return isinstance(val, dict) or (isinstance(val, str) and val.strip().startswith("{") and val.strip().endswith("}"))

            if tname == "list":
                # accept list/tuple or comma-separated string
                if isinstance(val, (list, tuple)):
                    return True
                if isinstance(val, str):
                    # treat empty string as empty list? keep your previous behavior
                    return "," in val or val.strip() == ""
                return False

            # unknown type: be permissive
            return True

        except Exception:
            return False
    
    def get_tracked_value_in_struct(self, track, any_struct):
        """
        Resolve and return a value from a nested structure using a tracker.

        Supports bracket-style paths such as "meta[key]" and automatic
        navigation through dicts, lists, and 'children' wrappers.

        Args:
            track (list): A list of path components describing the location.
            any_struct (dict or list): The root structure to navigate.

        Returns:
            Any: The resolved value, or None if the path cannot be navigated.
        """
        tracker = TreeStructTracker(any_struct)
        return tracker.get_value(track)

    def get_dict_max_depth(self, adict, depth: int = 0) -> int:
        """
        Compute the maximum depth of real items in the canonical structure.
        Uses the tracker's depth logic, which ignores meta and children wrappers.
        """
        tracker = TreeStructTracker(adict)
        return tracker.get_struct_item_depth(tracker.struct, depth)
    
    def get_depth_from_paths(self):
        """
        Compute the maximum depth of real (viewed) items in the canonical structure.
        Uses the self.modelobj.
        """
        max_depth = 0

        def walk(index):
            nonlocal max_depth
            item = self.modelobj.itemFromIndex(index)
            if item:
                stored = item.data(USER_ROLE)
                if isinstance(stored, dict):
                    path = stored.get("path", [])
                    max_depth = max(max_depth, len(path))

            rows = self.modelobj.rowCount(index)
            for r in range(rows):
                walk(self.modelobj.index(r, 0, index))

        walk(QtCore.QModelIndex())
        return max_depth

    def apply_tooltip(self, item: QtGui.QStandardItem):
        """Apply to item a tooltiptext

        Args:
            item (QtGui.QStandardItem): item
        """
        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            node = stored.get("node", {})
            if not isinstance(node, dict):
                return
            tip_key = node.get("tooltip_key")

            if tip_key and tip_key in self.tooltip_dict:
                item.setData(self.tooltip_dict[tip_key], QtCore.Qt.ItemDataRole.ToolTipRole)
        except AttributeError:
            pass
    
    def apply_icon(self, item: QtGui.QStandardItem):
        """Apply to item an icon

        Args:
            item (QtGui.QStandardItem): item
        """
        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            node = stored.get("node", {})
            if not isinstance(node, dict):
                return
            icon_key = node.get("icon_key")

            if icon_key and icon_key in self.icon_dict:
                item.setData(self.icon_dict[icon_key], QtCore.Qt.ItemDataRole.DecorationRole)
        except AttributeError:
            pass
    
    def apply_background(self, item: QtGui.QStandardItem):
        """Apply to item an background

        Args:
            item (QtGui.QStandardItem): item
        """
        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            node = stored.get("node", {})
            if not isinstance(node, dict):
                return
            bg_key = node.get("bg_key")

            if bg_key and bg_key in self.backgroundcolor_dict:
                color = self.backgroundcolor_dict[bg_key]
                item.setData(QtGui.QBrush(QtGui.QColor(color)), QtCore.Qt.ItemDataRole.BackgroundRole)
        except AttributeError:
            pass
    
    def apply_foreground(self, item: QtGui.QStandardItem):
        """Apply to item an foreground

        Args:
            item (QtGui.QStandardItem): item
        """
        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            node = stored.get("node", {})
            if not isinstance(node, dict):
                return
            fg_key = node.get("fg_key")

            if fg_key and fg_key in self.backgroundcolor_dict:
                color = self.foregroundcolor_dict[fg_key]
                item.setData(QtGui.QBrush(QtGui.QColor(color)), QtCore.Qt.ItemDataRole.ForegroundRole)
        except AttributeError:
            pass
    
    def apply_style(self, item: QtGui.QStandardItem):
        """Apply to item a style

        Args:
            item (QtGui.QStandardItem): item
        """
        try:
            stored = item.data(USER_ROLE)
            if not isinstance(stored, dict):
                return

            node = stored.get("node", {})
            if not isinstance(node, dict):
                return
            style_key = node.get("style_key")

            if style_key and style_key in self.style_dict:
                style = self.style_dict[style_key]
                if "bg" in style:
                    item.setData(QtGui.QBrush(QtGui.QColor(style["bg"])), QtCore.Qt.ItemDataRole.BackgroundRole)
                self._get_index_key_for_item
                # track = self.track_key_tree(item)
                # index = self.index_from_track(track)
                for role_txt,(role, role_type) in self.roles_map.items():
                    if role_txt in style:
                        if isinstance(style[role_txt],role_type):
                            self._set_role_item_index(self.modelobj,style[role_txt],item,None,role)
        except AttributeError as eee:
            print("decorate error -> ",eee)
            pass

    def set_role_by_track(self, model: QtCore.QAbstractItemModel, track:list, 
                          column:int, obj, role: QtCore.Qt.ItemDataRole)->bool:
        """Sets a role to one or more items in the track

        Args:
            model (QtCore.QAbstractItemModel): model object
            track (list): track list
            column (int): column number to apply
            obj (any): object of type according to role
            role (QtCore.Qt.ItemDataRole): 
            DisplayRole         -> str
            ToolTipRole         -> str
            StatusTipRole       -> str
            WhatsThisRole       -> str
            DecorationRole      -> QIcon | QPixmap
            ForegroundRole      -> QColor | QBrush
            BackgroundRole      -> QColor | QBrush
            FontRole            -> QFont
            TextAlignmentRole   -> Qt.AlignmentFlag
            CheckStateRole      -> Qt.CheckState
            SizeHintRole        -> QSize
            UserRole+N          -> anything
            
        Returns:
            bool: True when applied else False
        """
        _, _, _, index_list= self.get_item_from_track(model, track)

        if not index_list:
            return False
        
        for index in index_list:
            idx = index.sibling(index.row(), column)
            model.setData(idx, obj, role)
        return True
    
    def apply_column_styles(self, index: QtCore.QModelIndex, column: int =None):
        """Set style on a column using an index from the same row.

        Args:
            index (QtCore.QModelIndex): index of item
            column (int, optional): column to style. None sets the same column as index column. 
                Defaults to None.
        """
        if column is None:
            column = index.column()
        idx = index.sibling(index.row(), column)
        if not idx.isValid():
            return
        key_dict=self._get_index_key_for_item(idx)
        if not key_dict.get("item") and not key_dict.get("column"):
            for child_field, child_dict in key_dict.items():
                if child_dict["column"] == column:
                    item=child_dict["item"]        
                    break
        else:                
            item=key_dict["item"]
        stored = item.data(USER_ROLE)
        if not isinstance(stored, dict):
            return

        node = stored.get("node", {})
        if not isinstance(node, dict):
            return
        style_key = node.get("style_key")
        
        style = None
        if style_key and style_key in self.style_dict:
            style = self.style_dict[style_key]
        if not style:
            return

        for role_txt, (role, role_type) in self.roles_map.items():
            if role_txt not in style:
                continue
            obj = style[role_txt]
            if isinstance(obj, role_type):
                self._set_role_item_index(self.modelobj, obj, None, idx, role)

    def decorate_item(self, item: QtGui.QStandardItem,with_icon=True, 
                      index: QtCore.QModelIndex = None):
        """Decorate an item sets icon,tooltip, background and style.

        Args:
            item (QtGui.QStandardItem): item
            index (QtCore.QModelIndex) : index contains row,column, parent information. Item is just the ro
        """
        if item is None and index is not None:
            key_dict= self._get_index_key_for_item(index)
            item = key_dict["item"]
        if with_icon:
            self.apply_icon(item)
        self.apply_tooltip(item)
        self.apply_background(item)
        self.apply_foreground(item)
        self.apply_style(item)
        if item  and index is not None:
            self.apply_column_styles(index,index.column())
    
    

MAX_ARITY=4 # maximum size for items adding objects

class TypedItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent=parent

    def _get_meta(self,stored):
        """Helper to get meta dictionary"""
        if isinstance(stored, dict):
            node = stored.get("node")
            if not isinstance(node,dict):
                return {}
            return node.get("meta", {})
        return {}
    
    def _get_type_subtype(self,stored):
        """Helper to get type and subtype 
        Returns:
         tuple: valtype, subtype
         """
        node = stored.get("node")
        meta=self._get_meta(stored)
        valtype = node.get("type", "str")
        subtype = node.get("subtype") or meta.get("subtype", "")
        return valtype,subtype

    def _createEditor_full(self, parent, option, index):
        stored = index.data(USER_ROLE) or {}
        meta=self._get_meta(stored)
        t,_ = self._get_type_subtype(stored)
        is_restriction=False
        try:
            reslist, resvallist, _ = self._parent.get_item_restriction_resval(index)
            if reslist and len(reslist)>0:
                is_restriction=True
        except Exception:
            is_restriction=False
        # numeric editors
        if t == "int":
            editor = QtWidgets.QSpinBox(parent)
            editor.setRange(-999999, 999999)
            c = meta.get("constraints", {}) or {}
            if "min" in c: editor.setMinimum(int(c["min"]))
            if "max" in c: editor.setMaximum(int(c["max"]))
            return editor

        if t == "float":
            editor = QtWidgets.QDoubleSpinBox(parent)
            c = meta.get("constraints", {}) or {}
            editor.setRange(-999999.0, 999999.0)
            if "min" in c: editor.setMinimum(float(c["min"]))
            if "max" in c: editor.setMaximum(float(c["max"]))
            editor.setDecimals(meta.get("decimals", 6))
            return editor
        
        if t == "color":
            editor = ColorEditor(parent)
            editor.colorChanged.connect(self.commitData, QtCore.Qt.ConnectionType.DirectConnection)
            editor.colorChanged.connect(self.closeEditor, QtCore.Qt.ConnectionType.DirectConnection)
            editor.installEventFilter(self)
            return editor
        
        # boolean as checkbox
        if t == "bool":
            editor = QtWidgets.QCheckBox(parent)
            editor.setAutoFillBackground(True)
            return editor

        # limited selection -> combo
        options = meta.get("options") or meta.get("constraints", {}).get("options")
        if options:
            combo = QtWidgets.QComboBox(parent)
            combo.addItems([str(x) for x in options])
            return combo
        if is_restriction:
            for res, resval in zip(reslist, resvallist):
                if res in ['limited_selection']: #'is_list_item_limited_selection'
                    combo = QtWidgets.QComboBox(parent)
                    combo.addItems([str(x) for x in resval])
                    return combo
        
        # list or coords: if arity small, build small widget of spinboxes; else use line edit
        if t in ("list","coords"):
            c = meta.get("constraints", {}) or {}
            arity = c.get("arity")
            subtype = meta.get("subtype")
            if arity and int(arity) <= MAX_ARITY and subtype in ["str"] and is_restriction:
                w = QtWidgets.QWidget(parent)
                layout = QtWidgets.QHBoxLayout(w)
                layout.setContentsMargins(0,0,0,0)
                editors = []
                for i in range(int(arity)):
                    for res, resval in zip(reslist, resvallist):
                        if res in ['is_list_item_limited_selection']: 
                            sb = QtWidgets.QComboBox(parent)
                            sb.addItems([str(x) for x in resval])
                        layout.addWidget(sb)
                        editors.append(sb)
                w._editors = editors
                return w
            elif arity and int(arity) <= MAX_ARITY and subtype in ["int","float"]:
                # small composite widget
                w = QtWidgets.QWidget(parent)
                layout = QtWidgets.QHBoxLayout(w)
                layout.setContentsMargins(0,0,0,0)
                editors = []
                c = meta.get("constraints", {}) or {}
                if "min" in c: cmin=c.get("min",None)
                if "max" in c: cmax=c.get("max",None)
                for i in range(int(arity)):
                    if subtype == "int":
                        sb = QtWidgets.QSpinBox(w)
                        sb.setRange(-999999, 999999)
                        if isinstance(cmin,list) and len(cmin)==int(arity):
                            sb.setMinimum(int(cmin[i]))
                        if isinstance(cmax,list) and len(cmax)==int(arity):
                            sb.setMaximum(int(cmax[i]))
                    else:
                        sb = QtWidgets.QDoubleSpinBox(w)
                        sb.setRange(-999999.0, 999999.0)
                        sb.setDecimals(meta.get("decimals", 3))
                        if isinstance(cmin,list) and len(cmin)==int(arity):
                            sb.setMinimum(float(cmin[i]))
                        if isinstance(cmax,list) and len(cmax)==int(arity):
                            sb.setMaximum(float(cmax[i]))
                    layout.addWidget(sb)
                    editors.append(sb)
                w._editors = editors
                return w
            else:
                le = QtWidgets.QLineEdit(parent)
                return le

        # fallback: plain line edit (use regex validator if provided)
        le = QtWidgets.QLineEdit(parent)
        regex = meta.get("constraints", {}).get("regex")
        if regex:
            validator = QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(str(regex)), le)
            le.setValidator(validator)
        return le

    def setEditorData(self, editor, index):
        stored = index.data(USER_ROLE) or {}
        # meta = self._get_meta(stored)
        node = stored.get("node", {})
        if not isinstance(node,dict):
            return
        val = node.get("value")
        # t ,_ = self._get_type_subtype(stored)

        if isinstance(editor, QtWidgets.QSpinBox):
            try: editor.setValue(int(val))
            except: editor.setValue(0)
            return
        if isinstance(editor, QtWidgets.QDoubleSpinBox):
            try: editor.setValue(float(val))
            except: editor.setValue(0.0)
            return
        if isinstance(editor, QtWidgets.QCheckBox):
            editor.setChecked(bool(val))
            return
        if isinstance(editor, QtWidgets.QComboBox):
            idx = editor.findText(str(val))
            if idx >= 0: editor.setCurrentIndex(idx)
            return
        if isinstance(editor, ColorEditor): 
            editor.setColor(val) 
            return
        # composite widget for small lists
        if hasattr(editor, "_editors"):
            parts = val if isinstance(val, (list,tuple)) else (str(val).split(",") if val else [])
            for i, ed in enumerate(editor._editors):
                if isinstance(ed, QtWidgets.QComboBox):
                    idx = ed.findText(str(parts[i]))
                    if idx >= 0: ed.setCurrentIndex(idx)
                else:
                    try:
                        ed.setValue(float(parts[i]))
                    except Exception:
                        ed.setValue(0)
            return
        # line edit fallback
        if isinstance(editor, QtWidgets.QLineEdit):
            # print(f"{type(self._parent)} -> {dir(self._parent)}")
            if hasattr(self._parent,"_value_to_display"):
                editor.setText(self._parent._value_to_display(val))
            else:
                editor.setText(str(val))
            return

    def setModelData(self, editor, model, index):
        # extract value from editor
        if isinstance(editor, QtWidgets.QSpinBox):
            new_val = editor.value()
        elif isinstance(editor, QtWidgets.QDoubleSpinBox):
            new_val = editor.value()
        elif isinstance(editor, QtWidgets.QCheckBox):
            new_val = editor.isChecked()
        elif isinstance(editor, QtWidgets.QComboBox):
            new_val = editor.currentText()
        elif hasattr(editor, "_editors"):
            new_val = [ed.value() for ed in editor._editors]
        elif isinstance(editor, QtWidgets.QLineEdit):
            new_val = editor.text()
        elif isinstance(editor, ColorEditor):
            new_val = editor.color().name(QtGui.QColor.NameFormat.HexArgb)
        else:
            new_val = None

        # Write raw value into model → triggers itemChanged
        model.setData(index, new_val, QtCore.Qt.ItemDataRole.EditRole)
    
    def createEditor(self, parent, option, index):
        stored = index.data(USER_ROLE) or {}
        node = stored.get("node", {})
        t = node.get("type")

        # Special case: color editor
        if t == "color":
            editor = ColorEditor(parent=parent)
            # Connect colorChanged → commitData(editor)
            editor.colorChanged.connect(lambda _c: self.commitData.emit(editor))
            # Connect colorChanged → closeEditor(editor)
            editor.colorChanged.connect(lambda _c: self.closeEditor.emit(editor))
            editor.installEventFilter(self)
            return editor

        # Otherwise use your full logic
        return self._createEditor_full(parent, option, index)
    
    def eventFilter(self, editor, event):
        # Prevent commit when editor loses focus (because dialog opens)
        if isinstance(editor, ColorEditor):
            if event.type() == QtCore.QEvent.Type.FocusOut:
                return True  # block default behavior
        return super().eventFilter(editor, event)


class ColorEditor(QtWidgets.QPushButton):
    colorChanged = QtCore.pyqtSignal(QtGui.QColor)

    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor(color) if color else QtGui.QColor("white")
        self.setMaximumWidth(80)
        self.update_style()
        QtCore.QTimer.singleShot(0, self.pick_color)
        # self.clicked.connect(self.pick_color)

    def update_style(self):
        self.setStyleSheet(f"background-color: {self._color.name(QtGui.QColor.NameFormat.HexArgb)};")

    def pick_color(self):
        dlg = QtWidgets.QColorDialog(self._color, self, 
           options=QtWidgets.QColorDialog.ColorDialogOption.DontUseNativeDialog)
        dlg.setOption(QtWidgets.QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        new = dlg.getColor()
        if new.isValid():
            self._color = new
            self.update_style()
            self.colorChanged.emit(new)

    def color(self):
        return self._color

    def setColor(self, color):
        self._color = QtGui.QColor(color)
        self.update_style()
