import math
from venn7.bezier import MetafontBezier
import shapely.geometry
import shapely.affinity

class VennDiagram:
    """A simple, polar symmetric monotone Venn diagram represented with a
    compact matrix encoding.

    Reference: Cao et al. "Symmetric Monoton Venn Diagrams with Seven Curves."

    Glossary
    --------

    simple: only two curves may intersect at any point (no triple intersections).
    polar symmetric: n-fold rotational symmetry, where n is the order of the diagram.
    monotone: every k-region (region intersecting exactly k curves) is adjacent to a
    k-1-region if possible and a k+1-region if possible.
    matrix encoding: an (n-1) by (2^n - 2)/n matrix of 1's and 0's. There is exactly
    one 1 in every column, the rest are zeros. Each 1 indicates a crossing over of
    two curves.
    compact matrix encoding: a list giving the 1-indexed row position of the 1 in each
    column.
    """

    def __init__(self, n, weave_code):
        self.n = n

        self.condensed_code = self.parse_weave_code(weave_code)
        self.code = [y for x in self.condensed_code for y in x]

        self.validate_basic()
        self.validate_venn()

    def parse_weave_code(self, weave_code):
        rows = weave_code.strip().split()
        matrix = []
        for i, row in enumerate(rows):
            interpolated_row = "0".join(row)
            if i % 2 == 0:
                interpolated_row = "0" + interpolated_row
            else:
                interpolated_row = interpolated_row + "0"
            interpolated_row = [int(x) for x in interpolated_row]
            matrix.append(interpolated_row)

        code = []
        for column in range(len(matrix[0])):
            code_entry = []
            for row in range(len(matrix)):
                if matrix[row][column] == 1:
                    code_entry.append(row + 1)
            code.append(code_entry)
        return code

    def validate_basic(self):
        """Check for basic errors in the matrix code."""
        n = self.n
        expected_length = (2 ** n - 2) // n
        if len(self.code) != expected_length:
            raise ValueError(f"Wrong length: code should be of length {expected_length}")

        last_x = self.code[-1]
        for x in self.code:
            if last_x == x:
                raise ValueError("Immediate repetitions are not allowed in code")
            last_x = x

        for k in range(1, n - 1):
            expected = math.comb(n, k) // n
            count = 0
            for x in self.code:
                if x == k:
                    count += 1
            if count != expected:
                raise ValueError(f"Expected {expected} instances of {k}")

    def validate_venn(self):
        """Check that this is in fact a Venn diagram."""
        n = self.n

        # I am not sure if this validation code is correct, sorry
        ranks = [False] * (2 ** n)
        ranks[0] = ranks[-1] = True
        p = list(range(n))
        for swap_row in self.full_code():
            a = swap_row
            b = swap_row - 1
            p[a], p[b] = p[b], p[a]
            rank = sum([2 ** x for x in p[swap_row:]])
            if ranks[rank]:
                raise ValueError(f"Duplicate rank {rank}")
            ranks[rank] = True
        if not all(ranks):
            raise ValueError(f"Not all ranks represented")

    def condense(self):
        """Condense adjacent swaps"""
        pass

    def full_code(self):
        """Return the code duplicated n times."""
        full_code = []
        for i in range(self.n):
            full_code += self.code
        return full_code

    def get_spline_stage_1(self, index=0):
        """Retrieve Cartesian coordinates and angles of each spline control point."""
        angle_scaling = 1.2

        unraveled_points = []
        row, column = 0, index * len(self.condensed_code)
        for i in range(self.n):
            for swap_rows in self.condensed_code:
                if row + 1 in swap_rows:
                    unraveled_points.append((row + 1, column, -0.25 * math.pi * angle_scaling))
                    row += 1
                elif row in swap_rows:
                    unraveled_points.append((row, column, 0.25 * math.pi * angle_scaling))
                    row -= 1
                column += 1

        inner_radius = 30
        spacing = 5

        control_points = []
        for row, column, angle in unraveled_points:
            radius = inner_radius + spacing * row
            theta = column * 2 * math.pi / (self.n * len(self.condensed_code))
            new_angle = angle + theta + math.pi * 0.5
            x = radius * math.cos(theta)
            y = radius * math.sin(theta)
            control_points.append((x, y, new_angle))

        return control_points

    def get_splines(self, index=0):
        """Get the shape of a single curve as a list of Splines."""
        control_points = self.get_spline_stage_1(index=index)

        splines = []
        for i in range(len(control_points)):
            x_1, y_1, theta_1 = control_points[i]
            x_2, y_2, theta_2 = control_points[(i + 1) % len(control_points)]
            spline = MetafontBezier(x_1, y_1, x_2, y_2, theta_1, theta_2)
            splines.append(spline)

        return splines

    def get_bezier_control_points(self, index=0):
        """Get the shape of a single curve as a list of cubic Bezier control points."""
        return [
            [(x.control_points[i, 0], x.control_points[i, 1]) for i in range(4)]
            for x in self.get_splines(index=index)
        ]

    def get_polygon(self, index=0):
        """Get the shape of a single curve as a polygon."""
        splines = self.get_splines(index)
        resolution = 10
        points = []
        for spline in splines:
            for i in range(resolution):
                points.append(spline(i / resolution))
        return points

    def check_regions(self):
        """Approximate this Venn diagram with polygons and use Shapely to check
        that the diagram is valid."""
        original_curve = shapely.geometry.Polygon(self.get_polygon())
        curves = []
        for i in range(self.n):
            angle = 2 * math.pi * i / self.n
            curve = shapely.affinity.rotate(
                original_curve, angle, origin=(0, 0), use_radians=True
            )
            curves.append(curve)

        # Region at index 0 is an empty set.
        regions = [[]]
        for rank in range(1, 2 ** self.n):
            curves_included = []
            curves_excluded = []
            tmp_rank = rank
            for i in range(self.n):
                if tmp_rank % 2 == 0:
                    curves_excluded.append(curves[i])
                else:
                    curves_included.append(curves[i])
                tmp_rank //= 2

            region = curves_included[0]
            for curve in curves_included[1:]:
                region = region.intersection(curve)
            for curve in curves_excluded:
                region = region.difference(curve)

            assert not region.is_empty

    def export_json(self):
        return {
            "n": self.n,
            "bezier_control_points": self.get_bezier_control_points(),
        }

    def plot(self):
        import matplotlib.pyplot as plt
        import matplotlib.patches
        import matplotlib.collections

        fig, ax = plt.subplots()
        polygons = [matplotlib.patches.Polygon(self.get_polygon(i)) for i in range(diagram.n)]
        patches = matplotlib.collections.PatchCollection(polygons, alpha=0.2)
        ax.add_collection(patches)
        plt.xlim(-100, 100)
        plt.ylim(-100, 100)
        plt.show()

DIAGRAMS = {
    "victoria": VennDiagram(7, "100000 110010 110111 101111 001101 000100"),
    "adelaide": VennDiagram(7, "10000 11010 11111 11111 01101 00100"),
    "massey": VennDiagram(7, "100000 110001 110111 111110 111000 010000"),
    "manawatu": VennDiagram(7, "1000000 1000101 1101101 0111011 0011010 0010000"),
    "palmerston_north": VennDiagram(7, "1000000 1100010 1110110 1011101 0001101 0000100"),
    "hamilton": VennDiagram(7, "10000 10101 11111 11111 11010 10000")
}

if __name__ == "__main__":
    import json
    diagrams_json = {}
    for name, diagram in DIAGRAMS.items():
        diagrams_json[name] = diagram.export_json()

    with open("app/venn_diagrams.js", "w") as f:
        f.write("const venn_diagrams = ");
        json.dump(diagrams_json, f)
        f.write(";");

    DIAGRAMS["victoria"].plot()