# INFO: requires "playwright install"

from lawResearchAI import lawResearchAI
import requests
from bs4 import BeautifulSoup
import re
import time
from openai import OpenAI
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import sys
import webbrowser

# Globale Variablen
status = 0 # 0 = Start-Screen, 1 = Recherche wird durchgeführt, 2 = Suchbegriffe werden optimiert
frameElements = {
    "research_project":{},
    "short_answer":{},
    "settings":{},
}
stopSignal = threading.Event()
scriptDir = os.path.dirname(os.path.abspath(__file__))
cipher_suite = Fernet(b"X-V7P7Khk3Ke0mvWpe2-jKwWCSBZ5BKEVj6Og-FnwqA=")

# Universitäten aus JSON-Datei laden
unis_file = os.path.join(scriptDir, "Ext", "unis.json")

if os.path.exists(unis_file):
    with open(unis_file, "r") as file:
        unis_data = json.load(file)
    unis = {key: value for key, value in unis_data.items()}
else:
    unis = None

# Projektdatei erstellen oder laden
projects_file = os.path.join(scriptDir, "projects.json")
if not os.path.exists(projects_file):
    with open(projects_file, "w") as file:
        json.dump({}, file)

# Zuletzt ausgewählte Uni speichern und laden
last_uni_file = os.path.join(scriptDir, "last_uni.json")
def save_last_uni(uni):
    if uni in unis:
        with open(last_uni_file, "w", encoding="utf-8") as file:
            json.dump({"last_uni": uni}, file)

def load_last_uni():
    if os.path.exists(last_uni_file):
        with open(last_uni_file, "r", encoding="utf-8") as file:
            return unis[json.load(file).get("last_uni", "")]
    return ""

def save_settings():
    env_vars = {}
    env_vars["API_URL"] = frameElements["settings"]["api_url_entry"].get().strip()
    env_vars["API_KEY"] = frameElements["settings"]["api_key_entry"].get().strip()
    env_vars["API_MODEL"] = frameElements["settings"]["api_model_entry"].get().strip()
    env_vars["PROXY_URL"] = frameElements["settings"]["proxy_entry"].get().strip()
    
    env_vars["POPPLER_PATH"] = frameElements["settings"]["poppler_path_entry"].get().strip()
    env_vars["TESSERACT_PATH"] = frameElements["settings"]["tesseract_path_entry"].get().strip()
    
    # API-Key verschlüsseln
    env_vars["API_KEY"] = cipher_suite.encrypt(env_vars["API_KEY"].encode())
    
    with open(os.path.join(scriptDir, ".env"), "w") as env_file:
        for key, value in env_vars.items():
            env_file.write(f"{key}={value}\n")

# Hauptfenster erstellen
root = tk.Tk()
root.title("Juristische Recherche (BETA)")

# Umgebungsvariablen laden und als tk Variablen initialisieren
load_dotenv()
script_settings = {
    "API_KEY":os.getenv("API_KEY"),
    "API_URL":os.getenv("API_URL", "https://api.openai.com/v1"),
    "API_MODEL":os.getenv("API_MODEL", "gpt-4o"),
    "PROXY_URL":os.getenv("PROXY_URL"),
    "POPPLER_PATH":os.getenv("POPPLER_PATH"),
    "TESSERACT_PATH":os.getenv("TESSERACT_PATH"),
}

# Portale
portals = {"Beck-Online.de":"beck-online","Juris.de":"juris"}

if script_settings["POPPLER_PATH"] and script_settings["TESSERACT_PATH"]:
    portals["Google Suche (PDF)"] = "google-search"

# API-Key vorbearbeiten
if (script_settings["API_KEY"]):
    # Mit RegEx das 'b' und die umgebenden Anführungszeichen entfernen
    cleaned_key = re.sub(r"^b'(.*)'$", r"\1", script_settings["API_KEY"])
    
    if cleaned_key:
        script_settings["API_KEY"] = cleaned_key.encode("utf-8")
    
    script_settings["API_KEY"] = cipher_suite.decrypt(script_settings["API_KEY"]).decode("utf-8")

