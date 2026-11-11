from enum import Enum
from PyQt6.QtGui import *
from functional.class_struct_tracker import TreeStructTracker
from class_hikmodels import *
from functional.class_icons import Icons

icons=Icons()

class HIKStructBuilder:

    FIELDS=[
        {"name": "ITEM",  "editable": False, "selectable": True,  "hidden": False},
        {"name": "VALUE", "editable": True,  "selectable": True,  "hidden": False},
        {"name": "TYPE",  "editable": False, "selectable": False, "hidden": True},
        {"name": "UNIT",  "editable": False, "selectable": True, "hidden": False},
        {"name": "INFO",  "editable": True, "selectable": True, "hidden": False},
        ]


    style_dict = {#}
    #style_dict_other = {
    "Configuration":
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#27ae60"),
            "DecorationRole": icons.icon("cog 8 tooth")
        },

    "View": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#8ec6ff"),
            "DecorationRole": icons.icon("eye")
        },

    "Logging": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#ffe08a"),
            "DecorationRole": icons.icon("list bullet")
        },

    "Video": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#cce08a"),
            "DecorationRole": icons.icon("video camera solid")
        },

    "Viewport": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#bde0fe"),
            "DecorationRole": icons.icon("window")
        },
    
    "Cursor": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#bde00e"),
            "DecorationRole": icons.icon("cursor arrow ripple")
        },

    "Hotspot": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#ff3331"),
            "DecorationRole": icons.icon("chevron up")
        },
    
    "Coldspot": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#7ec3ff"),
            "DecorationRole": icons.icon("chevron down")
        },

    "Calibration": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#ffadad"),
            "DecorationRole": icons.icon("chart bar square")
        },

    "Probes": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#a8e6a3"),
            "DecorationRole": icons.icon("eye dropper solid")
        },

    "Masks": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#f2b5d4"),
            "DecorationRole": icons.icon("face smile solid")
        },

    "Tracker": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#d8b4fe"),
            # "DecorationRole": icons.icon("tracker")
        },

    "text_settings": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#e9ecef"),
            # "DecorationRole": icons.icon("text_settings")
        },


    "alarm_not_active": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#000000"),
            "BackgroundRole": QColor("#74c0fc"),
            "DecorationRole": icons.icon("bell")
        },

    "alarm_active": 
        {
            "field": "ITEM",
            "ForegroundRole": QColor("#ffffff"),
            "BackgroundRole": QColor("#ff3333"),
            "DecorationRole": icons.icon("bell alert solid")
        },
}

    
    def __init__(self, struct, parent=None):
        self.struct = struct
        self.widget_parent=parent

    def _clean_struct(self):
        return  {'Configuration': {'value': "", 'type': 'str', 'subtype': '', 
                                         "style_key":"Configuration",
                                          'meta': {'editable': False}}
                        }
    
    def clear(self):
        if self.struct:
            struct = self.struct
        else:
            struct = self._clean_struct()
        st = TreeStructTracker(struct)
        val=st.get_validate_node_as_obj(["Configuration"])
        for child in val.children_keys:
            was_del=st.delete_node(["Configuration", child])
            if not was_del:
                print(f"DEbug -> Could not delete {child}")
        
        self.struct = st.get_root()
        return self.struct
    
    def build(self, cam):
        cfg = cam.configuration_manager.export_camera(cam)
        # st=self.widget_parent.tracker
        # if not isinstance(st, TreeStructTracker):
        #     return
        struct = self._clean_struct()
        st = TreeStructTracker(struct)
        #st.struct= self.struct
        st.add_child(["Configuration"],"View", self._view_to_node(cfg))
        st.add_child(["Configuration"],"Viewport", self._viewport_to_node(cfg))
        st.add_child(["Configuration"],"Logging",self._logging_to_node(cfg))
        st.add_child(["Configuration"],"Video",self._video_to_node(cfg))
        st.add_child(["Configuration"],"Calibration",self._calibration_to_node(cfg))
        st.add_child(["Configuration"],"Cursor",self._cursor_to_node(cfg))
        st.add_child(["Configuration"],"Hotspot",self._hotspot_to_node(cfg))
        st.add_child(["Configuration"],"Coldspot",self._coldspot_to_node(cfg))
        # Make Probes
        probes=cfg.get("probes", [])
        ppp = {'value': "", 'type': 'str', 'subtype': '', 
                "style_key":"Probes",
                'meta': {'editable': False}}
        
        st.add_child(["Configuration"],"Probes",ppp)
        for p in probes:
            name = p.get("name")
            if name:
                p_node = self._probe_to_node(p)[name]
                st.add_child(["Configuration","Probes"],name,p_node)
        # Make Masks
        mmm = {'value': "", 'type': 'str', 'subtype': '', 
                "style_key":"Masks",
                'meta': {'editable': False}}
        
        st.add_child(["Configuration"],"Masks",mmm)
        masks=cfg.get("masks", [])
        for m in masks:
            name = m.get("name")
            if name:
                m_node = self._mask_to_node(m)[name]
                st.add_child(["Configuration","Masks"],name,m_node)
        self.struct = st.get_root()
        return self.struct
        
    def _type_of(self, value):
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, (tuple,list)):
            if (len(value)==3 
                and isinstance(value[0],int) 
                and value[0]<=255 
                and value[0]>=0):
                return "color"
            return "list"
        return "str"
    
    def _dict_to_branch(self, d):
        children = []
        for key, value in d.items():
            if isinstance(value, dict):
                children.append({
                    key: self._dict_to_branch(
                        value
                    )
                })
            else:
                children.append({key: self._make_property(key,value)})
        return {"children": children, 'value': "", 
                'type': 'str', 'subtype': '', 
                'meta': {'editable': False}}
    
    def _tracker_to_node(self, probe):
        name = probe.get("name", "Probe")
        children = []
        for k, v in probe.items():
            if k == "name":
                continue
            if isinstance(v, dict):
                children.append({k:self._dict_to_branch(v)})
            else:
                children.append({k:self._property(v)})
        # Runtime branch
        children.append({
            "Tracker": {
                "children": [
                    {
                        "Current": {
                            "value": 0.0,
                            "type": "float",
                            "unit": "°C",
                            "meta": {
                                "editable": False
                            }
                        }
                    },
                    {
                        "Average": {
                            "value": 0.0,
                            "type": "float",
                            "unit": "°C",
                            "meta": {
                                "editable": False
                            }
                        }
                    },
                    {
                        "Plot": {
                            "value": name,
                            "type": "plot",
                            "meta": {
                                "editable": False
                            }
                        }
                    }
                ]
            }
        })
        return {name: {"children": children, 'value': "", 
                       'type': 'str', 'subtype': '', 
                       'meta': {'editable': False}}}
    
    def rgb_to_treecolor(self, value):
        """
        Convert internal BGR tuple/list to Qt RGB color string.
        Internal format: (B, G, R)
        Tree format:     #AARRGGBB
        """
        if (
            isinstance(value, (tuple, list))
            and len(value) == 3
        ):
            b, g, r = [int(v) for v in value]

            return f"#ff{r & 0xFF:02X}{g & 0xFF:02X}{b & 0xFF:02X}"

        return value


    def treecolor_to_rgb(self, value):
        """
        Convert Qt RGB color string to internal BGR tuple.
        Tree format:     #AARRGGBB
        Internal format: (B, G, R)
        """
        if isinstance(value, str) and value.startswith("#"):
            value = value.lstrip("#")
            # Qt ARGB
            if len(value) == 8:
                value = value[2:]  # discard alpha

            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)

            # internal BGR
            return (b, g, r)

        return value
    def treemode_to_maskmode(self, value):
        if isinstance(value, str):
            for item in iter(MaskMode):
                if item.value == value.lower():
                    return item
        return value
    
    def maskmode_to_treemode(self, mode:MaskMode):
        if isinstance(mode, MaskMode):
            return mode.value.upper()
        return mode 
    
    def maskmode_options(self):
        return [item.value.upper() for item in iter(MaskMode)]
    
    def treemode_to_tempmode(self, value):
        if isinstance(value, str):
            for item in iter(TempMode):
                if item.value == value.lower():
                    return item
        return value
    
    def tempmode_to_treemode(self, mode:TempMode):
        if isinstance(mode, TempMode):
            return mode.value.upper()
        return mode 

    def tempmode_options(self):
        return [item.value.upper() for item in iter(TempMode)]
    
    def colormap_to_tree(self,colormap):
        for item in ColorMap:
            if item.value == colormap:
                return item.name
        return str(colormap)

    def tree_to_colormap(self,value:str):
        if isinstance(value, str):
            try:
                return ColorMap[value.upper()].value
            except KeyError:
                pass
        return value

    def colormap_options(self):
        return [item.name for item in ColorMap]
    
    def line_style_options(self):
        return ["solid","dash","dot","dashdot","dashdotdot"]
    
    def _calibration_options(self):
        return ["RAW", "POLYNOMIAL", "TABLE"]

    def _named_node(self, cfg, default_name):
        name = cfg.get("name", default_name)
        children = []
        for key, value in cfg.items():
            if key == "name":
                continue
            if isinstance(value, dict):
                children.append({key: self._dict_to_branch(value)})
            else:
                children.append({key: self._make_property(key,value)})
        return {name: {"children": children, 'value': "", 
                       'type': 'str', 'subtype': '', 
                       'meta': {'editable': False}}}
    
    def _alarm_props(self,st:TreeStructTracker,cfg, alarm="high_alarm"):
        base=[f"{cfg['name']}", alarm]
        st.set_or_create_property(
            base+ ["active", "meta[editable]"], False)
        
        cond={"active": f"me_set('style_key','alarm_active') if node_get('Configuration[Probes[{base[0]}[{base[1]}[active[value]]]]]') else me_set('style_key','alarm_not_active')"}
        st.set_or_create_property(
            base+ ["active", "meta[conditions]"], cond["active"])
        
        st.set_or_create_property(
            base+ ["threshold", "meta[constraints]"],
                            {'min':0,'max':255 })
        st.set_or_create_property(base+ ["threshold", "unit"],"0-255")

        return st
        
    def _text_props(self,st:TreeStructTracker,cfg):
        st = self._text_settings_base([f"{cfg['name']}","text_settings"],st)
        
        # Probe/Mask line thickness
        st.set_or_create_property([f"{cfg['name']}",
                                          "line_thickness",
                                          "meta[constraints]"],
                                          {'min':1,'max':7 })
        return st
    
    def _tracker_props(self,st:TreeStructTracker,cfg):

        st = self._tracker_settings_base([f"{cfg['name']}","tracker_settings"],st)
        
        return st
    
    def _tracker_settings_base(self,base_track:list[str],st:TreeStructTracker):

        # Text thickness
        st.set_or_create_property(base_track + ["line_width", "meta[constraints]"],
                                          {'min':1,'max':7 })
        # line style
        st.set_or_create_property(base_track + ["line_style", "meta[options]"],
                                          self.line_style_options())
        return st
    
    def _view_to_node(self, cfg):
        view_node = self._dict_to_branch(cfg.get("view", {}))

        vnt=TreeStructTracker({"view":view_node})
        vnt.set_or_create_property(["view", "style_key"], "View")
        # zoom
        vnt.set_or_create_property(
            ["view", "zoom", "meta[constraints]"],
                                          {'min':1.0,'max':16.0 })
        # grid spacing
        vnt.set_or_create_property(
            ["view", "grid_spacing", "meta[constraints]"],
                                          {'min':5,'max':150 })
        # centers
        vnt.set_or_create_property(
            ["view", "center_x", "meta[editable]"],
                                          False)
        vnt.set_or_create_property(
            ["view", "center_y", "meta[editable]"],
                                          False)
        
        vnt.set_or_create_property(
            ["view", "colormap", "meta[options]"],
                                self.colormap_options())

        return vnt.get_root()["view"]
    
    def _video_to_node(self, cfg):
        video_node =self._dict_to_branch(cfg.get("video", {}))

        vnt=TreeStructTracker({"video":video_node})
        vnt.set_or_create_property(["video", "style_key"], "Video")

        vnt.set_or_create_property(
            ["video", "raw_format", "meta[options]"],["npz"])
        vnt.set_or_create_property(
            ["video", "video_export", "vid_format", "meta[options]"],["mp4"])
        vnt.set_or_create_property(
            ["video", "video_export", "fps", "meta[constraints]"],
                {'min':0.0,'max':120.0})
        
        # Allows correct file formats
        mask= {
            "__m__1":"is_format",
            "__mv__1": "^[A-Za-z0-9_-]{1,64}$"
            }

        vnt.set_or_create_property(
            ["video", "filename_prefix", "meta[mask]"],mask)
        
        vnt.set_or_create_property(
            ["video", "enabled", "meta[editable]"],False)
        
        return vnt.get_root()["video"]

    def _logging_to_node(self, cfg):
        logging_node =self._dict_to_branch(cfg.get("logging", {}))

        vnt=TreeStructTracker({"logging":logging_node})
        vnt.set_or_create_property(["logging", "style_key"], "Logging")
        # interval
        vnt.set_or_create_property(
            ["logging", "interval_s", "meta[constraints]"],
                {'min':0.2,'max':60.0 * 60 * 24})
        vnt.set_or_create_property(
            ["logging", "interval_s", "unit"], "s")
        
        # duration
        vnt.set_or_create_property(
            ["logging", "duration_s", "meta[constraints]"],
                {'min':0,'max':60.0 * 60 * 24 * 30 * 365})
        vnt.set_or_create_property(
            ["logging", "duration_s", "unit"], "s")
        
        # file size
        vnt.set_or_create_property(
            ["logging", "max_file_size_mb", "meta[constraints]"],
                {'min':1,'max':1000.0})
        vnt.set_or_create_property(
            ["logging", "max_file_size_mb", "unit"], "MB")

        vnt.set_or_create_property(
            ["logging", "format", "meta[options]"],["csv"])
        
        # Allows to copy the path
        mask= {
            "__m__1":"is_not_change",
            "__mv__1": ""
            }
        vnt.set_or_create_property(
            ["logging", "output_path", "meta[mask]"],mask)
        
        vnt.set_or_create_property(
            ["logging", "enabled", "meta[editable]"],False)
        

        return vnt.get_root()["logging"]

    def _viewport_to_node(self, cfg):

        viewport_node = self._dict_to_branch(
                            cfg.get("viewport", {})
                        )

        vnt=TreeStructTracker({"viewport":viewport_node})
        vnt.set_or_create_property(["viewport", "style_key"], "Viewport")
         # all not editable
        val_dict=vnt.get_validate_node_as_obj(vnt.get_root())
        for child in val_dict.children_keys:
            vnt.set_or_create_property(
                ["viewport", child , "meta[editable]"], False)
        # zoom
        vnt.set_or_create_property(
            ["viewport", "zoom", "meta[constraints]"],
                                          {'min':1.0,'max':16.0 })
        # add px units
        vnt=self._unit_px("viewport",vnt)

        return vnt.get_root()["viewport"]
    
    def _cursor_to_node(self,cfg):
        cursor_node = self._dict_to_branch(cfg.get("cursor", {}))
        vnt=TreeStructTracker({"cursor":cursor_node})
        vnt.set_or_create_property(["cursor", "style_key"], "Cursor")
        vnt=self._text_settings_base(["cursor"],vnt)
        return vnt.get_root()["cursor"]
    
    def _hotspot_to_node(self,cfg):
        hotspot_node = self._dict_to_branch(cfg.get("hotspot", {}))
        vnt=TreeStructTracker({"hotspot":hotspot_node})
        vnt.set_or_create_property(["hotspot", "style_key"], "Hotspot")
        vnt=self._text_settings_base(["hotspot"],vnt)
        # hide Temperature mode
        vnt.set_or_create_property(["hotspot", "mode", "meta[hidden]"], True)
        return vnt.get_root()["hotspot"]
    
    def _coldspot_to_node(self,cfg):
        coldspot_node = self._dict_to_branch(cfg.get("coldspot", {}))
        vnt=TreeStructTracker({"coldspot":coldspot_node})
        vnt.set_or_create_property(["coldspot", "style_key"], "Coldspot")
        vnt=self._text_settings_base(["coldspot"],vnt)
        # hide Temperature mode
        vnt.set_or_create_property(["coldspot", "mode", "meta[hidden]"], True)
        return vnt.get_root()["coldspot"]
    
    def _text_settings_base(self,base_track:list[str],st:TreeStructTracker):
        # Probe/Mask unit
        st.set_or_create_property(base_track+["unit","meta[options]"],
                ['°C','Raw','°F','K'])
        # Probe/Mask decimals
        st.set_or_create_property(base_track + ["decimals", "meta[constraints]"],
                                          {'min':0,'max':6 })
        # Text thickness
        st.set_or_create_property(base_track + ["thickness", "meta[constraints]"],
                                          {'min':1,'max':5 })
        # Text scale
        st.set_or_create_property(base_track + ["font_scale", "meta[constraints]"],
                                          {'min':0.1,'max':3.0 })
        # Temperature mode
        st.set_or_create_property(base_track + ["mode", "meta[options]"],
                                          self.tempmode_options())
        return st
    
    def _calibration_to_node(self,cfg):
        calib_node = self._dict_to_branch(cfg.get("calibration", {}))
        vnt=TreeStructTracker({"calibration":calib_node})
        vnt.set_or_create_property(["calibration", "style_key"], "Calibration")
        # type
        vnt.set_or_create_property(
            ["calibration", "calibration_type", "meta[options]"],
                self._calibration_options())
        mask= {
            "__m__1":"is_not_change",
            "__mv__1": ""
            }
        vnt.set_or_create_property(
            ["calibration", "file_name", "mask"], mask)
        
        vnt.set_or_create_property(
            ["calibration", "coeff", "type"],"list")
        vnt.set_or_create_property(
            ["calibration", "coeff", "subtype"],"float")
        vnt.set_or_create_property(
            ["calibration", "raw_values", "type"],"list")
        vnt.set_or_create_property(
            ["calibration", "raw_values", "subtype"],"int")
        vnt.set_or_create_property(
            ["calibration", "raw_values", "unit"],"0-255")
        vnt.set_or_create_property(
            ["calibration", "temperature_values", "type"],"list")
        vnt.set_or_create_property(
            ["calibration", "temperature_values", "subtype"],"float")
        
        vnt.set_or_create_property(
            ["calibration", "display_unit", "meta[hidden]"], True)
        
        cond={"disp_unit":"me_set('unit',node_get('Configuration[Calibration[display_unit[value]]]'))"}
        vnt.set_or_create_property(
            ["calibration", "temperature_values", "meta[conditions]"], cond["disp_unit"])

        return vnt.get_root()["calibration"]
    
    def _unit_px(self,config,st:TreeStructTracker):
        for xy in ("x1","x2","y1","y2"):
            st.set_or_create_property([config, xy, "unit"],"px")
        return st
        
    def _probe_to_node(self, cfg):
        # this is {name:{children:[...]}}
        probe_node=self._named_node(cfg, "Probe")
        probe_node[cfg['name']].update({'value': "", 'type': 'str', 'subtype': '', 
                "style_key":"Probes",
                'meta': {'editable': False}})
        pnt=TreeStructTracker(probe_node)
        # add px units
        pnt=self._unit_px(cfg['name'],pnt)
        pnt=self._text_props(pnt,cfg)
        pnt=self._tracker_props(pnt,cfg)
        pnt=self._alarm_props(pnt,cfg,"high_alarm")
        pnt=self._alarm_props(pnt,cfg,"low_alarm")
        
        return pnt.get_root() 

    def _mask_to_node(self, cfg):
        mask_node = self._named_node(cfg, "Mask")
        mask_node[cfg['name']].update({'value': "", 'type': 'str', 'subtype': '', 
                "style_key":"Masks",
                'meta': {'editable': False}})
              
        mnt=TreeStructTracker(mask_node)
        # add px units
        mnt=self._unit_px(cfg['name'],mnt)
        mnt.set_or_create_property([f"{cfg['name']}","mode","meta[options]"],
                                          self.maskmode_options())
        
        mnt=self._text_props(mnt,cfg)
        return mnt.get_root()
    
    def _make_property(self, key:str, value):
        val_type = self._type_of(value)
        if "color" in key.lower(): 
            value = self.rgb_to_treecolor(value)
            if isinstance(value,str):
                val_type = "color"
        if "colormap" in key.lower(): 
            value = self.colormap_to_tree(value)
            if isinstance(value,str):
                val_type = "str"

        val_subtype = ""
        if val_type == "list" and len(value):
            val_subtype = self._type_of(value[0])            
        return {
            "value": value,
            "type": val_type,
            "subtype": val_subtype,
            "meta": {
                "editable": True
            }
        }
    
    def track_to_config_path(self,track):
        path=[]
        if isinstance(track,list) and len(track)>2:
            map_d={
                "View":"view",
                "Logging":"logging",
                "Video":"video",
                "Viewport":"viewport",
                "Calibration":"calibration",
                "Cursor":"cursor",
                "Coldspot":"coldspot",
                "Hotspot":"hotspot",
                "Probes": "probes",
                "Masks": "masks",
                }
            if track[0]=="Configuration":
                for tvval,camval in map_d.items(): 
                    if track[1]==tvval:
                        path=[camval]+track[2:]
                        return path[:-1] # remove 'value'
            
        return path        
    
    def apply_dict_path(self, conf, path, value):
        if (isinstance(path,list) and len(path)>2):
            if path[0] == "probes":
                probe_name = path[1]
                for probe in conf["probes"]:
                    if probe["name"] == probe_name:
                        current = probe
                        for part in path[2:-1]:
                            current = current[part]
                        current[path[-1]] = value
                        return

            elif path[0] == "masks":
                mask_name = path[1]
                for mask in conf["masks"]:
                    if mask["name"] == mask_name:
                        current = mask
                        for part in path[2:-1]:
                            current = current[part]
                        if path[-1] == "mode":
                            value=self.treemode_to_maskmode(value)
                        current[path[-1]] = value
                        return
        if isinstance(path,list):
            current = conf
            for part in path[:-1]:
                current = current[part]
            if path:
                if path[-1] == "colormap":
                    value=self.tree_to_colormap(value)
                if isinstance(current,dict):
                    current[path[-1]] = value
    
    def apply_object_path(self, obj, path, value):
        current = obj
        for part in path[:-1]:
            current = getattr(current, part)
        setattr(current, path[-1], value)

    def set_camera_output_file(self, cam, output_path, st:TreeStructTracker):
        cam.logging_settings.output_path = str(output_path)
        return self.get_camera_output_file_track()
    
    def get_camera_output_file_track(self):
        return ["Configuration", "Logging","output_path",'value']

    def on_camera_event(self, cam, eho:EventHandler, st:TreeStructTracker, log_callback = None):
        refresh_tree=False
        state=cam.state
        if isinstance(state,EngineState):
            pass
        if log_callback is None:
            log_callback=print

        if eho.event.event_type==CameraEvent.ACQUIRE_ERROR:
            state.error_changed = False
            log_callback(f"CAM Error: {eho.event.data}")
        
        if eho.event.event_type==CameraEvent.ALARM_CLEARED_H:
            probe=eho.event.data
            if isinstance(probe,ProbeArea):
                base=["Configuration", "Probes", probe.name, "high_alarm"]
                log_callback(f"Alarm High Cleared: {probe.name}")
                st.set_value(base+["active","value"], False)
                
            refresh_tree=True
        if eho.event.event_type==CameraEvent.ALARM_TRIGGERED_H:
            probe=eho.event.data
            if isinstance(probe,ProbeArea):
                base=["Configuration", "Probes", probe.name, "high_alarm"]
                log_callback(f"Alarm High Triggered: {probe.name}")
                st.set_value(base+["active","value"], True)
                
            refresh_tree=True
        
        if eho.event.event_type==CameraEvent.ALARM_CLEARED_L:
            probe=eho.event.data
            if isinstance(probe,ProbeArea):
                base=["Configuration", "Probes", probe.name, "low_alarm"]
                log_callback(f"Alarm High Cleared: {probe.name}")
                st.set_value(base+["active","value"], False)
                
            refresh_tree=True
        if eho.event.event_type==CameraEvent.ALARM_TRIGGERED_L:
            probe=eho.event.data
            if isinstance(probe,ProbeArea):
                base=["Configuration", "Probes", probe.name, "low_alarm"]
                log_callback(f"Alarm High Triggered: {probe.name}")
                st.set_value(base+["active","value"], True)

            refresh_tree=True
        if eho.event.event_type in (CameraEvent.LOGGING_STARTED,
                                    CameraEvent.LOGGING_STOPPED):
            log_sett=eho.event.data
            if isinstance(log_sett,LoggingSettings):
                base=["Configuration", "Logging"]
                st.set_value(base+["enabled","value"], log_sett.enabled)
                if log_sett.enabled:
                    log_callback("Logging activated")
                else:
                    log_callback("Logging deactivated")
            refresh_tree=True
        
        if eho.event.event_type in (CameraEvent.VIDEO_REC_STARTED,
                                    CameraEvent.VIDEO_REC_STOPPED):
            vid_sett=eho.event.data
            if isinstance(vid_sett,VideoSettings):
                base=["Configuration", "Video"]
                st.set_value(base+["enabled","value"], vid_sett.enabled)
                if vid_sett.enabled:
                    log_callback("Video Recording Activated")
                else:
                    log_callback("Video Recording Stopped")
            refresh_tree=True

        if refresh_tree:
            state.alarm_triggered_l=cam.has_low_alarms()
            state.alarm_triggered_h=cam.has_high_alarms()
        
        if eho.event.event_type == CameraEvent.LOG_MESSAGE:
            log_callback(f"CAM Message: {eho.event.data}")
        
        if eho.event.event_type == CameraEvent.SETTINGS_CHANGED:
            state.settings_changed = False
            log_callback("Settings Chaged")

        if eho.event.event_type == CameraEvent.CALIBRATION_CHANGED:
            state.calibration_changed = False
            log_callback("Calibration Chaged")

        if eho.event.event_type == CameraEvent.VIEW_CHANGED:
            
            #get new data node
            val_nd=st.get_validate_node_as_obj(["Configuration", "View"])
            for nd_key in val_nd.children_keys:
                track=["Configuration", "View", nd_key, "value"]
                if nd_key != "colormap":
                    st.set_value(
                        track, getattr(eho.event.data, nd_key))
                else:
                    st.set_value(
                        track, self.colormap_to_tree(
                            getattr(eho.event.data, nd_key)))
            
        
        # if eho.event.event_type == CameraEvent.VIEW_CHANGED:
        #     st.set_value(
        #         ["Configuration", "View", "zoom", "value"],
        #         eho.event.data.zoom
        #     )
        #     st.set_value(
        #         ["Configuration", "View", "center_x", "value"],
        #         eho.event.data.center_x
        #     )
        #     st.set_value(
        #         ["Configuration", "View", "center_y", "value"],
        #         eho.event.data.center_y
        #     )
            state=cam.state
            if isinstance(state,EngineState):
                state.view_changed = False
            
            refresh_tree = True

        if eho.event.event_type == CameraEvent.CONFIGURATION_LOADED:
            log_callback("Configuration Loaded Successfully")

        return refresh_tree
    
    
