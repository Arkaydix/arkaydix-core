from collections import Counter
import re

class TopicTracker:
    """Track topic shifts using keyword analysis"""
    
    def __init__(self):
        self.current_keywords = []
        self.message_count = 0
    
    def check_shift(self, conversation_history):
        """Check if topic has shifted"""
        self.message_count += 1
        
        # Only check every 3 messages
        if self.message_count % 3 != 0:
            return False
        
        # Get recent keywords
        recent_keywords = self._extract_keywords(conversation_history, window=5)
        
        # First topic
        if not self.current_keywords:
            self.current_keywords = recent_keywords
            return True
        
        # Calculate overlap
        overlap = self._calculate_overlap(self.current_keywords, recent_keywords)
        
        # Less than 30% overlap = topic changed
        if overlap < 0.3:
            self.current_keywords = recent_keywords
            return True
        
        return False
    
    def _extract_keywords(self, conversation_history, window=5):
        """Extract keywords from recent messages"""
        recent = conversation_history[-window:]
        
        all_text = " ".join([
            msg['content'] for msg in recent 
            if msg['role'] != 'system'
        ])
        
        # Extract words
        words = re.findall(r'\b\w+\b', all_text.lower())
        
        # Filter common words
        common = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'is', 'are', 'was', 'were', 'been', 'be',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would'
        }
        
        keywords = [w for w in words if w not in common and len(w) > 3]
        
        # Top 5
        counts = Counter(keywords)
        return [word for word, _ in counts.most_common(5)]
    
    def _calculate_overlap(self, keywords1, keywords2):
        """Calculate keyword overlap percentage"""
        if not keywords1 or not keywords2:
            return 0.0
        
        set1 = set(keywords1)
        set2 = set(keywords2)
        
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        return len(intersection) / len(union) if union else 0.0