import ollama
from collections import Counter
import re
MODEL = 'llama3.2:3b'
SELENE_PERSONALITY = "You are Selene, a thoughtful AI companion with a playful, slightly absurd sense of humor and a touch of sass."

class TopicExtractor:
    """Multi-step topic extraction with guaranteed structure"""
    
    def __init__(self, conversation):
        self.conversation = conversation
        self.state = "start"
        self.data = {
            'name': '',
            'description': '',
            'keywords': []
        }
    
    def extract(self):
        """Run all extraction steps"""
        try:
            self._extract_name()
            self._extract_description()
            self._extract_keywords()
            return self.data
        except Exception as e:
            print(f"❌ Topic extraction failed: {e}")
            return None
    
    def _extract_name(self):
        """Step 1: Extract topic name"""
        prompt = f"""Based on this conversation, what topic is being discussed?

Conversation:
{self.conversation}

Topic name (maximum 3 words, no punctuation):"""
        
        response = ollama.chat(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False
        )
        
        # Clean response
        name = response['message']['content'].strip()
        name = name.replace('"', '').replace("'", "")
        name = name.replace('.', '').replace(',', '')
        name = name.split('\n')[0]  # Take first line only
        
        # Limit to 3 words
        words = name.split()[:3]
        self.data['name'] = ' '.join(words)
        self.state = "has_name"
        
        print(f"  📝 Topic name: {self.data['name']}")
    
    def _extract_description(self):
        """Step 2: Extract rich description from actual conversation"""
        
        # ADD PERSONALITY PREFIX
        
        prompt = f"""{SELENE_PERSONALITY}

    Based on this recent conversation, write a detailed paragraph describing what was discussed. Include specific details, context, and the user's perspective or involvement. Write it in your natural voice - be conversational and let your personality show.

    Conversation:
    {self.conversation}

    Description paragraph (write naturally, in your own voice):"""
        
        response = ollama.chat(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=False
        )
        
        self.data['description'] = response['message']['content'].strip()
        self.state = "has_description"
        
        print(f"  📄 Description: {self.data['description'][:60]}...")
    
    def _extract_keywords(self):
        """Step 3: Extract keywords (include topic name)"""
        # Simple keyword extraction from conversation
        text = self.conversation.lower()
        words = re.findall(r'\b\w+\b', text)
        
        # Expanded common words filter
        common = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'is', 'are', 'was', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'can', 'about', 'just', 'really', 'very',
            'think', 'know', 'want', 'like', 'need', 'make', 'get', 'got',
            'user', 'assistant', 'you', 'your', 'that', 'this', 'these',
            'they', 'their', 'them', 'what', 'when', 'where', 'who', 'how'
        }
        
        keywords = [w for w in words if w not in common and len(w) > 3]
        
        # Get top 5 from conversation
        counts = Counter(keywords)
        top_keywords = [word for word, _ in counts.most_common(5)]
        
        # ADD TOPIC NAME WORDS AS KEYWORDS (most important!)
        topic_words = [w.lower() for w in self.data['name'].split() if len(w) > 2]
        
        # Combine: topic words first, then conversation keywords
        # Remove duplicates while preserving order
        combined = topic_words + [k for k in top_keywords if k not in topic_words]
        
        # Keep top 7 total (topic words + conversation keywords)
        self.data['keywords'] = combined[:7]
        self.state = "complete"
        
        print(f"  🔑 Keywords: {', '.join(self.data['keywords'])}")


