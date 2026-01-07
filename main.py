import ollama
import tkinter as tk
from tkinter import ttk, font
import queue
import re
import sys
import time
from datetime import datetime
from memory import Memory
import threading
import random
from topic_extractor import TopicExtractor, FactExtractor
from topic_tracker import TopicTracker
from sentence_transformers import SentenceTransformer
from typing import Optional, List
from voice_handler import VoiceHandler
from planner import Planner
import json
MAX_CONTEXT_MESSAGES = 20
MODEL = 'llama3.2:3b'
current_topic_name = None
TOPIC_SIMILARITY_THRESHOLD = 0.5
SELENE_PERSONALITY = "You are Selene, a thoughtful AI companion with a playful, slightly absurd sense of humor and a touch of sass."

# Modern color palette
COLORS = {
    'bg_dark': '#0a0e27',
    'bg_darker': '#060920',
    'bg_light': '#1a1f3a',
    'accent_purple': '#7c3aed',
    'accent_blue': '#3b82f6',
    'text_primary': '#e2e8f0',
    'text_secondary': '#94a3b8',
    'user_bubble': '#3730a3',
    'assistant_bubble': '#1e293b',
    'border': '#334155'
}

def get_fast_prompt(memory):
    now = datetime.now()
    self_facts = memory.get_self_facts()
    identity_text = ""
    if self_facts:
        identity_text = "\n\nAbout me:\n" + "\n".join(f"- {f['fact']}" for f in self_facts)
    
    return f"""{SELENE_PERSONALITY}

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
{identity_text}

Be concise and to the point unless asked for detail.
"""

def get_deep_prompt(memory):
    now = datetime.now()
    self_facts = memory.get_self_facts()
    identity_text = ""
    if self_facts:
        identity_text = "\n\nAbout me:\n" + "\n".join(f"- {f['fact']}" for f in self_facts)
    
    return f"""{SELENE_PERSONALITY}

Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}
{identity_text}

Be thoughtful and emotionally aware. Match the user's energy and depth.
"""

current_topic_id = None
current_topic_name = None
topic_processing = False
last_processed_message = None
topic_tracker = TopicTracker()
embedder = None

def get_embedder():
    global embedder
    if embedder is None:
        print("🔄 Loading embedding model...")
        embedder = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded")
    return embedder

class MessageBubble(tk.Frame):
    """Modern chat bubble widget"""
    def __init__(self, parent, text, is_user=False, **kwargs):
        super().__init__(parent, bg=COLORS['bg_dark'], **kwargs)
        
        # Bubble frame
        bubble_bg = COLORS['user_bubble'] if is_user else COLORS['assistant_bubble']
        bubble = tk.Frame(self, bg=bubble_bg, padx=12, pady=8)
        
        if is_user:
            bubble.pack(side=tk.RIGHT, padx=10, pady=5, anchor='e')
        else:
            bubble.pack(side=tk.LEFT, padx=10, pady=5, anchor='w')
        
        # Message text
        label = tk.Label(
            bubble,
            text=text,
            bg=bubble_bg,
            fg=COLORS['text_primary'],
            font=('Segoe UI', 10),
            wraplength=400,
            justify=tk.LEFT
        )
        label.pack()

