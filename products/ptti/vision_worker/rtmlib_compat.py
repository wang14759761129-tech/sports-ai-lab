"""Load RTMPose from RTMLib without its optional, absent drawing package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_rtmpose_class():
    """Import only the pose package tree; do not import detector or GUI helpers.

    The pinned RTMLib release's top-level initializer imports
    ``rtmlib.visualization.draw``, which is not included in its built wheel.
    PTTI needs neither those drawing helpers nor RTMLib's detector wrappers;
    keep upstream files untouched and load the documented RTMPose module path.
    """
    if "rtmlib.tools.pose_estimation.rtmpose" in sys.modules:
        return sys.modules["rtmlib.tools.pose_estimation.rtmpose"].RTMPose
    spec = importlib.util.find_spec("rtmlib")
    if spec is None or not spec.origin:
        raise ModuleNotFoundError("RTMLIB_PACKAGE_NOT_FOUND")
    package_path = Path(spec.origin).resolve().parent
    package = ModuleType("rtmlib")
    package.__path__ = [str(package_path)]
    package.__package__ = "rtmlib"
    sys.modules["rtmlib"] = package
    for name, folder in (
        ("rtmlib.tools", package_path / "tools"),
        ("rtmlib.tools.pose_estimation", package_path / "tools" / "pose_estimation"),
    ):
        child = ModuleType(name)
        child.__path__ = [str(folder)]
        child.__package__ = name
        sys.modules[name] = child
    from rtmlib.tools.pose_estimation.rtmpose import RTMPose
    return RTMPose