api_url_var = tk.StringVar(value=script_settings["API_URL"])
api_key_var = tk.StringVar(value=script_settings["API_KEY"])
api_model_var = tk.StringVar(value=script_settings["API_MODEL"])
proxy_var = tk.StringVar(value=script_settings["PROXY_URL"])
poppler_path_var = tk.StringVar(value=script_settings["POPPLER_PATH"])
tesseract_path_var = tk.StringVar(value=script_settings["TESSERACT_PATH"])

frameElements["research_project"]["resume_var"] = tk.BooleanVar(value=False)

project_name_var = tk.StringVar()
limit_var = tk.IntVar(value=10)
uni_var = tk.StringVar()

# Hilfsfunktion zum Escapen
def escape_filename(value):
    # Entfernt alle unerlaubten Zeichen (und auch Leerzeichen) durch einen regulären Ausdruck
    # Erlaubte Zeichen sind Buchstaben, Zahlen, Bindestriche und Unterstriche
    safe_string = re.sub(r'[\/:*?"<>|\s]', '_', value)
    
    # Optionale Anpassungen, um sicherzustellen, dass der Dateiname nicht mit Punkt oder Leerzeichen beginnt/endet
    safe_string = safe_string.strip().strip('.').strip()

    max_length = 255
    safe_string = safe_string[:max_length]

    # Rückgabe des umgewandelten, sicheren Strings
    return safe_string 

# Projekte laden
def load_projects():
    with open(projects_file, "r") as file:
        return json.load(file)

def save_projects(projects):
    with open(projects_file, "w") as file:
        json.dump(projects, file, indent=4)

projects = load_projects()

# Funktion zum Abrufen des zugehörigen Keys aus dem gespeicherten Value
def get_key_from_value(value, haystack):
    for key, val in haystack.items():
        if val == value:
            return key
    return None  # Wenn kein passender Key gefunden wird

# Funktion, um Projektdaten in das Formular einzufügen
def load_project_data(*args):
    global buttons
    
    project_name = project_name_var.get()
    
    if project_name in projects:
        data = projects[project_name]
        frameElements["research_project"]["search_entry"].delete("1.0", tk.END)
        frameElements["research_project"]["search_entry"].insert("1.0", data.get("search_query", ""))
        frameElements["research_project"]["research_text"].delete("1.0", tk.END)
        frameElements["research_project"]["research_text"].insert("1.0", data.get("research_topic", ""))
        frameElements["research_project"]["outline_text"].delete("1.0", tk.END)
        frameElements["research_project"]["outline_text"].insert("1.0", data.get("outline", ""))
        frameElements["research_project"]["uni_dropdown"].set(unis[data.get("university", "")])
        
        for portal, var in frameElements["research_project"]["portal_checkboxes"].items():
            var.set(portal in data.get("selected_portals", []))
        frameElements["research_project"]["limit_var"].set(data.get("limit", 10))
        frameElements["research_project"]["save_location_var"].set(data.get("save_location", ""))

def delete_project():
    project_name = project_name_var.get()
    if project_name in projects:
        # Übersicht aktualisieren
        del projects[project_name]
        save_projects(projects)
        
        # Projektstand löschen
        project_path = os.path.join(scriptDir, f"project{escape_filename(project_name)}.json")
        
        if os.path.exists(project_path):
            os.remove(project_path)
        
        # Layout aktualisieren
        frameElements["research_project"]["project_dropdown"]["values"] = list(projects.keys())
        project_name_var.set("")
        frameElements["research_project"]["search_entry"].delete("1.0", tk.END)
        frameElements["research_project"]["research_text"].delete("1.0", tk.END)
        frameElements["research_project"]["outline_text"].delete("1.0", tk.END)
        frameElements["research_project"]["save_location_var"].set("")
        
# Funktion, um Speicherort auszuwählen
def select_save_location():
    folder_selected = filedialog.askdirectory(title="Speicherort auswählen")
    if folder_selected:
        frameElements["research_project"]["save_location_var"].set(folder_selected)
        
def convert_text_to_json(text):
    text = text.strip()  # Text aus dem Widget holen und Leerzeichen entfernen
    lines = text.split("\n")  # Text in Zeilen aufteilen
    json_array = [line for line in lines if line]  # Leere Zeilen ignorieren
    return json_array

