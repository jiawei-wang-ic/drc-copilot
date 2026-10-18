"""Render a PNG of the layout around one DRC marker: SKY130 layer colours, red marker, ruler with the gap.

Uses KLayout's Python package headless (pip install klayout); no GUI needed.
"""
import os
import re
from typing import Dict, Optional

import klayout.db as db
import klayout.lay as lay

NUM = r"-?\d+(?:\.\d+)?"
PAIR = re.compile(rf"\(({NUM}),({NUM});({NUM}),({NUM})\)\s*[|/]\s*\(({NUM}),({NUM});({NUM}),({NUM})\)")
POLY = re.compile(r"polygon:\s*\(([^)]*)\)")
LYP = os.path.expanduser("~/.volare/sky130A/libs.tech/klayout/tech/sky130A.lyp")


class Snapshotter:
    def __init__(self, gds: str, top: str = "TOP", lyp: str = LYP):
        self.view = lay.LayoutView()
        self.view.load_layout(gds, True)
        if os.path.exists(lyp):
            self.view.load_layer_props(lyp)
        self.view.max_hier()
        ly = db.Layout()
        ly.read(gds)
        self.top = top
        self.to_top: Dict[str, db.DCplxTrans] = {top: db.DCplxTrans()}
        for inst in ly.cell(top).each_inst():   # one level is enough for our test chips
            self.to_top.setdefault(ly.cell(inst.cell_index).name, inst.dcplx_trans)

    def render(self, cell: str, value: str, out_png: str, margin: float = 1.2,
               size=(520, 340)) -> Optional[str]:
        t = self.to_top.get(cell, db.DCplxTrans())
        markers, ruler = [], None
        m = PAIR.search(value)
        if m:
            v = [float(x) for x in m.groups()]
            e1 = t * db.DEdge(v[0], v[1], v[2], v[3])
            e2 = t * db.DEdge(v[4], v[5], v[6], v[7])
            markers = [("edge", e1), ("edge", e2)]
            bbox = db.DBox(e1.p1, e1.p2) + db.DBox(e2.p1, e2.p2)
            # ruler between the two edges, drawn just outside the shapes so the label stays readable
            off = 0.15 + 0.08 * max(bbox.width(), bbox.height())
            if abs(e1.dx()) < 1e-9 and abs(e2.dx()) < 1e-9:          # vertical edges -> horizontal ruler below
                y = bbox.bottom - off
                ruler = (db.DPoint(e1.p1.x, y), db.DPoint(e2.p1.x, y))
            elif abs(e1.dy()) < 1e-9 and abs(e2.dy()) < 1e-9:        # horizontal edges -> vertical ruler left
                x = bbox.left - off
                ruler = (db.DPoint(x, e1.p1.y), db.DPoint(x, e2.p1.y))
        else:
            m = POLY.search(value)
            if not m:
                return None
            pts = [db.DPoint(*[float(c) for c in p.split(",")]) for p in m.group(1).split(";") if p]
            poly = t * db.DPolygon(pts)
            markers = [("poly", poly)]
            bbox = poly.bbox()

        self.view.clear_markers() if hasattr(self.view, "clear_markers") else None
        self.view.clear_annotations()
        keep = []
        for kind, g in markers:
            mk = lay.Marker(self.view)
            mk.set_edge(g) if kind == "edge" else mk.set_polygon(g)
            mk.color = 0xFF2D2D
            mk.frame_color = 0xFF2D2D
            mk.line_width = 3
            mk.vertex_size = 0
            keep.append(mk)
        if ruler and ruler[0].distance(ruler[1]) < 1e-6:   # zero-length (e.g. off-grid vertex): no ruler
            ruler = None
        if ruler:
            ann = lay.Annotation()
            ann.p1, ann.p2 = ruler
            ann.style = lay.Annotation.StyleArrowBoth
            ann.fmt = "$D µm"
            ann.main_position = lay.Annotation.PositionCenter
            ann.main_yalign = lay.Annotation.AlignDown
            ann.main_xalign = lay.Annotation.AlignCenter
            self.view.insert_annotation(ann)
        span = max(bbox.width(), bbox.height(), 0.2)
        box = bbox.enlarged(max(margin, 0.6 * span), max(margin, 0.6 * span))
        self.view.zoom_box(box)
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        self.view.save_image(out_png, *size)
        for mk in keep:
            mk._destroy() if hasattr(mk, "_destroy") else None
        return out_png


    def overview(self, out_png: str, size=(1100, 520)) -> str:
        """Whole test chip: standard-cell row plus the injected blocks."""
        self.view.clear_annotations()
        self.view.zoom_fit()
        os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
        self.view.save_image(out_png, *size)
        return out_png
