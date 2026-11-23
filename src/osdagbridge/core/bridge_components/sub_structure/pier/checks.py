"""Simple geometric checks on the pier (not a structural design)."""


def check_pier(part, p) -> list[str]:
    issues = []
    if part.props["Height"] <= 0:
        issues.append(f"{part.name}: height must be positive")
    if p.cover < 40:
        issues.append(f"{part.name}: cover {p.cover} mm is below 40 mm")
    return issues
