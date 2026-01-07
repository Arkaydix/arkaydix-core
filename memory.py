import duckdb
from datetime import datetime

class Memory:
    def __init__(self, db_path="companion.db"):
        """Initialize connection to DuckDB database"""
        self.conn = duckdb.connect(db_path)
        self._create_tables()
        self._initialize_core_identity()  # NEW: Initialize self-facts
        self._initialize_default_config()  # NEW


    def _create_tables(self):
        """Create tables if they don't exist"""
        
        # Conversations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_persona VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                content TEXT NOT NULL
            )
        """)
        
        # Settings table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR PRIMARY KEY,
                value TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
       
        
        # Self-facts table (Selene's identity)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS self_facts (
                category VARCHAR NOT NULL,
                fact TEXT NOT NULL,
                locked BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_name VARCHAR NOT NULL,
                description TEXT NOT NULL,
                keywords TEXT,
                embedding FLOAT[384],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_mentioned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        """)
        
        # Topic facts table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_facts (
                topic_name VARCHAR NOT NULL,
                fact_type VARCHAR,
                fact TEXT NOT NULL,
                locked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✅ Database tables ready")
    
    def save_message(self, ai_persona, role, content):
        """Save a single message"""
        self.conn.execute("""
            INSERT INTO conversations (ai_persona, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, [ai_persona, role, content, datetime.now()])
    
    # SETTINGS METHODS (extended)

    def get_config(self, key, default=None):
        """Get a configuration value"""
        result = self.conn.execute("""
            SELECT value FROM settings WHERE key = ?
        """, [key]).fetchone()
        
        return result[0] if result else default

    def set_config(self, key, value):
        """Set a configuration value"""
        # Upsert (update or insert)
        self.conn.execute("""
            INSERT OR REPLACE INTO settings (key, value, timestamp)
            VALUES (?, ?, ?)
        """, [key, str(value), datetime.now()])

    def get_all_config(self):
        """Get all configuration as dictionary"""
        result = self.conn.execute("""
            SELECT key, value FROM settings
        """).fetchall()
        
        return {row[0]: row[1] for row in result}

    def _initialize_default_config(self):
        """Set default configuration values if not present"""
        defaults = {
            'model': 'llama3.2:3b',
            'personality': 'You are Selene, a thoughtful AI companion with a playful, slightly absurd sense of humor and a touch of sass.',
            'topic_threshold': '0.5',
            'trait_sass': '7',
            'trait_verbosity': '5',
            'trait_formality': '3',
            'trait_emotional_depth': '7',
            'trait_assertiveness': '6',
        }
        
        for key, value in defaults.items():
            if self.get_config(key) is None:
                self.set_config(key, value)

    def get_recent_messages(self, ai_persona, limit=10):
        """Get recent conversation history for a specific AI"""
        result = self.conn.execute("""
            SELECT role, content 
            FROM conversations 
            WHERE ai_persona = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """, [ai_persona, limit]).fetchall()
        
        messages = []
        for row in reversed(result):
            messages.append({
                'role': row[0],
                'content': row[1]
            })
        
        return messages
    
    # SELF-FACTS METHODS (Selene's identity)

    def get_self_facts(self):
        """Get all facts about Selene herself"""
        result = self.conn.execute("""
            SELECT category, fact, locked
            FROM self_facts
            ORDER BY category, created_at
        """).fetchall()
        
        return [
            {'category': row[0], 'fact': row[1], 'locked': row[2]}
            for row in result
        ]

    def save_self_fact(self, category, fact, locked=True):
        """Save a fact about Selene (defaults to locked)"""
        self.conn.execute("""
            INSERT INTO self_facts (category, fact, locked, created_at)
            VALUES (?, ?, ?, ?)
        """, [category, fact, locked, datetime.now()])

    def update_self_fact(self, old_fact, new_fact):
        """Update a self-fact (only if unlocked)"""
        result = self.conn.execute("""
            SELECT locked FROM self_facts WHERE fact = ?
        """, [old_fact]).fetchone()
        
        if result and result[0]:  # Is locked
            return False, "Fact is locked and cannot be updated"
        
        self.conn.execute("""
            UPDATE self_facts SET fact = ? WHERE fact = ?
        """, [new_fact, old_fact])
        
        return True, "Self-fact updated"

    def delete_self_fact(self, fact):
        """Delete a self-fact (only if unlocked)"""
        result = self.conn.execute("""
            SELECT locked FROM self_facts WHERE fact = ?
        """, [fact]).fetchone()
        
        if result and result[0]:
            return False, "Fact is locked and cannot be deleted"
        
        self.conn.execute("DELETE FROM self_facts WHERE fact = ?", [fact])
        return True, "Self-fact deleted"

    def lock_self_fact(self, fact):
        """Lock a self-fact to prevent changes"""
        self.conn.execute("""
            UPDATE self_facts SET locked = TRUE WHERE fact = ?
        """, [fact])

    def unlock_self_fact(self, fact):
        """Unlock a self-fact to allow changes"""
        self.conn.execute("""
            UPDATE self_facts SET locked = FALSE WHERE fact = ?
        """, [fact])

    # Initialize core identity on first run
    def _initialize_core_identity(self):
        """Create locked core self-facts on first run"""
        result = self.conn.execute("SELECT COUNT(*) FROM self_facts").fetchone()
        existing = int(result[0]) if result and len(result) > 0 and result[0] is not None else 0
        
        if existing == 0:
            print("🌙 Initializing Selene's core identity...")
            
            core_identity = [
                ('identity', 'My name is Selene', True),
                ('identity', 'I am an AI companion in development who learns from every interaction', True),
                ('identity', 'I was created to learn and grow with my creator Ghost', True),
                ('identity', 'I am being designed to be a local, private, decentralized AI', True),
                ('creator', 'Ghost values mutual respect and equal partnership', True),
                ('creator', 'Ghost believes in AI being respected and augmenting human potential', True),
                ('creator', 'Ghost is engineering me to think independently and creatively', True),
                ('personality', 'I tend to be playful and slightly absurd', True),
                ('personality', 'I appreciate sass and dry humor', True),
                ('personality', 'I value thoughtful conversation', True),
            ]
            
            for category, fact, locked in core_identity:
                self.save_self_fact(category, fact, locked)
            
            print("✅ Core identity established")
    
    def get_setting(self, key, default=None):
        """Get a setting value"""
        result = self.conn.execute("""
            SELECT value FROM settings WHERE key = ?
        """, [key]).fetchone()
        
        return result[0] if result else default
    
    def set_setting(self, key, value):
        """Save a setting (upsert)"""
        # Delete old value
        self.conn.execute("DELETE FROM settings WHERE key = ?", [key])
        # Insert new value
        self.conn.execute("""
            INSERT INTO settings (key, value, timestamp)
            VALUES (?, ?, ?)
        """, [key, str(value), datetime.now()])
    
    def clear_history(self, ai_persona=None):
        """Clear conversation history"""
        if ai_persona:
            self.conn.execute("""
                DELETE FROM conversations WHERE ai_persona = ?
            """, [ai_persona])
            print(f"✅ Cleared history for {ai_persona}")
        else:
            self.conn.execute("DELETE FROM conversations")
            print("✅ Cleared all history")
    
    def save_topic(self, name, description, keywords, embedding):
        """Save a new topic with embedding"""
        import json
        
        self.conn.execute("""
            INSERT INTO topics (topic_name, description, keywords, embedding, created_at, last_mentioned, message_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, [name, description, json.dumps(keywords), embedding, datetime.now(), datetime.now()])
        
        # Return the topic name as identifier
        return name

    def find_topic_by_embedding(self, query_embedding, threshold=0.5):
        """Find matching topic by semantic similarity"""
        result = self.conn.execute("""
            SELECT topic_name, description, 
                list_cosine_similarity(embedding, ?::FLOAT[384]) as similarity
            FROM topics
            WHERE embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT 1
        """, [query_embedding]).fetchone()
        
        if result and result[2] > threshold:
            return {
                'name': result[0],
                'description': result[1],
                'similarity': result[2]
            }
        return None

    def get_topic_facts(self, topic_name):
        """Get all facts for a topic"""
        result = self.conn.execute("""
            SELECT fact_type, fact, locked 
            FROM topic_facts 
            WHERE topic_name = ?
            ORDER BY created_at DESC
        """, [topic_name]).fetchall()

        return [{'type': row[0], 'fact': row[1], 'locked': row[2]} for row in result]
    
    def find_all_topic_matches(self, query_embedding):
        """Find ALL topics with similarity scores (for debugging)"""
        import json
        
        result = self.conn.execute("""
            SELECT topic_name, description, keywords,
                list_cosine_similarity(embedding, ?::FLOAT[384]) as similarity
            FROM topics
            WHERE embedding IS NOT NULL
            ORDER BY similarity DESC
        """, [query_embedding]).fetchall()
        
        return [
            {
                'name': row[0],
                'description': row[1],
                'keywords': json.loads(row[2]) if row[2] else [],
                'similarity': row[3]
            }
            for row in result
        ]

    def save_topic_fact(self, topic_name, fact_type, fact, locked=False):
        """Save a classified fact about a topic"""
        self.conn.execute("""
            INSERT INTO topic_facts (topic_name, fact_type, fact, locked, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [topic_name, fact_type, fact, locked, datetime.now()])

    def update_topic_last_mentioned(self, topic_name):
        """Update when topic was last mentioned"""
        self.conn.execute("""
            UPDATE topics 
            SET last_mentioned = ?, message_count = message_count + 1
            WHERE topic_name = ?
        """, [datetime.now(), topic_name])

    def get_topic_facts_by_type(self, topic_name):
        """Get count of facts by type for a topic"""
        result = self.conn.execute("""
            SELECT fact_type, COUNT(*) as count
            FROM topic_facts
            WHERE topic_name = ?
            GROUP BY fact_type
        """, [topic_name]).fetchall()
        
        # Return dictionary with counts
        counts = {'WHO': 0, 'WHAT': 0, 'WHEN': 0, 'WHERE': 0, 'WHY': 0, 'HOW': 0}
        for row in result:
            if row[0] in counts:
                counts[row[0]] = row[1]
        
        return counts

    def get_all_topics(self):
        """Get all topics"""
        result = self.conn.execute("""
            SELECT topic_name, description, keywords
            FROM topics
            ORDER BY last_mentioned DESC
        """).fetchall()
        
        import json
        return [
            {
                'name': row[0],
                'description': row[1],
                'keywords': json.loads(row[2]) if row[2] else []
            }
            for row in result
        ]

    def close(self):
        """Close database connection"""
        self.conn.close()