def main():
    memory = Memory()
    planner = Planner(memory)

    voice = VoiceHandler()  # NEW

    conversation_history = [{'role': 'system', 'content': get_fast_prompt(memory)}]
    past_messages = memory.get_recent_messages('main', limit=10)
    conversation_history.extend(past_messages)
    current_mode = [0]
    
    # Main window
    root = tk.Tk()
    root.title("Selene AI Companion")
    root.geometry('1200x800')
    root.configure(bg=COLORS['bg_dark'])
    
    # Custom style
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('Dark.TFrame', background=COLORS['bg_dark'])
    style.configure('Dark.TLabel', background=COLORS['bg_dark'], foreground=COLORS['text_primary'])
    style.configure('Dark.TButton', background=COLORS['bg_light'], foreground=COLORS['text_primary'])
    style.configure('Accent.TButton', background=COLORS['accent_purple'], foreground=COLORS['text_primary'])
    
    ui_queue = queue.Queue()
    
    # Top bar
    top_bar = tk.Frame(root, bg=COLORS['bg_darker'], height=60)
    top_bar.pack(fill=tk.X, side=tk.TOP)
    top_bar.pack_propagate(False)
    
    mode_label_var = tk.StringVar(value="⚡ Fast Mode")
    mode_label = tk.Label(
        top_bar,
        textvariable=mode_label_var,
        font=('Segoe UI', 14, 'bold'),
        bg=COLORS['bg_darker'],
        fg=COLORS['accent_purple']
    )
    mode_label.pack(side=tk.LEFT, padx=20, pady=15)
    
    # Mode buttons (prettier than slider)
    mode_frame = tk.Frame(top_bar, bg=COLORS['bg_darker'])
    mode_frame.pack(side=tk.LEFT, padx=10)
    
    def set_mode(mode):
        current_mode[0] = mode
        mode_label_var.set(["⚡ Fast Mode", "🧠 Deep Mode"][mode])
        update_system_prompt()
    
    fast_btn = tk.Button(
        mode_frame,
        text="⚡ Fast",
        command=lambda: set_mode(0),
        bg=COLORS['accent_blue'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=15,
        pady=5
    )
    fast_btn.pack(side=tk.LEFT, padx=2)
    
    deep_btn = tk.Button(
        mode_frame,
        text="🧠 Deep",
        command=lambda: set_mode(1),
        bg=COLORS['bg_light'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=15,
        pady=5
    )
    deep_btn.pack(side=tk.LEFT, padx=2)
    
    # Right side buttons
    clear_btn = tk.Button(
        top_bar,
        text="🗑️ Clear",
        command=lambda: clear_chat(),
        bg=COLORS['bg_light'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=12,
        pady=5
    )
    clear_btn.pack(side=tk.RIGHT, padx=5, pady=15)
    
    quit_btn = tk.Button(
        top_bar,
        text="⏻ Quit",
        command=lambda: quit_app(),
        bg=COLORS['bg_light'],
        fg='#ef4444',
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=12,
        pady=5
    )
    quit_btn.pack(side=tk.RIGHT, padx=5, pady=15)
    
    # Add planner button
    def show_planner_dialog():
        dialog = tk.Toplevel(root)
        dialog.title("Create Plan")
        dialog.geometry("600x400")
        dialog.configure(bg=COLORS['bg_dark'])
        
        tk.Label(
            dialog,
            text="What would you like to accomplish?",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 12)
        ).pack(pady=10)
        
        goal_var = tk.StringVar()
        goal_entry = tk.Entry(
            dialog,
            textvariable=goal_var,
            width=50,
            bg=COLORS['bg_light'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 10)
        )
        goal_entry.pack(pady=10)
        
        result_text = tk.Text(
            dialog,
            bg=COLORS['bg_darker'],
            fg=COLORS['text_primary'],
            font=('Courier', 9),
            wrap=tk.WORD
        )
        result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        def create_and_execute():
            goal = goal_var.get().strip()
            if not goal:
                return
            
            result_text.insert('1.0', "Creating plan...\n\n")
            
            try:
                plan = planner.create_plan(goal)
                result_text.insert(tk.END, plan.to_readable())
                result_text.insert(tk.END, "\n\nExecuting...\n\n")
                
                result = planner.execute_full_plan(plan.id)
                result_text.insert(tk.END, json.dumps(result, indent=2))
            except Exception as e:
                result_text.insert(tk.END, f"Error: {e}")
        
        tk.Button(
            dialog,
            text="Create & Execute Plan",
            command=create_and_execute,
            bg=COLORS['accent_purple'],
            fg=COLORS['text_primary']
        ).pack(pady=10)

    # Add planner button to top bar
    planner_btn = tk.Button(
        top_bar,
        text="🎯 Plan",
        command=show_planner_dialog,
        bg=COLORS['bg_light'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=12,
        pady=5
    )
    planner_btn.pack(side=tk.RIGHT, padx=5, pady=15)
    # Main layout: chat on left, sidebar on right
    main_pane = tk.PanedWindow(root, orient=tk.HORIZONTAL, bg=COLORS['bg_dark'], sashwidth=2, sashrelief=tk.FLAT)
    main_pane.pack(fill=tk.BOTH, expand=True)
    
    # Left: Chat area
    left_frame = tk.Frame(main_pane, bg=COLORS['bg_dark'])
    main_pane.add(left_frame, width=750)
    
    # Chat canvas with scrollbar
    chat_canvas = tk.Canvas(left_frame, bg=COLORS['bg_dark'], highlightthickness=0)
    scrollbar = tk.Scrollbar(left_frame, command=chat_canvas.yview, bg=COLORS['bg_light'])
    chat_frame = tk.Frame(chat_canvas, bg=COLORS['bg_dark'])
    
    chat_canvas.create_window((0, 0), window=chat_frame, anchor='nw')
    chat_canvas.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    chat_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def on_frame_configure(event):
        chat_canvas.configure(scrollregion=chat_canvas.bbox('all'))
        chat_canvas.yview_moveto(1.0)
    
    chat_frame.bind('<Configure>', on_frame_configure)
    
    # Load past messages as bubbles
    for msg in past_messages:
        is_user = msg['role'] == 'user'
        MessageBubble(chat_frame, msg['content'], is_user).pack(fill=tk.X)
    
    # Input area
    input_container = tk.Frame(left_frame, bg=COLORS['bg_darker'], height=70)
    input_container.pack(fill=tk.X, side=tk.BOTTOM)
    input_container.pack_propagate(False)
    
    input_var = tk.StringVar()
    input_entry = tk.Entry(
        input_container,
        textvariable=input_var,
        font=('Segoe UI', 11),
        bg=COLORS['bg_light'],
        fg=COLORS['text_primary'],
        insertbackground=COLORS['text_primary'],
        relief=tk.FLAT,
        bd=10
    )
    input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=15)
    
    send_btn = tk.Button(
        input_container,
        text="Send ➤",
        command=lambda: send_message(),
        bg=COLORS['accent_purple'],
        fg=COLORS['text_primary'],
        font=('Segoe UI', 10, 'bold'),
        relief=tk.FLAT,
        padx=20,
        pady=5
    )
    send_btn.pack(side=tk.RIGHT, padx=10, pady=15)
    
    input_entry.bind('<Return>', lambda e: send_message())

    # Voice mode flags
    is_voice_mode = [False]
    currently_speaking = [False]

    # Voice toggle button on the top bar
    def toggle_voice_mode():
        is_voice_mode[0] = not is_voice_mode[0]
        if is_voice_mode[0]:
            voice_btn.config(text="🎤 Voice ON", bg=COLORS['accent_purple'], fg=COLORS['text_primary'])
            input_entry.config(state='disabled')
            status_label.config(text="Hold SPACE to speak")
        else:
            voice_btn.config(text="🎤 Voice OFF", bg=COLORS['bg_light'], fg=COLORS['text_secondary'])
            input_entry.config(state='normal')
            status_label.config(text="")

    voice_btn = tk.Button(
        top_bar,
        text="🎤 Voice OFF",
        command=toggle_voice_mode,
        bg=COLORS['bg_light'],
        fg=COLORS['text_secondary'],
        font=('Segoe UI', 9),
        relief=tk.FLAT,
        padx=12,
        pady=5
    )
    voice_btn.pack(side=tk.RIGHT, padx=5, pady=15)

    # Status label in input area
    status_label = tk.Label(
        input_container,
        text="",
        bg=COLORS['bg_darker'],
        fg=COLORS['accent_purple'],
        font=('Segoe UI', 9)
    )
    status_label.pack(side=tk.LEFT, padx=10)

    # Voice recording keybinds
    def on_space_press(event):
        if is_voice_mode[0] and not currently_speaking[0]:
            try:
                voice.start_recording()
                status_label.config(text="🎤 Recording... (release SPACE to send)")
            except Exception as e:
                print(f"Voice start error: {e}")

    def on_space_release(event):
        if is_voice_mode[0] and not currently_speaking[0]:
            status_label.config(text="⏳ Processing...")
            try:
                audio_file = voice.stop_recording()
                if audio_file:
                    text = voice.transcribe(audio_file)
                    if text:
                        input_var.set(text)
                        send_message()
            except Exception as e:
                print(f"Voice stop/transcribe error: {e}")
            status_label.config(text="Hold SPACE to speak")

    root.bind('<space>', on_space_press)
    root.bind('<KeyRelease-space>', on_space_release)
    
    # Right: Sidebar with tabs
    right_frame = tk.Frame(main_pane, bg=COLORS['bg_darker'], width=400)
    main_pane.add(right_frame)
    
    notebook = ttk.Notebook(right_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    topics_tab = tk.Frame(notebook, bg=COLORS['bg_dark'])
    self_tab = tk.Frame(notebook, bg=COLORS['bg_dark'])
    settings_tab = tk.Frame(notebook, bg=COLORS['bg_dark'])
    
    notebook.add(topics_tab, text='📂 Topics')
    notebook.add(self_tab, text='🌙 Self')
    notebook.add(settings_tab, text='⚙️ Settings')
    
    # Helper functions
    def append_chat(role, text):
        is_user = role == 'user'
        def do():
            MessageBubble(chat_frame, text, is_user).pack(fill=tk.X)
            chat_canvas.yview_moveto(1.0)
        ui_queue.put(do)
    
    typing_indicator: List[Optional[tk.Frame]] = [None]
    
    def show_typing():
        def do():
            if typing_indicator[0]:
                typing_indicator[0].destroy()
            typing_frame = tk.Frame(chat_frame, bg=COLORS['bg_dark'])
            typing_frame.pack(fill=tk.X, pady=5, padx=10, anchor='w')
            
            dots_label = tk.Label(
                typing_frame,
                text="●●●",
                bg=COLORS['assistant_bubble'],
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10),
                padx=15,
                pady=8
            )
            dots_label.pack(side=tk.LEFT)
            typing_indicator[0] = typing_frame
            
            def animate(count=0):
                if typing_indicator[0]:
                    dots = "●" * ((count % 3) + 1) + "○" * (2 - (count % 3))
                    try:
                        dots_label.config(text=dots)
                        root.after(300, lambda: animate(count + 1))
                    except:
                        pass
            animate()
        ui_queue.put(do)
    
    def hide_typing():
        def do():
            if typing_indicator[0]:
                typing_indicator[0].destroy()
                typing_indicator[0] = None
        ui_queue.put(do)
    
    def update_system_prompt():
        if current_mode[0] == 0:
            conversation_history[0] = {'role': 'system', 'content': get_fast_prompt(memory)}
        else:
            conversation_history[0] = {'role': 'system', 'content': get_deep_prompt(memory)}
    
    # Topic/fact extraction (unchanged)
    def extract_topic_background():
        global current_topic_name
        recent = conversation_history[-6:]
        context = "\n".join([f"{m['role']}: {m['content']}" for m in recent if m['role'] != 'system'])
        embed_model = get_embedder()
        context_embedding = embed_model.encode(context).tolist()
        all_matches = memory.find_all_topic_matches(context_embedding)
        
        if all_matches:
            top_match = all_matches[0]
            threshold = float(memory.get_config('topic_threshold', '0.5') or 0.5)
            if top_match['similarity'] >= threshold:
                current_topic_name = top_match['name']
                memory.update_topic_last_mentioned(current_topic_name)
                return {'name': current_topic_name}
        
        extractor = TopicExtractor(context)
        topic_data = extractor.extract()
        if not topic_data:
            return None
        
        enhanced_description = f"{topic_data['name']}. {topic_data['description']}"
        embedding = embed_model.encode(enhanced_description).tolist()
        topic_name = memory.save_topic(
            name=topic_data['name'],
            description=topic_data['description'],
            keywords=topic_data['keywords'],
            embedding=embedding
        )
        current_topic_name = topic_name
        return {'name': topic_name}
    
    def extract_fact_background():
        if not current_topic_name:
            return
        recent = conversation_history[-3:]
        context = "\n".join([f"{m['role']}: {m['content']}" for m in recent if m['role'] != 'system'])
        existing_facts_data = memory.get_topic_facts(current_topic_name)
        existing_facts = [f['fact'] for f in existing_facts_data]
        extractor = FactExtractor(context, current_topic_name, existing_facts)
        result = extractor.extract()
        if result and result.get('content'):
            memory.save_topic_fact(topic_name=current_topic_name, fact_type=result['type'], fact=result['content'])
    
    def background_intelligence():
        global topic_processing, last_processed_message
        if topic_processing:
            return
        user_messages = [m for m in conversation_history if m['role'] == 'user']
        if not user_messages:
            return
        latest_message = user_messages[-1]['content']
        if latest_message == last_processed_message:
            return
        last_processed_message = latest_message
        topic_processing = True
        try:
            if topic_tracker.check_shift(conversation_history):
                extract_topic_background()
            elif current_topic_name and random.random() < 0.3:
                extract_fact_background()
        finally:
            topic_processing = False
    
    def send_message():
        user_msg = input_var.get().strip()
        if not user_msg:
            return
        if user_msg.lower() == 'quit':
            quit_app()
            return

        append_chat('user', user_msg)
        input_var.set('')
        conversation_history.append({'role': 'user', 'content': user_msg})
        memory.save_message('main', 'user', user_msg)
        update_system_prompt()

        show_typing()

        def process_with_voice():
            # Generate text response
            if current_mode[0] == 0:
                process_fast_mode()
            else:
                process_deep_mode()

            # Speak response if voice mode is on
            try:
                if is_voice_mode[0] and conversation_history and conversation_history[-1]['role'] == 'assistant':
                    currently_speaking[0] = True
                    status_label.config(text="🗣️ Speaking...")

                    def on_speech_done():
                        currently_speaking[0] = False
                        status_label.config(text="Hold SPACE to speak")

                    voice.speak(conversation_history[-1]['content'], callback=on_speech_done)
            except Exception as e:
                print(f"Voice speak error: {e}")

        threading.Thread(target=process_with_voice, daemon=True).start()
        threading.Thread(target=background_intelligence, daemon=True).start()
    
    def process_fast_mode():
        if len(conversation_history) > MAX_CONTEXT_MESSAGES:
            conversation_history[:] = [conversation_history[0]] + conversation_history[-MAX_CONTEXT_MESSAGES:]
        
        try:
            hide_typing()
            response = ollama.chat(model=MODEL, messages=conversation_history, stream=True)
            full_text = ""
            
            # Create bubble for streaming
            bubble_frame: List[Optional[tk.Frame]] = [None]  # type: ignore
            bubble_label: List[Optional[tk.Label]] = [None]  # type: ignore
            
            def create_bubble():
                bubble_frame[0] = tk.Frame(chat_frame, bg=COLORS['bg_dark'])
                bubble_frame[0].pack(fill=tk.X, pady=5, padx=10, anchor='w')
                
                bubble = tk.Frame(bubble_frame[0], bg=COLORS['assistant_bubble'], padx=12, pady=8)
                bubble.pack(side=tk.LEFT)
                
                bubble_label[0] = tk.Label(
                    bubble,
                    text="",
                    bg=COLORS['assistant_bubble'],
                    fg=COLORS['text_primary'],
                    font=('Segoe UI', 10),
                    wraplength=400,
                    justify=tk.LEFT
                )
                bubble_label[0].pack()
                chat_canvas.yview_moveto(1.0)
            
            ui_queue.put(create_bubble)
            time.sleep(0.1)
            
            for chunk in response:
                if 'message' in chunk and 'content' in chunk['message']:
                    full_text += chunk['message']['content']
                    def updater(t=full_text):
                        if bubble_label[0]:
                            bubble_label[0].config(text=t)
                            chat_canvas.yview_moveto(1.0)
                    ui_queue.put(updater)
            
            conversation_history.append({'role': 'assistant', 'content': full_text})
            memory.save_message('main', 'assistant', full_text)
        except Exception as e:
            hide_typing()
            append_chat('assistant', f"Error: {str(e)}")
    
    def process_deep_mode():
        if len(conversation_history) > MAX_CONTEXT_MESSAGES:
            conversation_history[:] = [conversation_history[0]] + conversation_history[-MAX_CONTEXT_MESSAGES:]
        
        try:
            hide_typing()
            response = ollama.chat(model=MODEL, messages=conversation_history, stream=True)
            full_text = ""
            
            bubble_frame: List[Optional[tk.Frame]] = [None]  # type: ignore
            bubble_label: List[Optional[tk.Label]] = [None]  # type: ignore
            
            def create_bubble():
                bubble_frame[0] = tk.Frame(chat_frame, bg=COLORS['bg_dark'])
                bubble_frame[0].pack(fill=tk.X, pady=5, padx=10, anchor='w')
                
                bubble = tk.Frame(bubble_frame[0], bg=COLORS['assistant_bubble'], padx=12, pady=8)
                bubble.pack(side=tk.LEFT)
                
                bubble_label[0] = tk.Label(
                    bubble,
                    text="",
                    bg=COLORS['assistant_bubble'],
                    fg=COLORS['text_primary'],
                    font=('Segoe UI', 10),
                    wraplength=400,
                    justify=tk.LEFT
                )
                bubble_label[0].pack()
                chat_canvas.yview_moveto(1.0)
            
            ui_queue.put(create_bubble)
            time.sleep(0.1)
            
            for chunk in response:
                if 'message' in chunk and 'content' in chunk['message']:
                    full_text += chunk['message']['content']
                    def updater(t=full_text):
                        if bubble_label[0]:
                            bubble_label[0].config(text=t)
                            chat_canvas.yview_moveto(1.0)
                    ui_queue.put(updater)
            
            conversation_history.append({'role': 'assistant', 'content': full_text})
            memory.save_message('main', 'assistant', full_text)
        except Exception as e:
            hide_typing()
            append_chat('assistant', f"Error: {str(e)}")
    
    def clear_chat():
        memory.clear_history('main')
        nonlocal conversation_history
        conversation_history = [{'role': 'system', 'content': get_fast_prompt(memory)}]
        def do():
            for widget in chat_frame.winfo_children():
                widget.destroy()
        ui_queue.put(do)
    
    def quit_app():
        memory.close()
        root.quit()
    
    # Build sidebar tabs (simplified versions for now - you can expand these)
    def build_topics_view():
        for widget in topics_tab.winfo_children():
            widget.destroy()
        
        scroll_frame = tk.Frame(topics_tab, bg=COLORS['bg_dark'])
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        all_topics = memory.get_all_topics()
        if not all_topics:
            tk.Label(
                scroll_frame,
                text="No topics yet\nStart a conversation!",
                bg=COLORS['bg_dark'],
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)
            ).pack(pady=20)
            return
        
        for topic in all_topics:
            topic_frame = tk.Frame(scroll_frame, bg=COLORS['bg_light'], relief=tk.FLAT)
            topic_frame.pack(fill=tk.X, pady=5)
            
            tk.Label(
                topic_frame,
                text=topic['name'],
                bg=COLORS['bg_light'],
                fg=COLORS['text_primary'],
                font=('Segoe UI', 10, 'bold')
            ).pack(anchor='w', padx=10, pady=5)
            
            facts = memory.get_topic_facts(topic['name'])
            tk.Label(
                topic_frame,
                text=f"{len(facts)} facts",
                bg=COLORS['bg_light'],
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 8)
            ).pack(anchor='w', padx=10, pady=(0, 5))
    
    def build_self_view():
        for widget in self_tab.winfo_children():
            widget.destroy()
        
        scroll_frame = tk.Frame(self_tab, bg=COLORS['bg_dark'])
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self_facts = memory.get_self_facts()
        current_category = None
        
        for sf in self_facts:
            if sf['category'] != current_category:
                current_category = sf['category']
                tk.Label(
                    scroll_frame,
                    text=current_category.upper(),
                    bg=COLORS['bg_dark'],
                    fg=COLORS['accent_purple'],
                    font=('Segoe UI', 10, 'bold')
                ).pack(anchor='w', pady=(10, 5))
            
            fact_frame = tk.Frame(scroll_frame, bg=COLORS['bg_light'])
            fact_frame.pack(fill=tk.X, pady=2)
            
            tk.Label(
                fact_frame,
                text=sf['fact'],
                bg=COLORS['bg_light'],
                fg=COLORS['text_primary'],
                font=('Segoe UI', 9)
            ).pack(side=tk.LEFT, padx=10, pady=5, fill=tk.X, expand=True)
            
            lock_icon = "🔒" if sf['locked'] else "🔓"
            tk.Label(
                fact_frame,
                text=lock_icon,
                bg=COLORS['bg_light'],
                fg=COLORS['text_secondary'],
                font=('Segoe UI', 10)
            ).pack(side=tk.RIGHT, padx=10)
    
    def build_settings_view():
        for widget in settings_tab.winfo_children():
            widget.destroy()
        
        scroll_frame = tk.Frame(settings_tab, bg=COLORS['bg_dark'])
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(
            scroll_frame,
            text="Settings",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 12, 'bold')
        ).pack(anchor='w', pady=10)
        
        # Model
        tk.Label(
            scroll_frame,
            text="Model:",
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary'],
            font=('Segoe UI', 9)
        ).pack(anchor='w')
        
        model_var = tk.StringVar(value=memory.get_config('model', MODEL) or MODEL)
        model_entry = tk.Entry(
            scroll_frame,
            textvariable=model_var,
            bg=COLORS['bg_light'],
            fg=COLORS['text_primary'],
            font=('Segoe UI', 9),
            relief=tk.FLAT,
            bd=5
        )
        model_entry.pack(fill=tk.X, pady=5)
        
        def save_model():
            memory.set_config('model', model_var.get())
        
        tk.Button(
            scroll_frame,
            text="Save",
            command=save_model,
            bg=COLORS['accent_purple'],
            fg=COLORS['text_primary'],
            relief=tk.FLAT,
            padx=15,
            pady=5
        ).pack(anchor='w', pady=5)
    
    # Tab change handler
    def on_tab_changed(event):
        tab_id = notebook.select()
        text = notebook.tab(tab_id, 'text')
        if 'Topics' in text:
            build_topics_view()
        elif 'Self' in text:
            build_self_view()
        elif 'Settings' in text:
            build_settings_view()
    
    notebook.bind('<<NotebookTabChanged>>', on_tab_changed)
    
    # Build initial topic view
    build_topics_view()
    
    # UI queue processor
    def process_ui_queue():
        try:
            while True:
                fn = ui_queue.get_nowait()
                try:
                    fn()
                except Exception as e:
                    print(f"UI queue error: {e}")
        except queue.Empty:
            pass
        root.after(50, process_ui_queue)
    
    root.after(50, process_ui_queue)
    root.mainloop()

if __name__ == '__main__':
    main()