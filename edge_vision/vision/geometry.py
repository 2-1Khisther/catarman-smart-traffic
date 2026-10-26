"""Pure geometry helpers (no OpenCV), so they are easy to unit test."""


def point_in_polygon(pt, poly):
    """Ray casting. pt = (x, y); poly = [(x, y), ...] with 3+ points."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def side(pt, a, b):
    """Which side of line a->b the point is on: +1, -1, or 0 (on the line)."""
    v = (b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0])
    return (v > 0) - (v < 0)


def segments_intersect(p1, p2, a, b):
    """True if segment p1-p2 crosses segment a-b (touching counts)."""
    d1, d2 = side(p1, a, b), side(p2, a, b)
    d3, d4 = side(a, p1, p2), side(b, p1, p2)
    if d1 != d2 and d3 != d4:
        return True

    def on_seg(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])

    return ((d1 == 0 and on_seg(a, p1, b)) or (d2 == 0 and on_seg(a, p2, b))
            or (d3 == 0 and on_seg(p1, a, p2)) or (d4 == 0 and on_seg(p1, b, p2)))


def crossed_stop_line(prev, cur, a, b, queue_side):
    """True only when a vehicle moves from the queue side of stop line a-b to the other side.

    Reversing back over the line, or moving along it, does not count.
    """
    if prev is None:
        return False
    return (side(prev, a, b) == queue_side and side(cur, a, b) == -queue_side
            and segments_intersect(prev, cur, a, b))


def polygon_centroid(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return sum(xs) / len(xs), sum(ys) / len(ys)
