import json
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from class_hikmicro_native import HIKMICRO_NATIVE
from class_hikmodels import *
    
class HIKConfigurationManager:
    VERSION = 1
    def __init__(self):
        self.data = {}
    
    def export_camera(self, cam):
        # if not isinstance(cam,HIKMICRO_NATIVE):
        #     return
        self.data = {
            "version": self.VERSION,
            "dt_when": datetime.now().isoformat(),

            "application": {
                "name": "HIKMICRO Native",
                "version": str(cam.VERSION)
            },
            "view": cam.view_settings.to_config_dict(),
            "logging": cam.logging_settings.to_config_dict(),
            "video": cam.video_settings.to_config_dict(),
            "viewport": cam.viewport.to_config_dict(),
            "calibration": cam.calibration.to_config_dict(),
            "cursor": cam.txt_sett_cursor.to_config_dict(),
            "hotspot": cam.txt_sett_hot.to_config_dict(),
            "coldspot": cam.txt_sett_cold.to_config_dict(),
            "probes": [
                p.to_config_dict()
                for p in cam.probes.values()
                if isinstance(p, ProbeArea)],
            "masks": [
                m.to_config_dict()
                for m in cam.masks.values()
                if isinstance(m, MaskArea)],
        }
        return self.data
    
    def save(self, filename):
        with open(filename, "w", encoding="utf8") as f:
            json.dump(self.data, f, indent=4)
    
    def load(self, filename):
        with open(filename, "r", encoding="utf8") as f:
            self.data = json.load(f)
        return self.data
    
    def apply(self, cam):
        # if not isinstance(cam,HIKMICRO_NATIVE):
        #     return
        view_changed = False
        settings_changed = False
        if "view" in self.data:
            cam.view_settings.update_from_dict(self.data["view"])
            cam.apply_view_settings()
            view_changed = True
            settings_changed = True

        if "logging" in self.data:
            cam.logging_settings.update_from_dict(self.data["logging"])
            settings_changed=True
        
        if "video" in self.data:
            cam.video_settings.update_from_dict(self.data["video"])
            settings_changed=True

        if "viewport" in self.data:
            cam.viewport.update_from_dict(self.data["viewport"])
            view_changed = True
            settings_changed = True
        
        calibration_changed=False
        if "calibration" in self.data:
            cam.calibration.update_from_dict(self.data["calibration"])
            calibration_changed=True
            settings_changed = True
            cam.emit_event(CameraEvent.CALIBRATION_CHANGED, cam.calibration)
        
        if "cursor" in self.data:
            cam.txt_sett_cursor.update_from_dict(self.data["cursor"])
        
        if "hotspot" in self.data:
            cam.txt_sett_hot.update_from_dict(self.data["hotspot"])
        
        if "coldspot" in self.data:
            cam.txt_sett_cold.update_from_dict(self.data["coldspot"])          
            
        # Probes    
        # removed_probes=list(cam.probes.keys())
        for name in list(cam.probes.keys()):
            cam.state.probes_changed = True
            cam.emit_event(CameraEvent.PROBE_REMOVED,name)

        cam.probes.clear()
        for cfg in self.data.get("probes",[]):
            if not isinstance(cfg,dict) or not cfg.get("name"):
                continue
            probe = ProbeArea(
                name=cfg["name"],
                x1=cfg["x1"],
                y1=cfg["y1"],
                x2=cfg["x2"],
                y2=cfg["y2"]
            )            
            probe.update_from_dict(cfg)
            cam.probes[probe.name] = probe
            cam.state.probes_changed = True
            cam.emit_event(CameraEvent.PROBE_ADDED, cam.probes[probe.name])
            
        
        # Masks
        # removed_masks=list(cam.masks.keys())
        for name in list(cam.masks.keys()):
            cam.state.masks_changed = True
            cam.emit_event(CameraEvent.MASK_REMOVED,name)
        
        cam.masks.clear()
        for cfg in self.data.get("masks", []):
            if not isinstance(cfg,dict) or not cfg.get("name"):
                continue
            mask = MaskArea(
                name=cfg["name"],
                x1=cfg["x1"],
                y1=cfg["y1"],
                x2=cfg["x2"],
                y2=cfg["y2"]
            )
            mask.update_from_dict(cfg)
            cam.masks[mask.name] = mask
            cam.state.masks_changed = True
            cam.emit_event(CameraEvent.MASK_ADDED, cam.masks[mask.name])
        
        cam.state.settings_changed = settings_changed
        cam.state.view_changed = view_changed
        cam.state.calibration_changed = calibration_changed

        if view_changed:
            cam.emit_event(CameraEvent.VIEW_CHANGED, cam.view_settings)
        
        if settings_changed:
            cam.emit_event(CameraEvent.SETTINGS_CHANGED, cam.get_settings_model())
        info={"config_version":self.data.get("version"),
        "application":self.data.get("application")}
        cam.emit_event(CameraEvent.CONFIGURATION_LOADED, info)

            

