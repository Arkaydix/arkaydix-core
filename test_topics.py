import duckdb
from sentence_transformers import SentenceTransformer
import json

def test_topic_matching():
    """Interactive tool to test topic matching"""
    
    # Load model
    print("Loading embedding model...")
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Connect to database
    conn = duckdb.connect('companion.db')
    
    # Get all topics
    topics = conn.execute("""
        SELECT topic_name, description, keywords, embedding
        FROM topics
        ORDER BY created_at DESC
    """).fetchall()
    
    if not topics:
        print("No topics found in database. Have some conversations first!")
        return
    
    print(f"\n📂 Found {len(topics)} topics in database:\n")
    for i, topic in enumerate(topics, 1):
        keywords = json.loads(topic[2]) if topic[2] else []
        print(f"{i}. {topic[0]}")
        print(f"   Keywords: {', '.join(keywords)}")
        print(f"   Description: {topic[1][:80]}...")
        print()
    
    # Interactive testing
    print("=" * 60)
    print("TEST MODE: Enter conversation snippets to test matching")
    print("=" * 60)
    print()
    
    while True:
        test_text = input("\nEnter test conversation (or 'quit'): ").strip()
        
        if test_text.lower() == 'quit':
            break
        
        if not test_text:
            continue
        
        # Embed test text
        query_embedding = embedder.encode(test_text).tolist()
        
        # Find matches
        results = conn.execute("""
            SELECT topic_name, description,
                   list_cosine_similarity(embedding, ?::FLOAT[384]) as similarity
            FROM topics
            WHERE embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT 5
        """, [query_embedding]).fetchall()
        
        print("\n🔍 Match Results:")
        print("-" * 60)
        
        for i, result in enumerate(results, 1):
            sim_percent = result[2] * 100
            match_status = "✅ MATCH" if result[2] > 0.6 else "❌ NO MATCH"
            
            print(f"{i}. {result[0]} - {sim_percent:.1f}% similarity {match_status}")
            print(f"   {result[1][:100]}...")
            print()
        
        # Show what would happen
        top_match = results[0]
        if top_match[2] > 0.6:
            print(f"→ Would use existing topic: '{top_match[0]}'")
        else:
            print(f"→ Would create NEW topic (top match only {top_match[2]*100:.1f}%)")
    
    conn.close()

if __name__ == "__main__":
    test_topic_matching()