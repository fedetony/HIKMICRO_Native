# -*- coding: utf-8 -*-
#*********************************
# Author :F. Garcia
# Created 17.01.2026
#*********************************

import copy
from PyQt6 import QtCore
import deepdiff
from dataclasses import dataclass, field
from typing import Any

"""
Canonical Configuration Structure
=================================

This file defines the canonical hierarchical structure used by the editor,
validator, and tracker. The structure is a nested tree of *nodes*, where each
node is represented as:

    { "<NodeName>": <NodeData> }

The root of the structure is a plain dictionary containing one or more
top‑level groups. Each group maps to a list of nodes.

---------------------------------------------------------------------------
ROOT STRUCTURE
---------------------------------------------------------------------------

The root is always a dictionary:

    {
        "<GroupName>": [ <Node>, <Node>, ... ],
        "<AnotherGroup>": [ ... ],
        ...
    }

The root is *not* a node and must not contain node properties such as
"value", "type", "unit", "info", etc.

---------------------------------------------------------------------------
NODE STRUCTURE
---------------------------------------------------------------------------

A node is always a dictionary with value key:
    { "<NodeName>": {"value": <any>,..<other data fields>} }

< NodeData > is a dictionary describing the node's value, type, metadata,
and optionally its children.

Common fields inside <NodeData>:
    value       (required) The actual stored value (int, float, bool, str, list, coords…)
    type        The type of the value ("int", "float", "bool", "list", "str", "coords", ...) defaults to "str"
    subtype     For value with type list or coords: type of elements ("str", "int", "float", "list", "dict")
    <style, bg, icon, tooltip>_key   Optional UI key referencing to cache dictionary in set_tooltip_cache
    additonal user defined fields in fields dict:
        unit        Optional unit string (e.g. "mm")
        info        Optional user‑visible description

Nodes may contain nested nodes via:
    children    A list of child nodes, {"child1": { value:"",...}} form

Example:
    {"Origin": {
        "value": [10.0, 20.0],
        "type": "coords",
        "unit": "mm",
        "children": [ {"child1": {...}}, {"child2": {...}} ]
    }}

---------------------------------------------------------------------------
META STRUCTURE
---------------------------------------------------------------------------

Each node may contain a "meta" dictionary with optional behavior modifiers.

Supported meta fields:
    options                 List of allowed values (for list/enum types) (combo)
    subtype                 Element type for lists/coords (prefers the property over this)
    decimals                Number of decimals for float display
    refresh_on_change       UI should refresh when this value changes
    restore_all_properties  Reset all properties (except value) when this node changes (allows user select texts and copy)
    restore_<property>      Reset a specific property when this node changes

    constraints: {
        min                 Minimum allowed value (scalar or list)
        max                 Maximum allowed value (scalar or list)
        arity               Required length (for coords or fixed lists)
        subtype             Override element subtype
    }

    mask: {
        "__m__"             Mask rule name (e.g. "is_value_LT")
        "__mv__"            Mask comparison value
    }

Example:
    "meta": {
        "constraints": {"min": 0, "max": 100},
        "decimals": 3
    }

---------------------------------------------------------------------------
CHILDREN VS LIST NODES
---------------------------------------------------------------------------

Nodes may contain nested nodes in two ways:
1. As a list of nodes:
        {"Group": [ {"A": {...}}, {"B": {...}} ]}
2. As a node with a "children" field:
        {"Group": {
            "children": [ {"A": {...}}, {"B": {...}} ]
        }}
Both forms are valid and supported.

---------------------------------------------------------------------------
NOTES
---------------------------------------------------------------------------
This structure is used by:
    - the tracker (path navigation)
    - the validator (constraints, masks)
    - the model (Qt tree representation)
    - the editor (UI rendering and editing)

---------------------------------------------------------------------------
TRACK PATH RESOLUTION
---------------------------------------------------------------------------

A track identifies either a node or a property inside a node.

If the path terminates at a node name:
    the tracker returns the complete node structure.

Example:

    ["Devices", "0", "Details", "Model"]

returns:

    {
        "value": "Samsung",
        "type": "str",
        "meta": {...}
    }


If the path includes a property selector:
    the tracker returns only that property.

Example:

    ["Devices", "0", "Details", "Model[value]"]

returns:

    "Samsung"


Examples:

Node:
    ["Devices", "0"]

returns:
    {
        "children": [...],
        "meta": {...}
    }


Node property:
    ["Devices", "0[Details[Model[value]]]"]

returns:
    "Samsung"


Metadata property:
    ["Devices", "0[Details[Model[meta[hidden]]]]"]

returns:
    True / False


---------------------------------------------------------------------------
PROPERTY SELECTORS
---------------------------------------------------------------------------

Property selectors use square brackets after a node name.

Common node properties:

    [value]
    [type]
    [subtype]
    [children]
    [meta]
    ... user can add more of them

Metadata can be further accessed:

    [meta[hidden]]
    [meta[editable]]
    [meta[conditions]]
    [meta[constraints[min]]]


Without a property selector, the complete node is returned.

    ----------------------------------------------------------------------
    Track Syntax
    ----------------------------------------------------------------------

    Tracks identify nodes or properties inside the canonical structure.

    A track without a property selector returns the complete node.

        ["Devices", "0", "Details", "Model"]

    returns the Model node:

        {
            "value": "...",
            "type": "str",
            "meta": {...}
        }


    A property selector returns only that property.

        ["Devices", "0", "Details", "Model[value]"]

    returns:

        "Samsung"


    Nested property selectors are supported:

        ["Devices", "0", "Details", "Model[meta[hidden]]"]

    returns:

        True / False


    Equivalent compact notation is supported:

        ["Devices", "0", "Details[Model[value]]"]

        ["Devices[0[Details[Model[value]]]]"]


    The tracker internally normalizes paths before navigation.

    ----------------------------------------------------------------------
    Reading API
    ----------------------------------------------------------------------

    get_value(track)
        Returns the resolved object at the given path.
        Depending on the track, this may be:
            - a complete node
            - a node property
            - a metadata value

    ----------------------------------------------------------------------
    Writing API
    ----------------------------------------------------------------------

    set_value(track, value, subtype='')
        Updates an existing value or property.
        Does not create missing nodes.

    ----------------------------------------------------------------------
    Structure Management
    ----------------------------------------------------------------------

    create_node(track, node_dict)
        Creates a new node including all track path.

    add_child(track, child_name, child_node)
        Adds a child node. The track path must exist.

    insert_child(track, index, child_name, child_node)
        Inserts a child node at a specific position. Useful for sorting.

    delete_node(track)
        Deletes a node from its parent branch.

    rename_node(track, new_name)
        Renames a node while preserving its contents.

    move_node(source_track, destination_track)
        Moves a node between branches.

    ----------------------------------------------------------------------
    Traversal API
    ----------------------------------------------------------------------

    remove_property_from_all_nodes(node, property_name)
        Removes a property recursively from the structure.

    ----------------------------------------------------------------------
    Condition Engine Integration
    ----------------------------------------------------------------------

    The tracker provides the storage layer used by ConditionEngine.

    Conditions may access nodes through:

        node_get(path)

    and modify nodes through:

        me_set(property, value)


    Example:

        node_get('Settings[Show[value]]')

        me_set('meta[hidden]', True)


    Condition metadata is stored inside:

        node["meta"]["conditions"]

    and evaluated externally by ConditionEngine.

    ----------------------------------------------------------------------
    Design Notes
    ----------------------------------------------------------------------

    TreeStructTracker intentionally contains no knowledge of:

        - Qt widgets
        - models/delegates
        - rendering
        - layouts

    It is a pure data model layer.

    Any frontend can consume the canonical structure:
        - QTreeView
        - QTableView
        - JSON serializer
        - configuration editor
        - command line tools

"""