# Funktion, die beim Drücken des Suchbuttons ausgeführt wird
def search_action():
    global status, buttons, stopSignal
    
    if (status == 0):
        # Formularfelder prüfen
        search_query = frameElements["research_project"]["search_entry"].get("1.0", tk.END).strip()
        selected_portals = [portal for portal, var in frameElements["research_project"]["portal_checkboxes"].items() if var.get()] #[var.get() for portal, var in checkbox_vars.items() if var.get()] #selected_portals = [portal for portal, var in checkbox_vars.items() if var.get()]
        selected_uni = get_key_from_value(frameElements["research_project"]["uni_dropdown"].get(), unis)
        limit = int(frameElements["research_project"]["limit_var"].get())
        save_location = frameElements["research_project"]["save_location_var"].get()
        
        if (search_query and selected_portals and selected_uni and limit > 0 and save_location):
            # Starten und Buttons ändern
            frameElements["research_project"]["research_button"].configure(text="Recherche stoppen")
            frameElements["research_project"]["optimize_button"].configure(state="disabled")
            
            # Ladeanzeige anzeigen
            frameElements["research_project"]["progress_bar"].grid()
            frameElements["research_project"]["progress_var"].set(0)
            frameElements["research_project"]["progress_label"].config(text="Recherche läuft...")
            root.update()
            
            status = 1
            
            thread = threading.Thread(target=search)
            thread.start()
        else:
            messagebox.showerror("Fehler", "Es wurden nicht alle benötigten Felder ausgefüllt.")
    elif (status == 1):
        # Recherche beenden
        frameElements["research_project"]["research_button"].configure(text="Recherche starten")
        frameElements["research_project"]["optimize_button"].configure(state="normal")
        frameElements["research_project"]["progress_label"].config(text="")
        frameElements["research_project"]["progress_bar"].stop()
        frameElements["research_project"]["progress_bar"].grid_remove()
        
        status = 0
        
        # Stopp-Signal senden, führt auch zur Speicherung
        stopSignal.set()

def search():
    global stopSignal
    
    search_query = frameElements["research_project"]["search_entry"].get("1.0", tk.END).strip()
    research_topic = frameElements["research_project"]["research_text"].get("1.0", tk.END).strip()
    outline = frameElements["research_project"]["outline_text"].get("1.0", tk.END).strip()
    selected_portals = [portal for portal, var in frameElements["research_project"]["portal_checkboxes"].items() if var.get()] #[var.get() for portal, var in checkbox_vars.items() if var.get()] #selected_portals = [portal for portal, var in checkbox_vars.items() if var.get()]
    selected_uni = get_key_from_value(frameElements["research_project"]["uni_dropdown"].get(), unis)
    limit = frameElements["research_project"]["limit_var"].get()
    save_location = frameElements["research_project"]["save_location_var"].get()
    
    # Stopp-Signal zurücksetzen
    stopSignal.clear()
    
    # Projekt speichern
    project_name = project_name_var.get()
    if project_name:
        projects[project_name] = {
            "search_query": search_query,
            "research_topic": research_topic,
            "outline": outline,
            "selected_portals": selected_portals,
            "university": selected_uni,
            "limit": limit,
            "save_location": save_location,
        }
        save_projects(projects)
        frameElements["research_project"]["project_dropdown"]["values"] = list(projects.keys())
        
    save_last_uni(frameElements["research_project"]["uni_dropdown"].get())
    
    # Portale nach Speicherung des Projekts den Werten zuordnen
    selected_portals = [portals.get(portal, portal) for portal in selected_portals]
    
    # Recherche durchführen (wird ggf. automatisch fortgesetzt)
    try:
        # Vorbereiten
        research_topic = convert_text_to_json(research_topic)
        outline = convert_text_to_json(outline)
        search_query = convert_text_to_json(search_query)
        resumeSearch = True if frameElements["research_project"]["resume_var"].get() == 1 else False
       
        # Neubeginn-Checkbox zurücksetzen
        frameElements["research_project"]["resume_var"].set(False)
       
        uniAccess = []
       
        file_name = os.path.join(scriptDir, "Ext", f"{selected_uni}.json") # Pfad zur Datei basierend auf der ausgewählten Uni
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                uniAccess = json.load(file)  # JSON-Daten laden
       
        juris_autologin_url = uniAccess.get("__AUTOLOGIN__", {}).get("juris", {}).get("url")
        
        research = lawResearchAI(uniAccess, limit, search_action_callback, api_url_var.get(), api_key_var.get(), api_model_var.get(), proxy_var.get(), script_settings["TESSERACT_PATH"], script_settings["POPPLER_PATH"])
        research.research(save_location, project_name, research_topic, outline, search_query, selected_portals, juris_autologin_url, stopSignal, resumeSearch)
    
    except ValueError as e:
        messagebox.showerror("Fehler", f"Fehler: {e}")

