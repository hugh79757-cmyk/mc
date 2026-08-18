from dataclasses import dataclass, field


@dataclass
class ContractSpec:
    """Blog-specific contract loaded from YAML."""
    blog_id: str = ""
    role: str = ""
    required_sections: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    min_specific_facts: int = 0
    max_generic_ratio: float = 0.5
    cta_max_count: int = 2
    thumbnail_keyword_match: bool = False


@dataclass
class GateResult:
    """Result of validating a post against a contract."""
    passed: bool
    violations: list[str] = field(default_factory=list)
    score: float = 1.0