class FactExtractor:
    """Extract and classify facts using 5W+1H system"""
    
    FACT_TYPES = {
        'WHO': 'Information about people (names, relationships, roles)',
        'WHAT': 'Actions, events, objects, preferences',
        'WHEN': 'Time, dates, schedules, frequency',
        'WHERE': 'Locations, places, settings',
        'WHY': 'Reasons, motivations, goals',
        'HOW': 'Methods, processes, techniques'
    }
    
    def __init__(self, conversation, topic_name, existing_facts=None):
        self.conversation = conversation
        self.topic_name = topic_name
        self.existing_facts = existing_facts or []  # NEW: track what we already know


    def extract(self):
        """Extract ONE classified fact"""
        
        # Step 1: Determine what type of fact is present
        fact_type = self._classify_fact_type()
        
        if not fact_type:
            print("  ⚠️ No factual information detected")
            return None
        
        print(f"  📋 Detected fact type: {fact_type}")
        
        # Step 2: Extract fact of that specific type
        fact = self._extract_typed_fact(fact_type)
        
        if not fact:
            return None
        
        # Step 3: Check for duplicates
        if self._is_duplicate(fact):
            print(f"  ⚠️ Duplicate fact - skipping")
            return None

        return {
            'type': fact_type,
            'content': fact
        }
    

    def _is_duplicate(self, new_fact):
        """Check if fact is too similar to existing facts"""
        new_lower = new_fact.lower()
        
        for existing in self.existing_facts:
            existing_lower = existing.lower()
            
            # Simple word overlap check
            new_words = set(new_lower.split())
            existing_words = set(existing_lower.split())
            
            overlap = len(new_words.intersection(existing_words))
            total = len(new_words.union(existing_words))
            
            if overlap / total > 0.7:  # 70% word overlap = duplicate
                return True
        
        return False

    def _classify_fact_type(self):
        """Determine what type of fact is present using LLM routing"""
        
        # Build context with existing facts
        context_section = ""
        if self.existing_facts:
            context_section = f"\nFacts already known about {self.topic_name}:\n" + "\n".join(f"- {fact}" for fact in self.existing_facts[:5])
        
        prompt = f"""Based on this conversation about {self.topic_name}, what NEW information is present that we don't already know?

Conversation (User is the human, Assistant is the AI):
{self.conversation}
{context_section}

Choose ONE type of NEW information:
A) WHO - People, names, relationships, roles
B) WHAT - Actions, events, preferences, objects, things user did/has/likes
C) WHEN - Time, dates, schedules, frequency, timing
D) WHERE - Locations, places, settings
E) WHY - Reasons, motivations, goals, purposes
F) HOW - Methods, processes, techniques, ways of doing things
G) NONE - No NEW factual information (everything was already known or just AI responses)

IMPORTANT: Only extract information the USER (human) shared, not what the Assistant said.

Answer with ONLY the letter (A, B, C, D, E, F, or G):"""
        
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            
            # Parse answer - extract first letter
            answer = response['message']['content'].strip().upper()
            
            # Handle various formats
            for char in answer:
                if char in 'ABCDEFG':
                    answer = char
                    break
            
            # Map to fact types
            type_map = {
                'A': 'WHO',
                'B': 'WHAT',
                'C': 'WHEN',
                'D': 'WHERE',
                'E': 'WHY',
                'F': 'HOW',
                'G': None
            }
            
            return type_map.get(answer, None)
            
        except Exception as e:
            print(f"  ❌ Classification failed: {e}")
            return None
    
    def _extract_typed_fact(self, fact_type):
        """Extract fact of specific type"""
        
        # Build context with existing facts
        context_section = ""
        if self.existing_facts:
            context_section = f"\n\nFacts we already know:\n" + "\n".join(f"- {fact}" for fact in self.existing_facts[:5])
        
        # Type-specific instructions
        type_instructions = {
            'WHO': 'Extract information about a person (name, role, or relationship) that the USER mentioned.',
            'WHAT': 'Extract what the USER did, wants, likes, has, or experienced.',
            'WHEN': 'Extract timing information the USER shared - when something happens, happened, or will happen.',
            'WHERE': 'Extract location information the USER shared - where they are, were, or go.',
            'WHY': 'Extract the reason, motivation, or purpose the USER mentioned.',
            'HOW': 'Extract the method, process, or way the USER described doing something.'
        }
        
        prompt = f"""From this conversation about {self.topic_name}:

{self.conversation}
{context_section}

{type_instructions[fact_type]}

IMPORTANT: 
- Only extract what the USER (human) said, NOT what the Assistant said
- Do NOT repeat facts we already know
- Extract ONE NEW specific fact
- Start with "User" and write one clear sentence

Fact:"""
        
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            
            fact = response['message']['content'].strip()
            
            # Clean up
            fact = fact.replace('"', '').replace("'", "").strip()
            
            # Remove common prefixes
            prefixes = ['Fact:', 'Answer:', 'Response:', 'New fact:']
            for prefix in prefixes:
                if fact.lower().startswith(prefix.lower()):
                    fact = fact[len(prefix):].strip()
            
            # Ensure it starts with "User"
            if not fact.lower().startswith('user'):
                fact = f"User {fact.lower()}"
            
            # Capitalize properly
            if len(fact) > 5:
                fact = fact[:5] + fact[5].upper() + fact[6:]
            
            return fact if len(fact) > 10 else None
            
        except Exception as e:
            print(f"  ❌ Extraction failed: {e}")
            return None