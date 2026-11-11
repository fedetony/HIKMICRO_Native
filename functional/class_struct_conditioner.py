# -*- coding: utf-8 -*-
#*********************************
# Author :F. Garcia
# Created 17.01.2026
#*********************************

import copy
from PyQt6 import QtCore
import deepdiff

from functional.class_struct_tracker import TreeStructTracker

from functional.class_LogHandler import LM
log=LM.get_logger_with_handler("ConditionEngine","debug",True,None)

class ConditionEngine:
    """
    Evaluates dynamic UI conditions attached to nodes in the configuration tree.

    The ConditionEngine walks the entire data structure managed by the Tracker
    and executes any `meta[conditions]` expressions it finds. These expressions
    are written as Python one‑line expressions and evaluated in a restricted
    environment using `eval()`. They allow nodes to react to changes elsewhere
    in the tree (e.g., hide/show, change style, update metadata).

    Key responsibilities:
    - Recursively traverse the configuration structure (dicts, lists, children).
    - Detect and evaluate `meta[conditions]` fields on each node.
    - Provide safe helper functions inside the eval environment:
        * node_get(path) → read any node's value or metadata
        * me_set(field, value) → update metadata or properties on the current node
    - Track whether any condition changed a node, returning True if so.
    - Support reactive UI behavior such as:
        * hiding/showing nodes
        * updating style_key, bg_key, icon_key, tooltip_key
        * enforcing constraints or masks
        * restoring metadata when values change

    Condition syntax:
        Conditions must be valid Python expressions (not statements) and must
        fit on a single line. Multi‑action rules can be grouped using tuples:

            (me_set('meta[style_key]', 'warn'),
             me_set('meta[tooltip_key]', 'Value too high'))
            if node_get('Settings[Count[value]]') > 10
            else (me_set('meta[style_key]', None),
                  me_set('meta[tooltip_key]', None))

        Because JSON cannot store indentation, conditions should use Python's
        ternary operator and tuple grouping instead of multi‑line `if:` blocks.

    Return value:
        evaluate_conditions_in_a_node(node) → bool
            True  if any condition modified any node
            False if no changes occurred

    This return value allows the UI layer to refresh only when necessary.

    The engine is designed to be deterministic, side‑effect‑controlled, and safe
    to run after every data change without causing recursion or instability.
    """  

    def __init__(self, tracker:TreeStructTracker):
        super().__init__()
        self.tracker=tracker
        self.log_info_on_change=True
        
    def _evaluate_conditions(self, node_track, conditions):
        """
        Safely evaluates a single node's condition expression and applies any
        resulting metadata or property updates.

        The condition string must be a valid Python expression (not a statement)
        and is evaluated using `eval()` in a restricted environment. The expression
        may call helper functions exposed in `safe_locals`:

            node_get(path)
                Read-only accessor for any node in the tree. Accepts a string path
                such as "Settings[Count[value]]" and returns the resolved value.

            me_get(field)
                Read-only accessor for properties on the *current* node. This is
                equivalent to node_get() but scoped to the node being evaluated.
                Example: me_get("meta[hidden]") or me_get("value").

            me_set(field, value, subtype='')
                Write accessor for properties on the current node. If the value
                differs from the existing one, the Tracker is updated and the
                condition engine reports that a change occurred.

        Multiple actions can be grouped using tuple expressions, allowing complex
        rules to be written in a single JSON‑safe line:

            (me_set('meta[style_key]', 'warn'),
            me_set('meta[tooltip_key]', 'Too high'))
            if node_get('Settings[Count[value]]') > 10
            else (me_set('meta[style_key]', None),
                me_set('meta[tooltip_key]', None))

        Parameters
        ----------
        node_track : list[str]
            The hierarchical path to the node whose conditions are being evaluated.
            Used by the Tracker to resolve and update metadata.
        conditions : str
            A Python expression representing the condition logic.

        Returns
        -------
        bool
            True  if at least one metadata field was changed by the condition.
            False if no changes occurred or the expression failed.

        Notes
        -----
        - The eval environment contains no builtins except a small safe subset.
        - Errors inside the condition expression are logged and treated as no‑ops.
        - Only me_set() may modify data; node_get() and me_get() are read-only.
        - This method is side‑effect‑controlled and safe to run repeatedly.
        """
        #print(f"Found {node_track}: {conditions}")
        evaluated = False
        def set_to_local(v_or_p:str,value,subtype=''):
            nonlocal evaluated
            if "conditions" in v_or_p:
                return False
            if self.tracker.get_value(node_track+["__conditions__applied__"]):
                log.error(f"Circular reference detected: {node_track+[v_or_p]}")
                return False
            old_value=self.tracker.get_value(node_track+[v_or_p])
            if old_value!=value:
                was_set=self.tracker.set_value(node_track+[v_or_p],value,subtype)
                if self.log_info_on_change:
                    log.info(f"Conditional change applied: {node_track+[v_or_p]} set to {value}")
                evaluated = was_set or evaluated
                if was_set:
                    self.tracker.set_or_create_value(node_track+["__conditions__applied__"],True)
            else:
                was_set= False
            return was_set
        
        def get_me_prop(v_or_p:str):
            if "meta[conditions]" in v_or_p:
                return None
            return self.tracker.get_value(node_track+[v_or_p])

        safe_globals = {"__builtins__": {}}  
        safe_locals = {
            "node_get": self.get_any_node,   # read-only
            "me_set": set_to_local,   # write only on node with condition
            "me_get": get_me_prop,
            "min": min,
            "max": max,
            "abs": abs,
            "int": int,
            "float": float,
            "str": str,
            "list": list,
            "dict": dict,
            "bool": bool,
        }
        try:
            eval(conditions, safe_globals, safe_locals)
        except Exception as eee:
            log.error(f"Evaluating {node_track} {conditions}:\nAvailable functions: {safe_locals.keys()}\n{eee}")
            return False
        return evaluated

    def _get_track_of_path(self,path:str):
        """
        Convert a path like 'Settings[Enabled[value]]' into:
            ['Settings', 'Enabled', 'value']

        Special rules:
            - If path is empty → return None
            - If path contains 'meta[conditions]' → return None
            - If path contains 'children' → return None
            - If meta[...] is nested, keep it as a single element:
                'meta[hidden]' → 'meta[hidden]'
        """
        if not path or not isinstance(path, str):
            return None

        # Reject forbidden patterns early
        if "meta[conditions]" in path:
            return None
        if "children" in path:
            return None

        # Tokenize by splitting on '[' and removing trailing ']'
        tokens = self._split_bracket_path(path)
        # Collapses structure after meta
        tokens = self._collapse_after_list_item(tokens,"meta")
        return tokens
    
    @staticmethod
    def _collapse_after_list_item(parts: list, index_str="meta"):
        """Collapses everything after index_str into nested brackets."""
        if index_str not in parts:
            return parts[:]  # nothing to do
        i = parts.index(index_str)
        head = parts[:i]
        tail = parts[i+1:]
        # Build nested structure from right to left
        nested = None
        for item in reversed(tail):
            if nested is None:
                nested = item
            else:
                nested = f"{item}[{nested}]"
        # Wrap with index_str (e.g. meta[...])
        if nested is None:
            nested = index_str
        else:
            nested = f"{index_str}[{nested}]"
        return head + [nested]


    @staticmethod
    def _split_bracket_path(string_input: str):
        """Converts a string of the form "Settings[Enabled[value]]" into ['Settings', 'Enabled', 'value']

        Args:
            string_input (str): string with val1[val2[...]]

        Returns:
            list: separated value list in order
        """
        parts = []
        current = []

        for char in string_input:
            if char == '[':
                # end of a name before entering brackets
                if current:
                    parts.append(''.join(current))
                    current = []
            elif char == ']':
                # end of a name inside brackets
                if current:
                    parts.append(''.join(current))
                    current = []
            else:
                current.append(char)
        # catch any trailing token
        if current:
            parts.append(''.join(current))

        return parts

    
    def get_any_node(self,path:str):
        track=self._get_track_of_path(path)
        value=None
        if isinstance(track,list):
            value = self.tracker.get_value(track)
        # print(f"got node {value}")
        if value == None:
            log.warning(f"Did not find condition node_get({path}) -> {track}")
        return value

    def evaluate_conditions_in_a_node(self, node: dict, track: list = None):
        """
        Recursively evaluates all condition expressions (`meta[conditions]`) in the
        configuration tree starting from the given node.

        This method walks the structure exactly as the Tracker sees it, following
        nested dicts, lists, and "children" blocks. For each real node (a dict with
        exactly one key), it checks whether the node defines a `meta[conditions]`
        field. If so, the condition expression is evaluated using
        `_evaluate_conditions()`, and any resulting metadata changes are tracked.

        The traversal is depth‑first and returns a boolean indicating whether any
        condition caused a modification anywhere in the subtree.

        Parameters
        ----------
        node : dict
            The current node or container to evaluate. May be a root container,
            a node wrapper, or a nested child.
        track : list[str], optional
            The hierarchical path to the current node, used by the Tracker to
            resolve values and metadata. Automatically extended during recursion.

        Returns
        -------
        bool
            True  if at least one condition modified a node's metadata or value.
            False if no changes occurred.

        Notes
        -----
        - A "real node" is defined as a dict with exactly one top‑level key.
        - Containers (dicts with multiple keys) are traversed but not evaluated.
        - Lists and "children" arrays are traversed element‑wise.
        - This method never raises on condition errors; invalid expressions are
        logged and treated as no‑ops.
        """
        evaluated=False
        
        if not isinstance(node, (dict,list)):
            return evaluated
        # Inside val_dict
            # found: bool
            # track: list
            # node: the actual node (or None)
            # parent_node: the parent container (dict or list)
            # parent_key: the key/index used to reach this node
            # is_node: bool # dict with fields (value/type/etc.)
            # is_branch: bool # dict-with-children OR list
            # is_root: bool # dict-with-keys , no parent, no key
            # has_children: bool
            # children_count: int
            # children_keys: list # list of the key/index used to reach children
            # has_type: bool
            # has_subtype: bool
            # has_meta: bool
        if track is None:
            track = []
        val_dict=self.tracker.validate_node(track)
        if not val_dict or not val_dict["found"]:
            log.warning(f'{track} is not a valid node or branch!')
            return evaluated
        
        current_track=val_dict["track"]
        if (val_dict["is_node"] or val_dict["is_branch"]) and val_dict["has_meta"]:
            cond_track = current_track + ["meta[conditions]"]
            conditions = self.tracker.get_value(cond_track)
            if conditions:
                changed = self._evaluate_conditions(current_track, conditions)
                evaluated = changed or evaluated
        if val_dict["has_children"]:
            for key in val_dict["children_keys"]:
                val=self.tracker.get_value(track + [key])
                evaluated = self.evaluate_conditions_in_a_node(val, track + [key]) or evaluated 

        return evaluated
        
