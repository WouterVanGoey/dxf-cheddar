from __future__ import annotations
from pathlib import Path
import ezdxf
from ezdxf.render.forms import box, translate
from ezdxf import disassemble
from ezdxf.render import path
from typing import NamedTuple, Optional, List

import math


DIR = Path(".")


class L_frame:
    def __init__(
        self,
        width: int,
        horizontal_length: int,
        vertical_length: int,
        angle: int,
        thickness: int = 1,
    ) -> None:
        self.width = width
        self.horizontal_length = horizontal_length
        self.vertical_length = vertical_length
        self.angle = angle
        self.thickness = thickness


class Hole:
    def __init__(self) -> None:
        self.width: float = 0.0
        self.height: float = 0.0


class Circle(Hole):
    def __init__(self, radius: int) -> None:
        self.radius = radius
        self.height = self.radius * 2
        self.width = self.radius * 2


class Slot(Hole):
    def __init__(self, radius: int, length: int, angle: int) -> None:
        self.radius = radius
        self.length = length  # distance beteen end radii
        self.angle = angle
        # TODO not completely correct
        self.height = (self.length + (2 * self.radius)) * math.sin(self.angle)
        self.width = (self.length + (2 * self.radius)) * math.cos(self.angle)


class Rectangle:
    def __init__(
        self,
        width: int,
        height: int,
        offset_from_side: int = 0,
        offset_from_bottom: int = 0,
        thickness: int = 1,
    ) -> None:
        self.width = width
        self.height = height
        self.thickness = thickness
        self.offset_from_side = offset_from_side
        self.offset_from_bottom = offset_from_bottom

        self.holes: List[Hole] = []
        self.holes_total_width: float = 0.0

    @staticmethod
    def from_L_frame(l_frame) -> Rectangle:
        # replace with formula used in Excel
        height = (
            l_frame.horizontal_length
            + l_frame.vertical_length
            - (1 if l_frame == 90 else 0.5)
        )
        return Rectangle(l_frame.width, height, l_frame.thickness)

    def add_holes(self, holes: List[Hole]) -> None:
        for hole in holes:
            self.holes.append(hole)
            self.holes_total_width += hole.width

            assert (
                self.width > (2 * self.offset_from_side) + self.holes_total_width
            ), "holes don't fit into the rectangle"
            assert (
                self.height >= self.offset_from_bottom + hole.height
            ), "hole too large"


class DXF:
    def __init__(self) -> None:
        self.doc = ezdxf.new()
        self.doc.layers.new("FORMS", dxfattribs={"color": 1})
        self.doc.layers.new("HATCHES")
        self.msp = self.doc.modelspace()
        self.attribs = {"layer": "FORMS"}

    def add_rectangle(
        self, rectangle: Rectangle, start_from_x: int = 0, start_from_y: int = 0
    ) -> None:
        # Rectangle with evenly spaced holes
        rect_coordinates = translate(
            box(rectangle.width, rectangle.height), (start_from_x, start_from_y)
        )
        self.msp.add_lwpolyline(rect_coordinates, close=True, dxfattribs=self.attribs)

        space_minus_offsets_from_side = rectangle.width - (
            2 * rectangle.offset_from_side
        )
        space_remaining = space_minus_offsets_from_side - rectangle.holes_total_width
        if len(rectangle.holes) <= 1:
            raise ValueError("Need to have at least two holes")
        space_between_holes = space_remaining / (len(rectangle.holes) - 1)

        for i, hole in enumerate(rectangle.holes):
            hole_center_x = (
                start_from_x
                + rectangle.offset_from_side
                + (i * hole.width + (hole.width / 2))
                + (i * space_between_holes)
            )
            hole_center_y = (
                start_from_y + rectangle.offset_from_bottom + (hole.height / 2)
            )
            if isinstance(hole, Circle):
                self.msp.add_circle(
                    (hole_center_x, hole_center_y),
                    radius=hole.radius,
                    dxfattribs=self.attribs,
                )
            elif isinstance(hole, Slot):
                # TODO doesn't work correctly yet
                # TODO add lines connecting circles
                left_x = hole_center_x - ((hole.length / 2) * math.cos(hole.angle))
                left_y = hole_center_y + ((hole.length / 2) * math.sin(hole.angle))
                self.msp.add_circle(
                    (left_x, left_y),
                    radius=hole.radius,
                    dxfattribs=self.attribs,
                )
                right_x = hole_center_x + ((hole.length / 2) * math.cos(hole.angle))
                right_y = hole_center_y - ((hole.length / 2) * math.sin(hole.angle))
                self.msp.add_circle(
                    (right_x, right_y),
                    radius=hole.radius,
                    dxfattribs=self.attribs,
                )

    def save(self, filename: str) -> None:
        # Convert entities to primitives
        primitives = disassemble.to_primitives(self.msp)

        # Collect paths from primitives:
        paths = [p.path for p in primitives if p.path]

        # Render this paths as HATCH entities
        path.render_hatches(
            self.msp, paths, dxfattribs={"layer": "HATCHES", "color": 2}
        )

        self.doc.set_modelspace_vport(15, (4, 4))
        self.doc.saveas(DIR / f"{filename}.dxf")


if __name__ == "__main__":
    dxf = DXF()

    l_frame = L_frame(width=200, horizontal_length=50, vertical_length=10, angle=90)
    rectangle_1 = Rectangle.from_L_frame(l_frame)
    rectangle_1.offset_from_side = 6
    rectangle_1.offset_from_bottom = 10
    rectangle_1.add_holes([Circle(radius=5) for _ in range(7)])
    dxf.add_rectangle(rectangle_1)

    rectangle_2 = Rectangle(
        width=150, height=50, offset_from_side=40, offset_from_bottom=5
    )
    rectangle_2.add_holes(
        [
            Slot(radius=5, length=10, angle=45),
            Slot(radius=5, length=10, angle=45),
            Slot(radius=5, length=10, angle=45),
        ]
    )
    dxf.add_rectangle(rectangle_2, start_from_x=0, start_from_y=rectangle_2.height + 20)

    dxf.save("demo")
