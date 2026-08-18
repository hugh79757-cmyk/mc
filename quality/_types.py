from dataclasses import dataclass, field


@dataclass
class ContractSpec:
    """Stub — full implementation comes from Phase 41 contract_loader."""
    blog_id: str = ""
    role: str = ""
    required_sections: list = field(default_factory=list)
    forbidden_patterns: list = field(default_factory=list)
    min_specific_facts: int = 0
    max_generic_ratio: float = 0.5
    cta_max_count: int = 2
    thumbnail_keyword_match: bool = False