# Callback-Funktion ab Durchführung der Recherche, die die Statusleiste aktualisiert
def search_action_callback(percent, status_text):
    global stopSignal
    
    if stopSignal.is_set():
        # Callback ignorieren, wenn Projekt gerade beendet wird, um den Nutzer nicht zu verwirren
        return None
    
    if (percent >= 0):
        frameElements["research_project"]["progress_var"].set(percent)
    
    frameElements["research_project"]["progress_label"].config(text=status_text)
    root.update()

# Callback-Funktion ab Durchführung der Kurzantwort, die Status/Antworttext aktualisiert
def shortanswer_action_callback(percent, status_text):
    frameElements["short_answer"]["result_box"].config(state="normal")
    
    frameElements["short_answer"]["result_box"].delete("1.0",tk.END)
    frameElements["short_answer"]["result_box"].insert(tk.END, status_text)
    
    frameElements["short_answer"]["result_box"].config(state="disabled")
    root.update()

# Funktion, die beim Drücken des Optimieren-Buttons ausgeführt wird
def optimize_keywords():
    # Ladeanzeige anzeigen
    frameElements["research_project"]["progress_label"].config(text="Optimierung läuft...")
    frameElements["research_project"]["progress_var"].set(0)
    root.update()
    
    selected_portals = [portal for portal, var in frameElements["research_project"]["portal_checkboxes"].items() if var.get()] #[var.get() for portal, var in checkbox_vars.items() if var.get()] #selected_portals = [portal for portal, var in checkbox_vars.items() if var.get()]
    selected_portals = [portals.get(portal, portal) for portal in selected_portals]
    
    selected_uni = frameElements["research_project"]["uni_dropdown"].get()
    
    search_query = frameElements["research_project"]["search_entry"].get("1.0", tk.END).strip()
    
    uniAccess = []
    
    file_name = os.path.join(scriptDir, "Ext", f"{selected_uni}.json") # Pfad zur Datei basierend auf der ausgewählten Uni
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as file:
            uniAccess = json.load(file)  # JSON-Daten laden
    
    # Suchbegriffe optimieren
    research = lawResearchAI(uniAccess, 30, search_action_callback, api_url_var.get(), api_key_var.get(), api_model_var.get(), proxy_var.get())
    optimized = research.optimizeKeywords(search_query, selected_portals)
    
    if optimized:
        frameElements["research_project"]["search_entry"].delete("1.0", tk.END)
        
        for line in optimized:
            frameElements["research_project"]["search_entry"].insert(tk.END, line.strip() + "\n")
    
    # Ladeanzeige ausblenden
    frameElements["research_project"]["progress_label"].config(text="")
    frameElements["research_project"]["progress_bar"].stop()
    frameElements["research_project"]["progress_bar"].grid_forget()

# Universitäten aktualisieren
def update_universities():
    download_folder = os.path.join(scriptDir, "Ext")

    # Ladeanzeige anzeigen
    frameElements["research_project"]["progress_label"].config(text="Dateien werden aktualisiert . . .")
    frameElements["research_project"]["progress_var"].set(0)
    root.update()

    # Erstelle den Ordner, falls er nicht existiert
    os.makedirs(download_folder, exist_ok=True)
    
    # URLs
    portals_url = "https://jura-recherche.de/export/portals.json"
    unis_url = "https://jura-recherche.de/export/unis.json"

    # 1. Lade portals.json und speichere sie
    portals_file = os.path.join(download_folder, "portals.json")
    response = requests.get(portals_url)
    if response.status_code == 200:
        with open(portals_file, "wb", encoding="utf-8") as f:
            f.write(response.content)
    else:
        messagebox.showerror("Fehler", f"Versuche es später erneut. Fehler beim Download der Datei: {portals_url}")

    # 2. Lade unis.json und speichere sie
    unis_file = os.path.join(download_folder, "unis.json")
    response = requests.get(unis_url)
    if response.status_code == 200:
        with open(unis_file, "wb", encoding="utf-8") as f:
            f.write(response.content)
    else:
        messagebox.showerror("Fehler", f"Versuche es später erneut. Fehler beim Download der Datei: {unis_url}")

    # 3. Lese unis.json aus und lade für jeden Key die key.json
    with open(unis_file, "r", encoding="utf-8") as f:
        unis = json.load(f)

    # Überprüfe und lade key.json für jeden Key
    for key in unis.keys():
        key_url = f"https://jura-recherche.de/export/{key}.json"
        key_file = os.path.join(download_folder, f"{key}.json")
        response = requests.get(key_url)
        if response.status_code == 200:
            with open(key_file, 'wb') as f:
                f.write(response.content)
        else:
            messagebox.showerror("Fehler", f"Versuche es später erneut. Fehler beim Download der Datei: {key_url}")
    
    # Ladeanzeige ausblenden
    frameElements["research_project"]["progress_label"].config(text="")
    frameElements["research_project"]["progress_bar"].stop()
    frameElements["research_project"]["progress_bar"].grid_forget()

