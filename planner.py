from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime
import json
import uuid
import ollama
from typing import Optional
class StepStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_TOOL = "needs_tool"  # Tool not registered yet

class Complexity(Enum):
    ATOMIC = "atomic"      # Single action
    SIMPLE = "simple"      # 2-3 steps
    MODERATE = "moderate"  # 4-7 steps
    COMPLEX = "complex"    # 8+ steps

@dataclass
class ToolCapability:
    """What a tool can do - shown to LLM during planning"""
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    examples: list[str] = field(default_factory=list)
    
    def to_prompt(self) -> str:
        return f"""[{self.name}]
{self.description}
Inputs: {json.dumps(self.input_schema)}
Outputs: {json.dumps(self.output_schema)}
Examples: {', '.join(self.examples)}"""

@dataclass
class PlanStep:
    """Single step in execution plan"""
    id: str
    description: str
    tool: Optional[str]  # None = LLM generation
    tool_input: dict = field(default_factory=dict)
    expected_output: str = ""
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    output_data: Any = None
    error: Optional[str] = None
    deferred_requirements: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "tool_input": self.tool_input,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "output_data": str(self.output_data)[:200] if self.output_data else None,
            "deferred": self.deferred_requirements
        }

@dataclass
class Plan:
    """Complete execution plan"""
    id: str
    goal: str
    complexity: Complexity
    steps: list[PlanStep]
    created_at: datetime
    context: dict = field(default_factory=dict)
    
    def to_readable(self) -> str:
        """Human/LLM readable format"""
        status_icons = {
            "pending": "○",
            "ready": "◐",
            "executing": "◑",
            "completed": "●",
            "failed": "✗",
            "needs_tool": "?"
        }
        
        lines = [
            f"Plan: {self.goal}",
            f"Complexity: {self.complexity.value}",
            f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"\nSteps ({len(self.steps)}):\n"
        ]
        
        for i, step in enumerate(self.steps, 1):
            icon = status_icons.get(step.status.value, "○")
            tool = f"[{step.tool}]" if step.tool else "[LLM]"
            
            lines.append(f"{icon} {i}. {step.description}")
            lines.append(f"   Tool: {tool}")
            
            if step.depends_on:
                lines.append(f"   Depends: {', '.join(step.depends_on)}")
            
            if step.deferred_requirements:
                lines.append(f"   ⚠️ Missing: {step.deferred_requirements}")
            
            if step.output_data:
                preview = str(step.output_data)[:80]
                lines.append(f"   Output: {preview}...")
            
            lines.append("")
        
        return "\n".join(lines)


