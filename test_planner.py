# test_planner.py
from memory import Memory
from planner import Planner
import json
memory = Memory()
planner = Planner(memory)

# Test 1: Simple goal
plan = planner.create_plan("Find all topics about music and summarize what I know")

print("\n=== PLAN ===")
print(plan.to_readable())

print("\n=== EXECUTING ===")
result = planner.execute_full_plan(plan.id)

print("\n=== RESULTS ===")
print(json.dumps(result, indent=2))