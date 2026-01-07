"""
Model requirements for tool execution
"""

from enum import Enum
from dataclasses import dataclass, field

class ModelCapability(Enum):
    """What the model needs to be able to do"""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    IMAGE_GENERATION = "image_generation"
    IMAGE_ANALYSIS = "image_analysis"
    AUDIO_GENERATION = "audio_generation"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    EMBEDDING = "embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"

@dataclass
class ModelRequirement:
    """Specifies what model capabilities are needed"""
    
    required_capabilities: list[ModelCapability]
    
    # Model recommendations
    recommended_local_models: list[str] = field(default_factory=list)
    recommended_api_models: list[str] = field(default_factory=list)
    
    # Minimum specs
    min_vram_gb: float | None = None
    min_params: str | None = None  # "3B", "7B", etc
    
    # Optional: specific model needed
    requires_specific_model: str | None = None
    
    def is_satisfied_by(self, available_models: dict) -> bool:
        """Check if available models meet requirements"""
        
        for capability in self.required_capabilities:
            if capability.value not in available_models:
                return False
        
        return True
    
    def get_missing_capabilities(self, available_models: dict) -> list[ModelCapability]:
        """Return list of missing capabilities"""
        return [cap for cap in self.required_capabilities 
                if cap.value not in available_models]

# Common requirement presets
class ModelRequirements:
    """Pre-defined common requirements"""
    
    TEXT_ONLY = ModelRequirement(
        required_capabilities=[ModelCapability.TEXT_GENERATION],
        recommended_local_models=["llama3.2:3b", "mistral:7b"],
        min_params="3B"
    )
    
    CODE_GEN = ModelRequirement(
        required_capabilities=[ModelCapability.CODE_GENERATION],
        recommended_local_models=["deepseek-coder:6.7b", "codellama:7b"],
        min_params="7B"
    )
    
    IMAGE_GEN = ModelRequirement(
        required_capabilities=[ModelCapability.IMAGE_GENERATION],
        recommended_local_models=["stable-diffusion"],
        recommended_api_models=["dall-e-3", "midjourney"],
        min_vram_gb=6.0,
        requires_specific_model="stable-diffusion-xl"
    )
    
    IMAGE_ANALYSIS = ModelRequirement(
        required_capabilities=[ModelCapability.VISION, ModelCapability.TEXT_GENERATION],
        recommended_local_models=["llava:7b", "bakllava:7b"],
        recommended_api_models=["gpt-4-vision", "claude-3-opus"],
        min_vram_gb=8.0
    )
    
    AUDIO_TRANSCRIPTION = ModelRequirement(
        required_capabilities=[ModelCapability.AUDIO_TRANSCRIPTION],
        recommended_local_models=["whisper:base", "whisper:small"],
        recommended_api_models=["whisper-api"],
        min_vram_gb=2.0
    )
    
    EMBEDDING = ModelRequirement(
        required_capabilities=[ModelCapability.EMBEDDING],
        recommended_local_models=["all-minilm:l6-v2"],
        min_params="100M"
    )