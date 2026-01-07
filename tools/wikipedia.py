import requests

def get_wikipedia_page(topic: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "titles": topic,
        "prop": "extracts",
        "explaintext": True,  # This gives you plain text, no HTML
        "exsectionformat": "plain"
    }
    
    response = requests.get("https://en.wikipedia.org/w/api.php", params=params)
    data = response.json()
    
    pages = data["query"]["pages"]
    page_id = list(pages.keys())[0]
    
    if page_id == "-1":
        return {"error": "Page not found"}
    
    return {
        "title": pages[page_id]["title"],
        "content": pages[page_id]["extract"]
    }

# For searching when you don't have the exact title:
"""# params = {
    "action": "opensearch",
    "search": "quantum entanglement",
    "limit": 5,
    "format": "json"
}
# Returns: [search_term, [titles], [descriptions], [urls]]"""

#For getting a summary instead of full page:
"""params = {
    "action": "query",
    "prop": "extracts",
    "exintro": True,  # Just the intro section
    "explaintext": True,
    "titles": "Consciousness"
}"""

#For getting related links:
"""params = {
    "action": "query",
    "titles": "Artificial intelligence",
    "prop": "links",
    "pllimit": 50,
    "format": "json"
}"""

#For Categories:
"""params = {
    "action": "query",
    "titles": "Neural network",
    "prop": "categories",
    "format": "json"
}"""

#headers = {"User-Agent": "Selene/1.0 (local AI research project)"}