def short_answer():
    selected_portal = frameElements["short_answer"]["portal_dropdown"].get()
    selected_uni = frameElements["short_answer"]["uni_dropdown"].get()
    query = frameElements["short_answer"]["question_entry"].get("1.0", tk.END).strip()
    
    if (portals[selected_portal] and selected_uni and query):
        uniAccess = []
        selected_portal = portals[selected_portal]
        
        file_name = os.path.join(scriptDir, "Ext", f"{selected_uni}.json") # Pfad zur Datei basierend auf der ausgewählten Uni
        if os.path.exists(file_name):
            with open(file_name, "r", encoding="utf-8") as file:
                uniAccess = json.load(file)  # JSON-Daten laden
        
        # Kurzantwort generieren
        research = lawResearchAI(uniAccess, 30, shortanswer_action_callback, api_url_var.get(), api_key_var.get(), api_model_var.get(), proxy_var.get(), script_settings["TESSERACT_PATH"], script_settings["POPPLER_PATH"])
        answer = research.shortAnswer(query, selected_portal)
        
        shortanswer_action_callback(-1, answer)
    else:
        messagebox.showerror("Fehler", "Es wurden nicht alle benötigten Felder ausgefüllt.")

# Projektmanagement Tab

def create_research_project_frame():
    research_project_frame = ttk.Frame(root)

    # Projektmanagement
    project_frame = ttk.LabelFrame(research_project_frame, text="Projektmanagement")
    project_frame.pack(fill="x", padx=10, pady=10)

    project_name_label = ttk.Label(project_frame, text="Projektname:")
    project_name_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    project_dropdown = ttk.Combobox(project_frame, textvariable=project_name_var, values=list(projects.keys()), state="normal")
    project_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    project_dropdown.bind("<<ComboboxSelected>>", load_project_data)
    frameElements["research_project"]["project_dropdown"] = project_dropdown
    
    # Zusätzlich ein Ereignis für die Validierung, um manuelle Eingaben zu erkennen
    project_dropdown.bind("<FocusOut>", load_project_data) 

    delete_button = ttk.Button(project_frame, text="Löschen", command=delete_project)
    delete_button.grid(row=0, column=2, padx=5, pady=5)
    frameElements["research_project"]["delete_button"] = delete_button

    restart_checkbox = ttk.Checkbutton(project_frame, text="Recherche fortsetzen", variable=frameElements["research_project"]["resume_var"])
    restart_checkbox.grid(row=0, column=3, padx=5, pady=5)
    frameElements["research_project"]["restart_checkbox"] = restart_checkbox

    # Suchfeld erstellen
    main_frame = ttk.Frame(research_project_frame)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)

    search_label = ttk.Label(main_frame, text="Suchbegriffe:")
    search_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    search_entry = tk.Text(main_frame, width=40, height=3, wrap=tk.NONE)
    search_entry.grid(row=0, column=1, padx=5, pady=5)
    frameElements["research_project"]["search_entry"] = search_entry

    research_label = ttk.Label(main_frame, text="Forschungsthema:")
    research_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")

    research_entry = tk.Text(main_frame, width=40, height=3)
    research_entry.grid(row=1, column=1, padx=5, pady=5)
    frameElements["research_project"]["research_text"] = research_entry

    outline_label = ttk.Label(main_frame, text="Beitragsgliederung:")
    outline_label.grid(row=2, column=0, padx=5, pady=5, sticky="nw")

    outline_entry = tk.Text(main_frame, width=40, height=5)
    outline_entry.grid(row=2, column=1, padx=5, pady=5)
    frameElements["research_project"]["outline_text"] = outline_entry

    # Dropdown für Universitäten erstellen
    uni_label = ttk.Label(main_frame, text="Universitätszugang:")
    uni_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")

    uni_var = tk.StringVar(value=load_last_uni())
    uni_dropdown = ttk.Combobox(main_frame, textvariable=uni_var, values=(list(unis.values()) if unis else ["Lädt . . ."]), state="readonly")
    uni_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="w")

    frameElements["research_project"]["uni_dropdown"] = uni_dropdown

    update_icon = ttk.Button(main_frame, text="Online neu laden", command=update_universities)
    update_icon.grid(row=3, column=2, padx=5, pady=5, sticky="w")

    portal_label = ttk.Label(main_frame, text="Portale (keine Kooperation):")
    portal_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")

    checkbox_frame = ttk.Frame(main_frame)
    checkbox_frame.grid(row=4, column=1, padx=5, pady=5)
    frameElements["research_project"]["portal_checkboxes"] = []
    
    checkbox_vars = {}
    for portal in portals:
        var = tk.BooleanVar()
        checkbox = ttk.Checkbutton(checkbox_frame, text=portal, variable=var)
        checkbox.pack(side="left", padx=5)
        checkbox_vars[portal] = var
        
    frameElements["research_project"]["portal_checkboxes"] = checkbox_vars

    # Speicherort
    save_location_label = ttk.Label(main_frame, text="Speicherort:")
    save_location_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")

    frameElements["research_project"]["save_location_var"] = tk.StringVar()
    save_location_entry = ttk.Entry(main_frame, textvariable=frameElements["research_project"]["save_location_var"], state="readonly", width=30)
    save_location_entry.grid(row=5, column=1, padx=5, pady=5, sticky="w")
    frameElements["research_project"]["save_location_entry"] = save_location_entry

    save_location_button = ttk.Button(main_frame, text="Auswählen", command=select_save_location)
    save_location_button.grid(row=5, column=2, padx=5, pady=5)
    frameElements["research_project"]["save_location_button"] = save_location_button

    # Eingabefeld für Limit an Beiträgen
    limit_label = ttk.Label(main_frame, text="Limit an Beiträgen:")
    limit_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")

    frameElements["research_project"]["limit_var"] = tk.IntVar(value=10)
    limit_entry = ttk.Entry(main_frame, textvariable=frameElements["research_project"]["limit_var"], width=10)
    limit_entry.grid(row=7, column=1, padx=5, pady=5, sticky="w")
    
    # Hinweis zur Verwendung
    copyright_label = ttk.Label(main_frame, wraplength=300, text="Ja, ich habe die urheberrechtlichen Hinweise zur Nutzung (README) gelesen und nutze das Tool für zulässige Zwecke (z.B. wissenschaftliche Forschungszwecke).")
    copyright_label.grid(row=8, column=1, padx=5, pady=5, sticky="w")
    
    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=9, column=0, columnspan=3, pady=5)

    research_button = ttk.Button(button_frame, text="Recherche starten", command=search_action)
    research_button.pack(side="left", padx=5)
    frameElements["research_project"]["research_button"] = research_button

    optimize_button = ttk.Button(button_frame, text="Suchbegriffe optimieren", command=optimize_keywords)
    optimize_button.pack(side="left", padx=5)
    frameElements["research_project"]["optimize_button"] = optimize_button
    
    # Ladeanzeige hinzufügen
    frameElements["research_project"]["progress_var"] = tk.IntVar()
    frameElements["research_project"]["progress_bar"] = ttk.Progressbar(main_frame, variable=frameElements["research_project"]["progress_var"], maximum=100)
    frameElements["research_project"]["progress_bar"].grid(row=10, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

    frameElements["research_project"]["progress_label"] = ttk.Label(main_frame, text="")
    frameElements["research_project"]["progress_label"].grid(row=11, column=0, columnspan=2, padx=5, pady=5, sticky="w")

    # Ladeanzeige zunächst ausblenden
    frameElements["research_project"]["progress_bar"].grid_remove()

    return research_project_frame

# Kurzantwort Tab

def create_short_answer_frame():
    short_answer_frame = ttk.Frame(root)
    frameElements["short_answer"] = {}

    question_label = ttk.Label(short_answer_frame, text="Frage:")
    question_label.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

    question_entry = tk.Text(short_answer_frame, width=40, height=5)
    question_entry.grid(row=0, column=1, padx=5, pady=5)
    frameElements["short_answer"]["question_entry"] = question_entry

    uni_label = ttk.Label(short_answer_frame, text="Universitätszugang:")
    uni_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

    uni_var = tk.StringVar(value=load_last_uni())
    uni_dropdown = ttk.Combobox(short_answer_frame, textvariable=uni_var, values=(list(unis.values()) if unis else ["Lädt . . ."]), state="readonly")
    uni_dropdown.grid(row=1, column=1, padx=5, pady=5, sticky="w")
    frameElements["short_answer"]["uni_dropdown"] = uni_dropdown

    portal_label = ttk.Label(short_answer_frame, text="Portale (keine Kooperation):")
    portal_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
    
    selected_portal = tk.StringVar()
    portal_dropdown = ttk.Combobox(short_answer_frame, textvariable=selected_portal, values=list(portals.keys()), state="readonly")
    portal_dropdown.grid(row=2, column=1, padx=5, pady=5, sticky="w")
    frameElements["short_answer"]["portal_dropdown"] = portal_dropdown

    result_box = tk.Text(short_answer_frame, width=60, height=15, state="disabled")
    result_box.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
    frameElements["short_answer"]["result_box"] = result_box
    
    # Hinweis zur Verwendung
    copyright_label = ttk.Label(short_answer_frame, wraplength=300, text="Ja, ich habe die urheberrechtlichen Hinweise zur Nutzung (README) gelesen und nutze das Tool nur für wissenschaftliche Forschungszwecke.")
    copyright_label.grid(row=5, column=1, padx=5, pady=5, sticky="w")

    start_button = ttk.Button(short_answer_frame, text="Antwort erhalten",command=short_answer)
    start_button.grid(row=6, column=1, padx=5, pady=10, sticky="e")
    frameElements["short_answer"]["start_button"] = start_button

    return short_answer_frame

# Einstellungen Tab
def create_settings_frame():
    settings_frame = ttk.Frame(root)
    frameElements["settings"] = {}

    allgemeine_einstellungen_label = ttk.Label(settings_frame, text="Allgemeine Einstellungen", font=("Segoe UI", 10, "bold"))
    allgemeine_einstellungen_label.grid(row=0, column=0, columnspan=2, padx=5, pady=(10, 5), sticky="w")

    api_url_label = ttk.Label(settings_frame, text="AI API Base-URL (z.B. OpenAI, OpenRouter):")
    api_url_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

    api_url_entry = ttk.Entry(settings_frame, textvariable=api_url_var, width=50)
    api_url_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
    frameElements["settings"]["api_url_entry"] = api_url_entry

    api_key_label = ttk.Label(settings_frame, text="API-Key:")
    api_key_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")

    api_key_entry = ttk.Entry(settings_frame, textvariable=api_key_var, width=50)
    api_key_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
    frameElements["settings"]["api_key_entry"] = api_key_entry

    api_model_label = ttk.Label(settings_frame, text="Sprachmodell:")
    api_model_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")

    api_model_entry = ttk.Entry(settings_frame, textvariable=api_model_var, width=50)
    api_model_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
    frameElements["settings"]["api_model_entry"] = api_model_entry

    proxy_label = ttk.Label(settings_frame, text="Proxy (optional):")
    proxy_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")

    proxy_entry = ttk.Entry(settings_frame, textvariable=proxy_var, width=50)
    proxy_entry.grid(row=4, column=1, padx=5, pady=5, sticky="w")
    frameElements["settings"]["proxy_entry"] = proxy_entry

    pdf_settings_label = ttk.Label(settings_frame, text="Einstellungen für die PDF-Auswertung (optional für PDF-Suche per Google)", font=("Segoe UI", 10, "bold"))
    pdf_settings_label.grid(row=5, column=0, columnspan=2, padx=5, pady=(15, 5), sticky="w")

    # Ordnerauswahl für Poppler-Pfad
    def choose_poppler_path():
        path = filedialog.askdirectory()
        if path:
            poppler_path_var.set(path)

    poppler_path_label = ttk.Label(settings_frame, text=r"Poppler-Pfad (endet mit \Library\bin):")
    poppler_path_label.grid(row=6, column=0, padx=5, pady=5, sticky="w")

    poppler_path_frame = ttk.Frame(settings_frame)
    poppler_path_frame.grid(row=6, column=1, padx=5, pady=5, sticky="w")

    poppler_path_entry = ttk.Entry(poppler_path_frame, textvariable=poppler_path_var, width=35)
    poppler_path_entry.pack(side="left")

    poppler_path_button = ttk.Button(poppler_path_frame, text="...", width=3, command=choose_poppler_path)
    poppler_path_button.pack(side="left")
    
    poppler_path_download_button = ttk.Button(poppler_path_frame, text="Download", width=15, command=lambda:webbrowser.open_new("https://github.com/oschwartz10612/poppler-windows/releases"))
    poppler_path_download_button.pack(side="left")

    frameElements["settings"]["poppler_path_entry"] = poppler_path_entry

    # Ordnerauswahl für Tesseract-Pfad
    def choose_tesseract_path():
        path = filedialog.askdirectory()
        if path:
            tesseract_path_var.set(path)

    tesseract_path_label = ttk.Label(settings_frame, text=r"Tesseract-Pfad (z.B. endet mit \; z.B. ...\Tesseract-OCR\):")
    tesseract_path_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")

    tesseract_path_frame = ttk.Frame(settings_frame)
    tesseract_path_frame.grid(row=7, column=1, padx=5, pady=5, sticky="w")

    tesseract_path_entry = ttk.Entry(tesseract_path_frame, textvariable=tesseract_path_var, width=35)
    tesseract_path_entry.pack(side="left")

    tesseract_path_button = ttk.Button(tesseract_path_frame, text="...", width=3, command=choose_tesseract_path)
    tesseract_path_button.pack(side="left")
    
    tesseract_path_download_button = ttk.Button(tesseract_path_frame, text="Download", width=15, command=lambda:webbrowser.open_new("https://github.com/UB-Mannheim/tesseract/wiki"))
    tesseract_path_download_button.pack(side="left")
    tesseract_path_download_button.pack(side="left")

    frameElements["settings"]["tesseract_path_entry"] = tesseract_path_entry

    # Speichern-Button
    save_button = ttk.Button(settings_frame, text="Speichern", command=save_settings)
    save_button.grid(row=8, column=1, padx=5, pady=10, sticky="e")
    frameElements["settings"]["save_button"] = save_button

    return settings_frame
    
# Info Tab
def create_info_frame():
    info_frame = ttk.Frame(root)
    
    info_text = (
        r"(C) 2025. Version 0.9.0. "
        "Informationen zum Projekt und zur Verarbeitung personenbezogener Daten bei Aktualisierung der Uni-Daten finden sich unter: https://jura-recherche.de"
    )

    label = ttk.Label(
        info_frame,
        text=info_text,
        wraplength=400,  # Breite in Pixeln, ab der ein Umbruch erfolgt
        justify="left"
    )
    label.pack(padx=10, pady=10)
    
    return info_frame
    

# Hauptfenster und Tabs erstellen
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

research_project_frame = create_research_project_frame()
notebook.add(research_project_frame, text="Recherche-Projekt")

short_answer_frame = create_short_answer_frame()
notebook.add(short_answer_frame, text="Kurzantwort")

settings_frame = create_settings_frame()
notebook.add(settings_frame, text="Einstellungen")

info_frame = create_info_frame()
notebook.add(info_frame, text="Über das Tool")

# Ggf. Unis zunächst laden, falls noch nicht definiert
if not unis:
    update_universities()
    
    # Gesamtes Skript sodann neu laden
    python = sys.executable
    os.execl(python, python, *sys.argv)  # Startet das Skript neu
    
# Ggf. mit Tab "Einstellungen" starten
if not script_settings["API_KEY"] or not script_settings["API_URL"]:
    notebook.select(2)
    
root.mainloop()