@dataclass
class ValidationResult:
    found: bool = False

    track: list = field(default_factory=list)

    node: Any = None
    parent_node: Any = None
    parent_key: Any = None

    is_node: bool = False
    is_branch: bool = False
    is_root: bool = False

    has_children: bool = False
    children_count: int = 0
    children_keys: list = field(default_factory=list)

    has_type: bool = False
    has_subtype: bool = False
    has_meta: bool = False

class TreeStructTracker(QtCore.QObject):
    """
    TreeStructTracker
    =================

    A high‑level manager for your canonical tree structure.  
    This class provides safe, explicit operations for reading,
    writing, creating, deleting, and restructuring nodes inside
    the hierarchical dictionary/list format used by the treeview.

    ----------------------------------------------------------------------
    Canonical Structure Rules
    ----------------------------------------------------------------------
    - The root is a dictionary: {}.
    - A node may be:
        1) A dictionary with minimum value field such as:
            {
                "value": ...,
                "type": ...,
                "subtype": ...,
                "unit": ...,
                "info": ...,
                "meta": {...},
                "children": [ {...}, {...} ]
            }

        2) A dictionary with only "children":
            { "children": [ {...}, {...} ] }

        3) A list of single‑key dictionaries:
            [
                {"Count": {...}},
                {"Threshold": {...}}
            ]

      Lists represent branches without metadata.  
      If metadata is added to such a branch, the list is automatically
      converted into a dictionary with:
            { "meta": {}, "children": <old_list> }

    - "meta" and "children" are internal node properties and are NOT
      treated as tree items. They are only accessed when explicitly
      requested in a track.

    ----------------------------------------------------------------------
    Navigation
    ----------------------------------------------------------------------
    The tracker uses `_navigate(track)` to walk the structure without
    creating new nodes. It understands:
      - dict nodes
      - list‑of‑single‑key‑dict nodes
      - dict nodes with "children"
    and automatically descends into "children" when appropriate.

    If navigation encounters a list and the next key is "meta" or
    "children", the list is automatically wrapped into a canonical
    dict-with-children node.

    `_navigate()` returns:
        (parent_node, key, node)
    or (None, None, None) if the path does not exist.

    ----------------------------------------------------------------------
    Automatic Branch Conversion
    ----------------------------------------------------------------------
    `_ensure_branch_dict(parent, key)` guarantees that parent[key] is a
    canonical branch node:
        { "children": [...], "meta": {...} }

    This is used when:
      - adding metadata to a list branch
      - adding children to a list branch
      - creating nodes under a list branch

    ----------------------------------------------------------------------
    Public API
    ----------------------------------------------------------------------

    get_value(track)
        Returns the node at the given path, or None if not found.

    set_value(track, value, subtype='')
        Updates an existing node. Does NOT create missing nodes.
        Emits data_changed(track, value, type, subtype).

    create_node(track, node_dict)
        Creates a new node at the given path.
        Automatically converts list branches into dict-with-children.

    add_child(track, child_name, child_node)
        Appends a child to the "children" list of the node at `track`.
        Converts list branches automatically.

    insert_child(track, index, child_name, child_node)
        Inserts a child at a specific index.

    delete_node(track)
        Removes a node from its parent.

    rename_node(track, new_name)
        Renames a node key in dict or list-of-dicts.

    move_node(source_track, dest_track)
        Moves a node from one branch to another.
    ----------------------------------------------------------------------
    Additional Public API
    ----------------------------------------------------------------------

    ensure_path(track)
        Ensures that all branches required by a track exist.

        Missing intermediate nodes are created using canonical branch rules.
        Existing nodes are preserved.

        This is used when dynamically building structures from external data
        such as JSON configurations.


    set_or_create_value(track, value, subtype='')
        Sets a value if the node exists.

        If the path does not exist, creates the required structure first.

        Unlike set_value(), this method is allowed to modify the tree layout.


    set_or_create_property(track, property_name, value)
        Sets a node property.

        If the target node does not exist, the required branches are created.

        Useful for adding metadata or dynamic fields after a structure has
        already been generated.


    add_property_to_all_nodes(node, property_name, value)
        Recursively adds a property to every node below the supplied node.

        Used for global structure modifications such as:
            - adding metadata
            - applying temporary flags
            - preparing nodes for processing


    remove_property_from_all_nodes(node, property_name)
        Recursively removes a property from every node below the supplied node.

        Useful for clearing temporary processing fields, for example:
            - condition evaluation markers
            - UI-only metadata


    copy_node(source_track, destination_track)
        Copies a node and inserts the copy at the destination.

        The original node remains unchanged.


    merge(structure)
        Merges another canonical structure into the current structure.

        Existing compatible nodes are updated while preserving canonical rules.


    diff(structure)
        Compares another structure against the current structure.

        Returns dictionary of differences between structures.


    collapse_at(track)
        Converts a branch representation into a simplified form when possible.


    collapse_branches()
        Simplifies redundant branch structures throughout the tree.


    get_struct_item_depth(track)
        Returns the depth of a track in the hierarchy.


    get_root()
        Returns the current canonical root structure.
    
    validate_node() 
        Returns a structural description of the node at the given track 
        is also used as a defensive layer.
        
        The tracker accepts multiple canonical representations and attempts to
        resolve invalid or incomplete structures without raising exceptions.
        Validation provides enough information for higher-level systems
        (ConditionEngine, editors, serializers) to make decisions safely.
    
    get_validate_node_as_obj() -> ValidationResult:
        This is an object-oriented wrapper around validate_node(). The underlying
        validation is performed by validate_node(), which returns a dictionary;
        this method converts that result into a ValidationResult dataclass.

    ----------------------------------------------------------------------
    Signals
    ----------------------------------------------------------------------
    data_changed(track, value, type, subtype)
        Emitted whenever a node is modified, created, renamed, or deleted.
        The UI layer (treeview) listens to this to refresh or update.

    ----------------------------------------------------------------------
    Usage Example
    ----------------------------------------------------------------------

        tracker = TreeStructTracker(main_struct)

        # Update an existing value
        tracker.set_value(['Settings', 'Enabled', 'value'], True)

        # Create a new node
        tracker.create_node(
            ['Settings', 'NewItem'],
            {"value": 0, "type": "int"}
        )

        # Add a child to a branch
        tracker.add_child(
            ['Settings', 'Origin'],
            'Z',
            {"value": 5.0, "type": "float"}
        )

        # Rename a node
        tracker.rename_node(['Settings', 'Count'], 'Counter')

        # Delete a node
        tracker.delete_node(['Settings', 'Threshold'])

    ----------------------------------------------------------------------
    Notes
    ----------------------------------------------------------------------
    - This class contains NO Qt model/view logic.
      It is purely a data‑model manager.
    - The UI layer should call tracker methods whenever the user edits
      the treeview.
    - The treeview should rebuild itself from the canonical structure
      after each change.
    """
    data_changed = QtCore.pyqtSignal(list, object, str, str)

    def __init__(self, struct: dict):
        super().__init__()
        self.struct = struct

    def _navigate(self, track: list):
        """
        Navigate the structure following the track.
        Returns (parent, key, node) or (None, None, None).
        Automatically converts list branches into dict-with-children
        when accessing 'meta' or 'children'.
        """
        node = self.struct
        parent = None
        key = None
        for k in track:
            parent = node
            key = k
            # --- CASE: field[subfield] syntax ---
            if isinstance(k, str) and "[" in k and k.endswith("]"):
                base, inner = k.split("[", 1)
                inner = inner[:-1]  # strip ']'
                # Step 1: navigate to base field
                if isinstance(node, dict) and base in node:
                    node = node[base]
                elif isinstance(node, dict) and "children" in node:
                    for nnn in node["children"]:
                        if base in nnn:
                            node = nnn[base]
                            break
                else:
                    return None, None, None
                # Step 2: navigate inside base dict
                if isinstance(node, dict) and inner in node:
                    parent = node
                    key = inner
                    node = node[inner]
                    continue
                else:
                    return None, None, None

            # --- dict node ---
            if isinstance(node, dict):
                if k not in node: 
                    if "children" not in node:
                        return None, None, None
                if k in node:
                    node = node[k]
                    continue
                # auto-descend into children
                if isinstance(node, dict) and "children" in node and k not in ("meta", "children"):
                    node = node["children"] # now is a list
                    # Normal list-of-single-key-dicts
                    found = False
                    for entry in node:
                        if isinstance(entry, dict) and k in entry:
                            parent = entry
                            key = k
                            node = entry[k]
                            found = True
                            break
                    if not found:
                        return None, None, None

            # --- list node ---
            elif isinstance(node, list):
                # If next key is meta/children → convert list to dict
                if k in ("meta", "children"):
                    newnode = {
                        "children": node,
                        "meta": {}
                    }
                    # Replace list in parent
                    if isinstance(parent, dict):
                        parent[key] = newnode
                    node = newnode[k]
                    continue
                # Normal list-of-single-key-dicts
                found = False
                for entry in node:
                    if isinstance(entry, dict) and k in entry:
                        parent = entry
                        key = k
                        node = entry[k]
                        found = True
                        break
                if not found:
                    return None, None, None
            else:
                return None, None, None
        return parent, key, node
    
    def get_value(self, track: list) ->dict|list:
        """Returns the node at the given path, or None if not found."""
        parent, key, node = self._navigate(track)
        if node is None:
            return None
        return node
    
    def set_value(self, track: list, value: any, subtype:str='') -> bool:
        """Updates an existing node. Does NOT create missing nodes.
        Emits data_changed(track, value, type, subtype)."""
        parent, key, node = self._navigate(track)

        if parent is None:
            return False

        # If parent[key] is a list and we are writing meta → convert it
        if key == "meta" and isinstance(parent, list):
            # impossible: lists don't have keys
            return False

        # If writing meta to a branch that is currently a list
        if key == "meta" and isinstance(parent[key], list):
            parent[key] = {
                "meta": value,
                "children": parent[key]
            }
            self.data_changed.emit(track, value, "meta", subtype)
            return True

        # Normal write
        parent[key] = value
        self.data_changed.emit(track, value, str(type(value)), subtype)
        return True

    def create_node(self, track: list, node_dict: dict) -> bool:
        """
        Create a new node at the given path.
        Automatically converts list branches into dict-with-children.
        """
        if not track:
            return False

        *parent_path, key = track

        # Top-level creation
        if not parent_path:
            self.struct[key] = node_dict
            self.data_changed.emit(track, node_dict, "dict", "")
            return True

        parent, pkey, parent_node = self._navigate(parent_path)
        if parent_node is None:
            return False

        # If parent is a list → convert to dict-with-children
        if isinstance(parent_node, list):
            parent_node = self._ensure_branch_dict(parent, pkey)

        # Now parent_node is guaranteed to be a dict
        parent_node.setdefault("children", [])

        # Create inside children
        parent_node["children"].append({key: node_dict})
        self.data_changed.emit(track, node_dict, "dict", "")
        return True

    def add_child(self, track: list, child_name: str, child_node: dict) -> bool:
        """Appends a child to the "children" list of the node at `track`.
        Converts list branches automatically."""
        parent, key, node = self._navigate(track)
        if node is None:
            return False

        if isinstance(node, dict):
            node.setdefault("children", [])
            node["children"].append({child_name: child_node})
            self.data_changed.emit(track + [child_name], child_node, "dict", "")
            return True

        return False

    def insert_child(self, track: list, index: int, child_name:str, child_node: dict) -> bool:
        """Inserts a child at a specific index."""
        parent, key, node = self._navigate(track)
        if node is None:
            return False

        if isinstance(node, dict):
            node.setdefault("children", [])
            node["children"].insert(index, {child_name: child_node})
            self.data_changed.emit(track + [child_name], child_node, "dict", "")
            return True

        return False

    def delete_node(self, track: list) -> bool:
        """Removes a node from its parent."""
        if not track:
            return False

        *parent_path, key = track
        parent, pkey, parent_node = self._navigate(parent_path)

        if parent_node is None:
            return False

        if isinstance(parent_node, dict):
            if key in parent_node:
                del parent_node[key]
                self.data_changed.emit(track, None, "delete", "")
                return True
            children_list = parent_node.get('children')
            if children_list:
                #set as list to enter next evaluation
                parent_node = children_list

        if isinstance(parent_node, list):
            for i, entry in enumerate(parent_node):
                if isinstance(entry, dict) and key in entry:
                    del parent_node[i]
                    self.data_changed.emit(track, None, "delete", "")
                    return True

        return False
    
    def _ensure_branch_dict(self, parent: dict, key: str) -> dict:
        """
        Ensure parent[key] is a dict node with:
            { "children": [...], "meta": {...} }

        If parent[key] is a list → wrap it.
        If parent[key] is a dict without children → add children list.
        Returns the dict node.
        """
        node = parent[key]

        # Already correct
        if isinstance(node, dict) and "children" in node:
            node.setdefault("meta", {})
            return node

        # List → wrap into dict
        if isinstance(node, list):
            newnode = {
                "children": node,
                "meta": {}
            }
            parent[key] = newnode
            return newnode

        # Dict without children → add children
        if isinstance(node, dict):
            node.setdefault("children", [])
            node.setdefault("meta", {})
            return node

        # Anything else → convert to empty branch
        newnode = {
            "children": [],
            "meta": {}
        }
        parent[key] = newnode
        return newnode
    
    def rename_node(self, track: list, new_name: str) -> bool:
        """Renames a node key in dict or list-of-dicts."""
        *parent_path, key = track
        parent, pkey, parent_node = self._navigate(parent_path)

        if parent_node is None:
            return False

        if isinstance(parent_node, dict):
            parent_node[new_name] = parent_node.pop(key)
            self.data_changed.emit(parent_path + [new_name], parent_node[new_name], "rename", "")
            return True

        if isinstance(parent_node, list):
            for entry in parent_node:
                if key in entry:
                    entry[new_name] = entry.pop(key)
                    self.data_changed.emit(parent_path + [new_name], entry[new_name], "rename", "")
                    return True
        return False
    
    def move_node(self, source_track: list, dest_track: list) -> bool:
        """Moves a node from one branch to another."""
        parent, key, node = self._navigate(source_track)
        if node is None:
            return False

        # remove from source
        self.delete_node(source_track)

        # add to destination
        self.add_child(dest_track, key, node)

        return True
    
    def set_or_create_value(self, track: list, value: any, subtype: str='')  -> bool:
        """
        Update a value if the node exists, otherwise create the full path.
        """
        parent, key, node = self._navigate(track)

        if parent is not None:
            # Node exists → update
            return self.set_value(track, value, subtype=subtype)

        # Node does not exist → create path
        self.ensure_path(track[:-1])
        was_set=self.set_or_create_property(track, value, subtype=subtype)
        return was_set
    
    def set_or_create_property(self, track: list, value: any, subtype: str='')  -> bool:
        """Sets the property path to Node must exist"""
        was_set=self.set_value(track, value, subtype=subtype)
        if not was_set:
            # Add property if missing
            inner=self.get_value(track[:-1])
            if not isinstance(inner, dict):
                return False
            prop=track[-1]
            field,subfield=self._get_field_subfield_key(prop)
            # create field if does not exist
            if field not in inner:
                if not subfield:
                    inner[field] = ""
                    return self.set_value(track, value, subtype=subtype)
                fff,sfff=self._get_field_subfield_key(subfield)
                if sfff:
                    inner[field] = {f"{fff}":{f"{sfff}":""}}
                else:    
                    inner[field] = {f"{subfield}":""}  
                was_set=self.set_value(track, value, subtype=subtype)   
            # modify field if does not exist
            elif field in inner:
                innd=inner[field]
                if isinstance(innd, dict):
                    fff,sfff=self._get_field_subfield_key(subfield)
                    if sfff:
                        innd.update({f"{fff}":{f"{sfff}":""}})
                    else:    
                        innd.update({f"{subfield}":""})  
                    was_set=self.set_value(track, value, subtype=subtype)  
        return was_set
    
    def _get_field_subfield_key(self,key):
        """returns field,subfield tuple in field[subfield] syntax"""
        base=key
        inner=None
        if isinstance(key, str) and "[" in key and key.endswith("]"):
            base, inner = key.split("[", 1)
            inner = inner[:-1]  # strip ']'
        return base,inner
    
    def ensure_path(self, track: list):
        """
        Ensure that all intermediate nodes in the path exist.
        Creates dict-with-children nodes as needed.
        """
        node = self.struct
        parent = None
        key = None

        for k in track:
            parent = node
            key = k

            if isinstance(node, dict):
                if k not in node:
                    node[k] = {"children": [], "meta": {}}
                node = node[k]

                # descend into children if present
                if isinstance(node, dict) and "children" in node:
                    node = node["children"]

            elif isinstance(node, list):
                # find or create entry
                found = False
                for entry in node:
                    if isinstance(entry, dict) and k in entry:
                        node = entry[k]
                        found = True
                        break
                if not found:
                    newnode = {"children": [], "meta": {}}
                    node.append({k: newnode})
                    node = newnode

                # descend into children
                if isinstance(node, dict) and "children" in node:
                    node = node["children"]

            else:
                # convert to branch
                newnode = {"children": [], "meta": {}}
                parent[key] = newnode
                node = newnode["children"]    

    def copy_node(self, source_track: list, dest_track: list) -> bool:
        """Copies a node to a new destination node"""
        parent, key, node = self._navigate(source_track)
        if node is None:
            return False

        clone = copy.deepcopy(node)
        self.add_child(dest_track, key, clone)
        return True
    
    def get_validate_node_as_obj(self, track: list) -> ValidationResult:
        """
        Returns a ValidationResult object describing the node at the given track.

        This is an object-oriented wrapper around validate_node(). The underlying
        validation is performed by validate_node(), which returns a dictionary;
        this method converts that result into a ValidationResult dataclass.

        Args:
            track: List of keys/indices describing the path to the node.

        Returns:
            ValidationResult containing:

                found: bool
                    True if the node was found, otherwise False.

                track: list
                    The resolved track/path used to locate the node.

                node: object or None
                    The actual node found at the track.

                parent_node: dict, list, or None
                    The container holding the node.

                parent_key: object or None
                    The dictionary key or list index used to reach the node.

                is_node: bool
                    True if the object is a node dictionary containing node fields
                    such as value/type/etc.

                is_branch: bool
                    True if the object is a branch containing children, either a
                    dictionary with children or a list.

                is_root: bool
                    True if the object is the root dictionary, with no parent
                    container or parent key.

                has_children: bool
                    True if the node has one or more children.

                children_count: int
                    Number of direct children.

                children_keys: list
                    Keys or indices used to access the direct children.

                has_type: bool
                    True if the node contains a type field.

                has_subtype: bool
                    True if the node contains a subtype field.

                has_meta: bool
                    True if the node contains metadata.
        """

        val_node = self.validate_node(track) or {}

        return ValidationResult(
            found=val_node.get("found", False),
            track=val_node.get("track", track),
            node=val_node.get("node"),
            parent_node=val_node.get("parent_node"),
            parent_key=val_node.get("parent_key"),

            is_node=val_node.get("is_node", False),
            is_branch=val_node.get("is_branch", False),
            is_root=val_node.get("is_root", False),

            has_children=val_node.get("has_children", False),
            children_count=val_node.get("children_count", 0),
            children_keys=val_node.get("children_keys", []),

            has_type=val_node.get("has_type", False),
            has_subtype=val_node.get("has_subtype", False),
            has_meta=val_node.get("has_meta", False),
        )



    def validate_node(self, track: list) -> dict:
        """
        Returns a structural description of the node at the given track.

        Fields returned:
            found: bool
            track: list
            node: the actual node (or None)
            parent_node: the parent container (dict or list)
            parent_key: the key/index used to reach this node

            is_node: bool          # dict with fields (value/type/etc.)
            is_branch: bool        # dict-with-children OR list
            is_root: bool          # dict-with-keys , no parent, no key
            has_children: bool
            children_count: int
            children_keys: list    # list of the key/index used to reach children

            has_type: bool
            has_subtype: bool
            has_meta: bool
        """

        parent, key, node = self._navigate(track)

        result = {
            "found": node is not None,
            "track": track,
            "node": node,
            "parent_node": parent,
            "parent_key": key,

            "is_node": False,
            "is_branch": False,
            "is_root": False,
            "has_children": False,
            "children_count": 0,
            "children_keys": [],

            "has_type": False,
            "has_subtype": False,
            "has_meta": False,
        }

        if node is None:
            return result

        # --- CASE 1: dict node ---
        if isinstance(node, dict):
            is_root=True
            # Node-like if it has value/type/subtype/meta
            if any(k in node for k in ("value", "type", "subtype", "meta")):
                is_root=False
                result["is_node"] = True

            # Branch-like if it has children
            if "children" in node and isinstance(node["children"], list):
                is_root=False
                result["is_branch"] = True
                result["has_children"] = len(node["children"]) > 0
                result["children_count"] = len(node["children"])
                result["children_keys"] = [
                    list(entry.keys())[0]
                    for entry in node["children"]
                    if isinstance(entry, dict) and len(entry) == 1
                ]
            # --- Metadata ---
            meta = node.get("meta", {})
            result["has_meta"] = isinstance(meta, dict) and len(meta) > 0
            # --- Type / Subtype ---
            node_type = node.get("type")
            node_subtype = node.get("subtype") or meta.get("subtype")
            result["has_type"] = node_type is not None
            result["has_subtype"] = node_subtype is not None

            if parent is None and key is None and is_root:
                #root node
                result["is_root"]=True
                result["has_children"] = len(node.keys()) > 0
                result["children_keys"] = list(node.keys()) if len(node.keys()) > 0 else []

            return result

        # --- CASE 2: list node ---
        if isinstance(node, list):
            result["is_branch"] = True
            result["has_children"] = len(node) > 0
            result["children_count"] = len(node)
            result["children_keys"] = [
                list(entry.keys())[0]
                for entry in node
                if isinstance(entry, dict) and len(entry) == 1
            ]
            return result

        # --- CASE 3: primitive or unexpected ---
        result["is_node"] = True
        return result

    def diff(self, other: dict) -> dict:
        """
        Returns a dict describing differences between self.struct and other.
        """
        return deepdiff.DeepDiff(self.struct, other, ignore_order=True)
    
    def merge(self, other: dict):
        """
        Merge another structure into this one.
        """
        def _merge(a, b):
            if isinstance(a, dict) and isinstance(b, dict):
                for k, v in b.items():
                    if k in a:
                        a[k] = _merge(a[k], v)
                    else:
                        a[k] = copy.deepcopy(v)
                return a

            if isinstance(a, list) and isinstance(b, list):
                return a + copy.deepcopy(b)

            return copy.deepcopy(b)

        _merge(self.struct, other)
        self.data_changed.emit([], None, "merge", "")
    
    def collapse_branches(self, node: dict|list) -> dict:
        """
        Recursively convert canonical branch nodes:
            { "children": [...], "meta": {} }
        back into plain lists.

        Returns the collapsed structure.
        """

        # --- CASE 1: list ---
        if isinstance(node, list):
            return [self.collapse_branches(entry) for entry in node]

        # --- CASE 2: dict ---
        if isinstance(node, dict):

            # If this is a canonical branch
            if "children" in node and isinstance(node["children"], list):

                # Collapse children first
                collapsed_children = [
                    self.collapse_branches(entry) for entry in node["children"]
                ]

                # If meta is empty or irrelevant → return list
                meta = node.get("meta", {})
                if not meta or len(node.keys()) == 2:
                    return collapsed_children

                # Otherwise keep dict but update children
                newnode = dict(node)
                newnode["children"] = collapsed_children
                return newnode

            # Normal dict node → collapse fields recursively
            newnode = {}
            for k, v in node.items():
                newnode[k] = self.collapse_branches(v)
            return newnode

        # --- CASE 3: primitive ---
        return node
    
    def collapse_at(self, track: list) -> dict|list:
        """Collapses at a specific node"""
        parent, key, node = self._navigate(track)
        if node is None:
            return False

        collapsed = self.collapse_branches(node)
        parent[key] = collapsed
        return True
    
    def get_struct_item_depth(self, node: dict, depth=0) -> int:
        """
        Compute depth of real items in the canonical structure.
        Ignores meta and does not count 'children' wrappers.
        """
        if not isinstance(node, dict):
            return depth

        max_depth = depth

        # If this is a branch node with children
        if "children" in node and isinstance(node["children"], list):
            for entry in node["children"]:
                if isinstance(entry, dict):
                    for key, child in entry.items():
                        d = self.get_struct_item_depth(child, depth + 1)
                        max_depth = max(max_depth, d)
            return max_depth

        # Normal dict node: descend into children if present
        for key, val in node.items():
            if key in ("meta", "value", "type", "unit", "info"):
                continue
            d = self.get_struct_item_depth(val, depth + 1)
            max_depth = max(max_depth, d)

        return max_depth
    
    def add_property_to_all_nodes(self, node: dict, prop: str, default: any):
        """
        Add a property to all real nodes, skipping the root container.
        """
        if not isinstance(node, dict):
            return

        # Root or container: multiple keys → descend
        if len(node) != 1:
            for key, val in node.items():
                self.add_property_to_all_nodes(val, prop, default)
            return

        # Real node: exactly one key
        key = next(iter(node))
        inner = node[key]

        # Add property if missing
        if isinstance(inner, dict) and prop not in inner:
            inner[prop] = default

        # If children exist, descend
        if isinstance(inner, dict) and "children" in inner:
            for entry in inner["children"]:
                for _, child in entry.items():
                    self.add_property_to_all_nodes(child, prop, default)
            return

        # If value is a list of nodes, descend
        if isinstance(inner, list):
            for entry in inner:
                self.add_property_to_all_nodes(entry, prop, default)
            return

        # Otherwise descend into inner dict
        if isinstance(inner, dict):
            for k, v in inner.items():
                if k in ("meta", "value", "children"): # or prop in inner.keys(): 
                    continue
                self.add_property_to_all_nodes(v, prop, default)
    
    def _is_real_node(self, node: dict|list) -> bool:
        """Returns True if is a real node, False it's a container (root or branch)"""
        return isinstance(node, dict) and len(node) == 1
    
    def get_root(self) -> dict:
        """Return the root container of the main structure."""
        return self.struct
    
    def remove_property_from_all_nodes(self, node: dict|list, prop: str, remove_value: bool=False):
        """
        Recursively remove a property from all real nodes in the canonical structure.
        - Does NOT remove 'value' unless the programmer explicitly asks for it.
        - Descends through 'children' wrappers.
        - Safe to call even if the property does not exist.
        """
        if not isinstance(node, dict):
            return

        # Programmer decides what is allowed to be removed
        if prop in node:
            del node[prop]

        # If this node has children, descend into them
        if "children" in node and isinstance(node["children"], list):
            for entry in node["children"]:
                if isinstance(entry, dict):
                    for _, child in entry.items():
                        self.remove_property_from_all_nodes(child, prop)
            return

        # Descend into normal dict keys
        for key, val in node.items():
            # Skip value ONLY if the programmer wants
            if key == "value" and not remove_value:
                continue
            self.remove_property_from_all_nodes(val, prop)

