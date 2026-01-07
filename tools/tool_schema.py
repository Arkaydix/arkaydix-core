"""
Complete tool definition schema with type safety
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any
from .data_types import DataFormat, DataValidator
from .model_requirements import ModelRequirement

class ToolType(Enum):
    """Tool position in workflow"""
    STARTER = "starter"           # Can begin a chain
    PROCESSOR = "processor"       # Middle of chain
    ENDPOINT = "endpoint"         # Ends a chain
    BIDIRECTIONAL = "bidirectional"  # Can be anywhere

class CompatibilityMode(Enum):
    """How tool connects to others"""
    STRUCTURED = "structured"     # Explicit connections
    UNIVERSAL = "universal"       # Connects to everything
    CONTEXTUAL = "contextual"     # Semantic search only

@dataclass
class ToolIO:
    """Input or output specification"""
    name: str
    description: str
    format: DataFormat
    required: bool = True
    default: Any = None

@dataclass
class ToolMetadata:
    """Complete tool definition"""
    
    # Basic info
    name: str
    description: str
    category: str
    version: str = "1.0.0"
    author: str = "system"
    
    # Tool behavior
    tool_type: ToolType
    compatibility_mode: CompatibilityMode
    
    # I/O specifications
    inputs: list[ToolIO]
    outputs: list[ToolIO]
    
    # Compatibility (for STRUCTURED mode)
    accepts_input_from: list[str] = field(default_factory=list)
    compatible_next: list[str] = field(default_factory=list)
    
    # Semantic search (for CONTEXTUAL mode)
    semantic_tags: list[str] = field(default_factory=list)
    
    # Model requirements
    model_requirements: ModelRequirement | None = None
    
    # Examples
    examples: list[dict] = field(default_factory=list)
    
    # Execution
    execute_fn: Callable | None = None
    
    def validate_input(self, input_data: dict) -> tuple[bool, str]:
        """Validate input data matches schema"""
        
        errors = []
        
        for input_spec in self.inputs:
            # Check required fields
            if input_spec.required and input_spec.name not in input_data:
                errors.append(f"Missing required input: {input_spec.name}")
                continue
            
            # Validate format if present
            if input_spec.name in input_data:
                value = input_data[input_spec.name]
                if not DataValidator.validate(value, input_spec.format):
                    errors.append(
                        f"Input '{input_spec.name}' has wrong format. "
                        f"Expected {input_spec.format}, got {type(value).__name__}"
                    )
        
        if errors:
            return False, "; ".join(errors)
        
        return True, "Valid"
    
    def can_connect_to(self, other_tool: 'ToolMetadata') -> bool:
        """Check if this tool's output can connect to another tool's input"""
        
        # Universal tools connect to everything
        if self.compatibility_mode == CompatibilityMode.UNIVERSAL:
            return True
        
        # Check explicit compatibility
        if self.compatibility_mode == CompatibilityMode.STRUCTURED:
            if "*" in self.compatible_next:
                # Check output/input format compatibility
                return self._formats_compatible(other_tool)
            return other_tool.name in self.compatible_next
        
        # Contextual tools need semantic matching (handled elsewhere)
        return False
    
    def _formats_compatible(self, other_tool: 'ToolMetadata') -> bool:
        """Check if output formats match input formats"""
        
        # Get our output types
        our_outputs = {out.format.type for out in self.outputs}
        
        # Get their input types
        their_inputs = {inp.format.type for inp in other_tool.inputs}
        
        # Check for any overlap
        return bool(our_outputs & their_inputs)
    
    def to_prompt_format(self) -> str:
        """Format for LLM planning context"""
        
        input_desc = "\n".join([
            f"  - {inp.name} ({inp.format}): {inp.description}"
            for inp in self.inputs
        ])
        
        output_desc = "\n".join([
            f"  - {out.name} ({out.format}): {out.description}"
            for out in self.outputs
        ])
        
        return f"""[{self.name}]
{self.description}

Inputs:
{input_desc}

Outputs:
{output_desc}

Type: {self.tool_type.value}
Category: {self.category}
Examples: {', '.join([ex.get('description', '') for ex in self.examples])}"""