import duckdb
import json

conn = duckdb.connect('companion.db')

# NEW: Show self-facts first
print("\n🌙 SELENE'S SELF-KNOWLEDGE\n")
print("=" * 70)

self_facts = conn.execute("""
    SELECT category, fact, locked
    FROM self_facts
    ORDER BY category, created_at
""").fetchall()

if self_facts:
    current_category = None
    for sf in self_facts:
        if sf[0] != current_category:
            current_category = sf[0]
            print(f"\n{current_category.upper()}:")
        
        lock_icon = "🔒" if sf[2] else "🔓"
        print(f"  {lock_icon} {sf[1]}")
else:
    print("No self-facts found")

print("\n" + "=" * 70)
print("📈 OVERALL STATISTICS\n")

print("\n📊 TOPIC & FACT STATISTICS\n")
print("=" * 70)

topics = conn.execute("""
    SELECT topic_name, message_count, created_at
    FROM topics
    ORDER BY message_count DESC
""").fetchall()

for topic in topics:
    print(f"\n📂 {topic[0]}")
    print(f"   Messages: {topic[1]}")
    print(f"   Created: {topic[2]}")

row = conn.execute("SELECT COUNT(*) FROM topic_facts").fetchone()
total_facts = row[0] if row and row[0] is not None else 0
print(f"Total facts collected: {total_facts}")

fact_type_dist = conn.execute("""
    SELECT fact_type, COUNT(*) as count
    FROM topic_facts
    GROUP BY fact_type
    ORDER BY count DESC
""").fetchall()

if fact_type_dist:
    print("\nFact type distribution across all topics:")
    for ft in fact_type_dist:
        pct = (ft[1] / total_facts * 100) if total_facts else 0
        print(f"   {ft[0]}: {ft[1]} ({pct:.1f}%)")

conn.close()