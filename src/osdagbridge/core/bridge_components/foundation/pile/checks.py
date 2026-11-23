"""Geometric rules of thumb for a pile group (not a structural design)."""
import math


def check_pile_group(positions, p) -> list[str]:
    issues = []
    for i, a in enumerate(positions):
        for b in positions[i + 1:]:
            d = math.dist(a, b)
            if d < 3 * p.pile_dia - 1e-6:
                issues.append(f"piles at {a} and {b} are {d:.0f} mm apart, "
                              f"less than 3 x diameter ({3 * p.pile_dia:.0f} mm)")
    return issues
