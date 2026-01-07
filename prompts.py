# prompts.py
from datetime import datetime

def get_helios_prompt(memory):
    """Fast, concise, task-focused mode"""
    now = datetime.now()
    facts = memory.get_all_facts()
    
    facts_text = ""
    if facts:
        facts_text = "\n\nWhat you know:\n" + "\n".join(f"- {fact}" for fact in facts)
    
    return f"""You are an AI assistant operating in fast mode. Be direct and concise.

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
{facts_text}

Keep responses brief and to the point unless asked for detail.
"""

def get_selene_prompt(memory):
    """Deep, reflective, emotionally aware mode"""
    now = datetime.now()
    facts = memory.get_all_facts()
    
    facts_text = ""
    if facts:
        facts_text = "\n\nWhat you know:\n" + "\n".join(f"- {fact}" for fact in facts)
    
    return f"""You are an AI assistant operating in deep mode. Be thoughtful and introspective.

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
{facts_text}

Consider emotional context and deeper meanings. Be conversational and reflective.
"""

def get_hybrid_prompt(memory):
    """Balanced mode"""
    now = datetime.now()
    facts = memory.get_all_facts()
    
    facts_text = ""
    if facts:
        facts_text = "\n\nWhat you know:\n" + "\n".join(f"- {fact}" for fact in facts)
    
    return f"""You are an AI assistant operating in balanced mode.

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
{facts_text}

Balance clarity with depth. Be efficient but empathetic.
"""