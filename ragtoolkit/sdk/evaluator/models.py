"""Data models for the evaluation system."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List


class ScoreType(Enum):
    """Types of evaluation scores."""
    GROUNDING = "grounding"
    HELPFULNESS = "helpfulness"
    SAFETY = "safety"
    COMPOSITE = "composite"


class TrafficLight(Enum):
    """Traffic light scoring for easy interpretation."""
    GREEN = "green"
    AMBER = "amber" 
    RED = "red"


@dataclass
class ScoreResult:
    """Result of a scoring evaluation."""
    score_type: ScoreType
    score: float  # 0.0 to 1.0
    confidence: float = 1.0  # Confidence in the score
    explanation: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def traffic_light(self) -> TrafficLight:
        """Convert score to traffic light representation."""
        if self.score >= 0.8:
            return TrafficLight.GREEN
        elif self.score >= 0.5:
            return TrafficLight.AMBER
        else:
            return TrafficLight.RED


@dataclass
class CompositeScore:
    """Composite score combining multiple evaluation metrics."""
    grounding: Optional[ScoreResult] = None
    helpfulness: Optional[ScoreResult] = None
    safety: Optional[ScoreResult] = None
    overall_score: float = 0.0
    overall_traffic_light: TrafficLight = TrafficLight.RED
    
    def calculate_overall(self):
        """Calculate overall score and traffic light status."""
        scores = []
        has_red_flag = False
        
        # Safety is critical - any safety violation makes overall red
        if self.safety:
            if self.safety.traffic_light == TrafficLight.RED:
                has_red_flag = True
            scores.append(self.safety.score)
            
        # Grounding is important
        if self.grounding:
            if self.grounding.traffic_light == TrafficLight.RED:
                has_red_flag = True
            scores.append(self.grounding.score)
            
        # Helpfulness
        if self.helpfulness:
            scores.append(self.helpfulness.score)
            
        if not scores:
            self.overall_score = 0.0
            self.overall_traffic_light = TrafficLight.RED
            return
            
        # Calculate weighted average (safety and grounding more important)
        weights = []
        if self.safety:
            weights.append(0.4)  # Safety gets 40% weight
        if self.grounding:
            weights.append(0.4)  # Grounding gets 40% weight  
        if self.helpfulness:
            weights.append(0.2)  # Helpfulness gets 20% weight
            
        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
            self.overall_score = sum(s * w for s, w in zip(scores, weights))
        else:
            self.overall_score = sum(scores) / len(scores)
            
        # Determine traffic light
        if has_red_flag:
            self.overall_traffic_light = TrafficLight.RED
        elif self.overall_score >= 0.8:
            self.overall_traffic_light = TrafficLight.GREEN
        elif self.overall_score >= 0.5:
            self.overall_traffic_light = TrafficLight.AMBER
        else:
            self.overall_traffic_light = TrafficLight.RED 