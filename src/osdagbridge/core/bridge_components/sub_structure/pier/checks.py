"""Simple geometric checks on the pier (not a structural design)."""


def check_pier(part, p) -> list[str]:
    issues = []
    if part.props["Height"] <= 0:
        issues.append(f"{part.name}: height must be positive")
    if p.rebar_cover <= 0:
        issues.append(f"{part.name}: cover must be positive")
    return issues
