"""Data models for defensive static security analysis."""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class FileHashes:
    md5: str
    sha1: str
    sha256: str
    git_blob_sha1: str


@dataclass(frozen=True)
class Finding:
    id: str
    category: str
    severity: str
    confidence: float
    description: str
    evidence: str
    source: str


@dataclass
class SecurityReport:
    path: str
    size: int
    file_type: str
    entropy: float
    hashes: FileHashes
    iocs: Dict[str, List[str]] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    children: List["SecurityReport"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def risk_score(self) -> int:
        # Keep structural/static signals useful for triage without allowing a
        # handful of correlated heuristics to imply a deterministic malware verdict.
        weights = {"info": 0, "low": 5, "medium": 10, "high": 20, "critical": 35}
        score = sum(weights.get(item.severity, 0) * item.confidence for item in self.all_findings())
        return min(100, int(round(score)))

    @property
    def risk_level(self) -> str:
        score = self.risk_score
        if score >= 80:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 25:
            return "medium"
        if score > 0:
            return "low"
        return "info"

    def all_findings(self) -> List[Finding]:
        result = list(self.findings)
        for child in self.children:
            result.extend(child.all_findings())
        return result

    def to_dict(self) -> dict:
        result = asdict(self)
        result["risk_score"] = self.risk_score
        result["risk_level"] = self.risk_level
        return result