class Planner:
    """Selene's planning and orchestration engine"""
    
    def __init__(self, memory, model='llama3.2:3b'):
        self.memory = memory
        self.model = model
        self.tools: dict[str, ToolCapability] = {}
        self.plans: dict[str, Plan] = {}
        
        # Register default LLM capability
        self._register_builtin_tools()
    
    def _register_builtin_tools(self):
        """Register Selene's built-in capabilities"""
        
        # LLM generation (default)
        self.register_tool(ToolCapability(
            name="llm_generate",
            description="General text generation and reasoning. Use when no specialized tool needed.",
            input_schema={"prompt": "string", "context": "optional dict"},
            output_schema={"response": "string"},
            examples=["Answer a question", "Summarize text", "Analyze and explain"]
        ))
        
        # Memory tools
        self.register_tool(ToolCapability(
            name="memory_search_topics",
            description="Search Selene's memory for topics by keyword or semantic similarity",
            input_schema={"query": "string", "limit": "int (default 5)"},
            output_schema={"topics": "list of {name, description, facts}"},
            examples=["Find topics about music", "Search for coding discussions"]
        ))
        
        self.register_tool(ToolCapability(
            name="memory_get_facts",
            description="Get all facts about a specific topic",
            input_schema={"topic_name": "string"},
            output_schema={"facts": "list of {type, content, locked}"},
            examples=["Get facts about Jazz Guitar", "What do I know about Python"]
        ))
        
        self.register_tool(ToolCapability(
            name="memory_save_fact",
            description="Save a new fact to memory under a topic",
            input_schema={"topic_name": "string", "fact_type": "WHO|WHAT|WHEN|WHERE|WHY|HOW", "fact": "string"},
            output_schema={"success": "boolean"},
            examples=["Save that user likes coffee", "Remember user's birthday"]
        ))
    
    def register_tool(self, capability: ToolCapability):
        """Register a new tool capability"""
        self.tools[capability.name] = capability
        print(f"🔧 Registered tool: {capability.name}")
    
    def get_tool_manifest(self) -> str:
        """Get all available tools in LLM-readable format"""
        lines = ["# Available Tools\n"]
        for tool in self.tools.values():
            lines.append(tool.to_prompt())
            lines.append("")
        return "\n".join(lines)

    from typing import Optional

    def create_plan(self, goal: str, context: Optional[dict] = None) -> Plan:        
        """Create an execution plan for a goal.
            LLM analyzes and breaks down into steps.
            """
            
            # Build context string properly
        context_str = "None"
        if context:
            context_str = json.dumps(context, indent=2)
            
        planning_prompt = f"""You are a task planner. Your ONLY output must be valid JSON.

        Goal: {goal}

        Context: {context_str}

        Available Tools:
        {self.get_tool_manifest()}

        Create a plan with these fields:
        - complexity: one of "atomic", "simple", "moderate", "complex"
        - reasoning: brief explanation
        - steps: array of step objects

        Each step object:
        - id: "step_1", "step_2", etc
        - description: what this step does
        - tool: tool name from above OR null for LLM
        - tool_input: dict with required inputs for the tool
        - expected_output: what you expect back
        - depends_on: array of step IDs this depends on (empty array if none)
        - deferred_requirements: array of missing requirements (empty array if none)

        CRITICAL: Output ONLY the JSON object. No explanation before or after. No markdown.

        Example format:
        {{
            "complexity": "simple",
            "reasoning": "Only needs memory search and summary",
            "steps": [
                {{
                    "id": "step_1",
                    "description": "Search memory for music topics",
                    "tool": "memory_search_topics",
                    "tool_input": {{"query": "music", "limit": 5}},
                    "expected_output": "List of music-related topics",
                    "depends_on": [],
                    "deferred_requirements": []
                }},
                {{
                    "id": "step_2",
                    "description": "Summarize findings",
                    "tool": null,
                    "tool_input": {{"prompt": "Summarize the music topics found"}},
                    "expected_output": "Summary text",
                    "depends_on": ["step_1"],
                    "deferred_requirements": []
                }}
            ]
        }}

        Now create the plan as JSON:"""
            
        print("🧠 Creating plan...")
        
        # Call LLM
        response = ollama.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': planning_prompt}],
            stream=False,
            options={
                'temperature': 0.3,  # Lower temp for more structured output
                'num_predict': 2000   # Allow longer response
            }
        )
        
        # Parse response
        llm_output = response['message']['content'].strip()
        
        # Extract JSON from response (handle various formats)
        json_str = self._extract_json(llm_output)
        
        if not json_str:
            print(f"❌ Could not extract JSON from LLM response")
            print(f"Raw output: {llm_output[:500]}")
            raise ValueError("LLM did not return valid JSON")
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse extracted JSON: {e}")
            print(f"Extracted: {json_str[:500]}")
            raise
        
        # Validate required fields
        if "complexity" not in data or "steps" not in data:
            raise ValueError(f"Missing required fields in plan: {data.keys()}")
        
        # Build plan
        steps = []
        for s in data["steps"]:
            steps.append(PlanStep(
                id=s.get("id", f"step_{len(steps)+1}"),
                description=s.get("description", ""),
                tool=s.get("tool"),
                tool_input=s.get("tool_input", {}),
                expected_output=s.get("expected_output", ""),
                depends_on=s.get("depends_on", []),
                deferred_requirements=s.get("deferred_requirements", [])
            ))
        
        plan = Plan(
            id=f"plan_{uuid.uuid4().hex[:8]}",
            goal=goal,
            complexity=Complexity(data["complexity"]),
            steps=steps,
            created_at=datetime.now(),
            context={"reasoning": data.get("reasoning", "")}
        )
        
        self._update_ready_status(plan)
        self.plans[plan.id] = plan
        
        # Save to database
        self._save_plan_to_db(plan)
        
        print(f"✅ Plan created: {plan.id}")
        return plan

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response that might have extra text"""
        
        # Try 1: Direct JSON parse (ideal case)
        try:
            json.loads(text)
            return text
        except:
            pass
        
        # Try 2: Remove markdown code fences
        if "```json" in text or "```" in text:
            lines = text.split("\n")
            in_code = False
            json_lines = []
            
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    json_lines.append(line)
            
            if json_lines:
                potential = "\n".join(json_lines)
                try:
                    json.loads(potential)
                    return potential
                except:
                    pass
        
        # Try 3: Find JSON object by braces
        import re
        
        # Find outermost { }
        brace_count = 0
        start_idx = None
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx is not None:
                    potential = text[start_idx:i+1]
                    try:
                        json.loads(potential)
                        return potential
                    except:
                        pass
        
        # Try 4: Look for JSON between specific markers
        json_pattern = r'\{[\s\S]*\}'
        matches = re.findall(json_pattern, text)
        
        for match in matches:
            try:
                json.loads(match)
                return match
            except:
                continue
        
        return ""
    
    def _update_ready_status(self, plan: Plan):
        """Update which steps are ready to execute"""
        completed = {s.id for s in plan.steps if s.status == StepStatus.COMPLETED}
        
        for step in plan.steps:
            if step.status != StepStatus.PENDING:
                continue
            
            # Check if missing tools
            if step.deferred_requirements:
                unmet = [r for r in step.deferred_requirements 
                        if r.get("type") == "tool" and r.get("name") not in self.tools]
                if unmet:
                    step.status = StepStatus.NEEDS_TOOL
                    continue
            
            # Check dependencies
            if all(dep in completed for dep in step.depends_on):
                step.status = StepStatus.READY
    
    def get_next_steps(self, plan_id: str) -> list[PlanStep]:
        """Get steps ready to execute"""
        plan = self.plans.get(plan_id)
        if not plan:
            return []
        
        self._update_ready_status(plan)
        return [s for s in plan.steps if s.status == StepStatus.READY]
    
    def execute_step(self, plan_id: str, step_id: str) -> Any:
        """Execute a single step"""
        plan = self.plans.get(plan_id)
        if not plan:
            return None
        
        step = next((s for s in plan.steps if s.id == step_id), None)
        if not step or step.status != StepStatus.READY:
            return None
        
        step.status = StepStatus.EXECUTING
        
        try:
            # Get execution context
            ctx = self._get_execution_context(plan, step)
            
            # Execute based on tool
            if step.tool == "llm_generate" or step.tool is None:
                result = self._execute_llm(step, ctx)
            elif step.tool == "memory_search_topics":
                result = self._execute_memory_search(step)
            elif step.tool == "memory_get_facts":
                result = self._execute_get_facts(step)
            elif step.tool == "memory_save_fact":
                result = self._execute_save_fact(step)
            else:
                result = f"Tool '{step.tool}' not implemented yet"
            
            # Mark complete
            step.status = StepStatus.COMPLETED
            step.output_data = result
            plan.context[f"output_{step_id}"] = result
            
            self._update_ready_status(plan)
            return result
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            print(f"❌ Step failed: {e}")
            return None
    
    def _get_execution_context(self, plan: Plan, step: PlanStep) -> dict:
        """Get everything needed to execute a step"""
        dep_outputs = {}
        for dep_id in step.depends_on:
            dep_step = next((s for s in plan.steps if s.id == dep_id), None)
            if dep_step and dep_step.output_data:
                dep_outputs[dep_id] = dep_step.output_data
        
        return {
            "plan_goal": plan.goal,
            "step": step.to_dict(),
            "dependency_outputs": dep_outputs,
            "plan_context": plan.context
        }
    
    def _execute_llm(self, step: PlanStep, ctx: dict) -> str:
        """Execute LLM generation step"""
        prompt = step.tool_input.get("prompt", step.description)
        
        # Add context
        if ctx["dependency_outputs"]:
            prompt += f"\n\nContext from previous steps:\n{json.dumps(ctx['dependency_outputs'], indent=2)}"
        
        response = ollama.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False
        )
        
        return response['message']['content']
    
    def _execute_memory_search(self, step: PlanStep) -> dict:
        """Search memory topics"""
        query = step.tool_input.get("query", "")
        limit = step.tool_input.get("limit", 5)
        
        # Use existing embedding search
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        query_emb = embedder.encode(query).tolist()
        matches = self.memory.find_all_topic_matches(query_emb)
        
        results = []
        for match in matches[:limit]:
            facts = self.memory.get_topic_facts(match['name'])
            results.append({
                'name': match['name'],
                'similarity': match['similarity'],
                'facts': [f['fact'] for f in facts]
            })
        
        return {"topics": results}
    
    def _execute_get_facts(self, step: PlanStep) -> dict:
        """Get facts for a topic"""
        topic_name = step.tool_input.get("topic_name", "")
        facts = self.memory.get_topic_facts(topic_name)
        
        return {
            "topic": topic_name,
            "facts": [{'type': f['type'], 'content': f['fact'], 'locked': f['locked']} for f in facts]
        }
    
    def _execute_save_fact(self, step: PlanStep) -> dict:
        """Save a fact to memory"""
        topic = step.tool_input.get("topic_name", "")
        fact_type = step.tool_input.get("fact_type", "WHAT")
        fact = step.tool_input.get("fact", "")
        
        try:
            self.memory.save_topic_fact(topic, fact_type, fact)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _save_plan_to_db(self, plan: Plan):
        """Save plan to database for persistence"""
        self.memory.conn.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id VARCHAR PRIMARY KEY,
                goal TEXT,
                complexity VARCHAR,
                steps TEXT,
                created_at TIMESTAMP,
                context TEXT
            )
        """)
        
        self.memory.conn.execute("""
            INSERT INTO plans (id, goal, complexity, steps, created_at, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            plan.id,
            plan.goal,
            plan.complexity.value,
            json.dumps([s.to_dict() for s in plan.steps]),
            plan.created_at,
            json.dumps(plan.context)
        ])
    
    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID"""
        return self.plans.get(plan_id)
    
    def execute_full_plan(self, plan_id: str) -> dict:
        """Execute entire plan step by step"""
        plan = self.plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        results = []
        
        while next_steps := self.get_next_steps(plan_id):
            for step in next_steps:
                print(f"▶️ Executing: {step.description}")
                result = self.execute_step(plan_id, step.id)
                results.append({
                    "step": step.description,
                    "result": result
                })
        
        return {
            "plan_id": plan_id,
            "goal": plan.goal,
            "results": results,
            "final_plan": plan.to_readable()
        }