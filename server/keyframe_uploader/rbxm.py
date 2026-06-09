"""Rebuild a KeyframeSequence as a Roblox XML model (.rbxmx) from plain JSON.

The Studio plugin can't write files or serialize instances, so it sends each selected
KeyframeSequence as JSON (see Serializer.lua). This module reconstructs the equivalent
.rbxmx so it can be uploaded through the Open Cloud Assets API.

Expected animation JSON shape:
{
  "name": "Idle",
  "loop": true,
  "priority": 1,                 # Enum.AnimationPriority .Value
  "authoredHipHeight": 2.0,
  "keyframes": [
    {
      "time": 0.0,
      "name": "Keyframe",
      "poses": [ pose, ... ]      # top-level poses (usually the rig root)
    }
  ]
}
pose = {
  "name": "HumanoidRootPart",
  "weight": 1.0,
  "easingStyle": 0,              # Enum.PoseEasingStyle .Value
  "easingDirection": 0,         # Enum.PoseEasingDirection .Value
  "cframe": [x,y,z, r00,r01,r02, r10,r11,r12, r20,r21,r22],
  "poses": [ child pose, ... ]
}
"""

from xml.sax.saxutils import escape

_HEADER = (
    '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">'
)
_FOOTER = "</roblox>"


class _RefCounter:
    def __init__(self):
        self.n = 0

    def next(self):
        ref = "RBX%X" % self.n
        self.n += 1
        return ref


def _num(v) -> str:
    # Roblox XML writes plain decimals; keep it compact but unambiguous.
    f = float(v)
    if f == int(f):
        return "%d" % int(f)
    return repr(f)


def _cframe_xml(cf) -> str:
    if not cf or len(cf) < 12:
        cf = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
    keys = ["X", "Y", "Z", "R00", "R01", "R02", "R10", "R11", "R12", "R20", "R21", "R22"]
    inner = "".join("<%s>%s</%s>" % (k, _num(cf[i]), k) for i, k in enumerate(keys))
    return '<CoordinateFrame name="CFrame">%s</CoordinateFrame>' % inner


def _pose_xml(pose, refs) -> str:
    ref = refs.next()
    props = (
        '<string name="Name">%s</string>' % escape(str(pose.get("name", "")))
        + '<float name="Weight">%s</float>' % _num(pose.get("weight", 1))
        + '<token name="EasingDirection">%d</token>' % int(pose.get("easingDirection", 0))
        + '<token name="EasingStyle">%d</token>' % int(pose.get("easingStyle", 0))
        + _cframe_xml(pose.get("cframe"))
    )
    children = "".join(_pose_xml(p, refs) for p in pose.get("poses", []) or [])
    return '<Item class="Pose" referent="%s"><Properties>%s</Properties>%s</Item>' % (
        ref, props, children
    )


def _keyframe_xml(kf, refs) -> str:
    ref = refs.next()
    props = (
        '<string name="Name">%s</string>' % escape(str(kf.get("name", "Keyframe")))
        + '<float name="Time">%s</float>' % _num(kf.get("time", 0))
    )
    poses = "".join(_pose_xml(p, refs) for p in kf.get("poses", []) or [])
    return '<Item class="Keyframe" referent="%s"><Properties>%s</Properties>%s</Item>' % (
        ref, props, poses
    )


def build_rbxmx(anim: dict) -> bytes:
    """Return the .rbxmx bytes for one animation JSON object."""
    refs = _RefCounter()
    ks_ref = refs.next()
    ks_props = (
        '<string name="Name">%s</string>' % escape(str(anim.get("name", "Animation")))
        + '<bool name="Loop">%s</bool>' % ("true" if anim.get("loop", True) else "false")
        + '<token name="Priority">%d</token>' % int(anim.get("priority", 0))
        + '<float name="AuthoredHipHeight">%s</float>' % _num(anim.get("authoredHipHeight", 0))
    )
    keyframes = "".join(_keyframe_xml(kf, refs) for kf in anim.get("keyframes", []) or [])
    body = (
        '<Item class="KeyframeSequence" referent="%s"><Properties>%s</Properties>%s</Item>'
        % (ks_ref, ks_props, keyframes)
    )
    doc = _HEADER + body + _FOOTER
    return doc.encode("utf-8")
