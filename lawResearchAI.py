import uuid
from bs4 import BeautifulSoup
import re
import time
from openai import OpenAI
import os
import json
import threading
from tkinter import messagebox
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
#from googlesearch import search
import urllib.parse
import requests
from pdf2image import convert_from_bytes
import pytesseract

class lawResearchAI:
    # Konstruktor, um das Objekt zu initialisieren
    def __init__(self, journalsAccess, maxSources, callbackFunction, aiBaseURL, aiAPIKey, aiModel, proxyURL, tesseractPath="", popplerPath=""):
        self.OAIClient = OpenAI(
            base_url=aiBaseURL,
            api_key=aiAPIKey if aiAPIKey else "none",
        )
               
        # Zentrale Einstellungen
        self.requestBreak = 4 # Zeit in Sekunden nach Request
        self.sourcesDownload = False # True = Quellen werden heruntergeladen, False = Nur Links werden angelegt
        self.UniProxy = {
            "http": proxyURL,   # e.g., "http://proxy.ub.tum.de:8080"
            "https": proxyURL, # e.g., "http://proxy.ub.tum.de:8080"
        }
        self.portals = {
            "beck-online":
                {
                    "baseurl":"https://beck-online.beck.de",
                    "url":"https://beck-online.beck.de/Search?pagenr=__PAGENR__&words=__Q__&st=&searchid=",
                    "findLinksByClass":"treffer-firstline-text",
                    "resultsPerPage":20,
                },
            "google-search":
                {
                    "url":"__Q__",
                    "url":"__Q__",
                    "separateAPI": True,
                },
            "juris":
                {
                    "baseurl":"https://www.juris.de",
                    "url":"https://www.juris.de/r3/?query=__Q__",
                    "findLinksByClass":"result-list__entry-link",
                },
        }
        
        # Einstellungen anhand übergebener Variablen
        self.journalsAccess = journalsAccess
        self.maxSources = maxSources
        self.aiModel = aiModel;
        
        if tesseractPath and popplerPath:
            pytesseract.pytesseract.tesseract_cmd = tesseractPath+"tesseract.exe"
            self.popplerPath = popplerPath
        
        
        if callable(callbackFunction):
            self.callbackFunction = callbackFunction
        else:
            self.callbackFunction = print            
        
    # Keywords optimieren
    def optimizeKeywords(self, queries, portalsSelected):
        self.callbackFunction(50, "Optimierung beginnt . . .")
        
        self.portalsSelected = portalsSelected
        
        # Mehrere Zeilen in eine Zeile umwandeln, getrennt durch ';;'
        queries = single_line_query = ";;".join(queries.splitlines())
        
        if self.portalsSelected == ["beck-online"]:
            # ChatGPT anfragen, Beck-Online Suchoperatoren berücksichtigen
            prompt = "Für eine juristische Recherche optimierst Du die folgenden Suchbegriffe durch ;; getrennt, indem du bessere oder ähnliche Suchbegriffe, Suchoperatoren (UND, ODER, OHNE, NAHE), Klammern und Anführungszeichen verwendest. Gib mir nur die neu generierten Suchbegriffe durch ;; getrennt zurück. Die bisherigen Suchbegriffe lauten: " + queries
        else:
            prompt = "Für eine juristische Recherche optimierst Du die folgenden Suchbegriffe durch ;; getrennt, indem du bessere oder ähnliche Suchbegriffe, Klammern und Anführungszeichen, aber keine Suchoperatoren verwendest. Gib mir nur die neu generierten Suchbegriffe durch ;; getrennt zurück.  Die bisherigen Suchbegriffe lauten: " + queries
        
        # OpenAI-API -> Relevanz in Prozent einordnen; relevante weiterführende Quellen
        completionReq = self.OAIClient.chat.completions.create(
            model=self.aiModel,
            max_completion_tokens=4000,
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent für einen Jura-Professor/Wissenschaftler."},
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        content = completionReq.choices[0].message.content
        
        if content:
            self.callbackFunction(100, "Suchbegriffe wurden erfolgreich optimiert.")
            return content.split(";;")
        else:
            return False
    
    # Kurzantwort generieren
    def shortAnswer(self, query, portalsSelected):
        self.callbackFunction(1, "Kurzantwort wird vorbereitet . . .")
        answer = ""
        
        self.portalsSelected = portalsSelected
        
        # Mehrere Query-Zeilen in eine Zeile umwandeln
        query = " ".join(query.splitlines())
        
        # 1. Schritt: AI-Tool nach geeigneten Suchbegriffen fragen
        self.callbackFunction(33, "Es wird nach geeigneten Suchbegriffen gefragt . . .")
        
        if self.portalsSelected == "beck-online":
            # ChatGPT anfragen, Beck-Online Suchoperatoren berücksichtigen
            prompt = "Du sollst mir später eine kurze Antwort zu einer juristischen Frage geben. Ich werde dir Eingabekontext zur Verfügung stellen, den ich aus einer juristischen Datenbank lade. Gib mir für diese juristische Datenbank genau einen passenden Suchbegriff aus, wobei du Suchoperatoren (UND, ODER, OHNE, NAHE), Klammern und Anführungszeichen verwenden kannst. Gib mir nur diesen neu generierten Suchbegriff aus. Die zugehörige Frage lautet: " + query
        else:
            prompt = "Du sollst mir später eine kurze Antwort zu einer juristischen Frage geben. Ich werde dir Eingabekontext zur Verfügung stellen, den ich aus einer juristischen Datenbank lade. Gib mir für diese juristische Datenbank genau einen passenden Suchbegriff aus, wobei du Klammern und Anführungszeichen verwenden kannst. Gib mir nur diesen neu generierten Suchbegriff aus. Die zugehörige Frage lautet: " + query
        
        # OpenAI-API
        completionReq = self.OAIClient.chat.completions.create(
            model=self.aiModel,
            max_completion_tokens=4000,
            messages=[
                {"role": "system", "content": "Du bist ein hilfreicher Assistent für einen Jura-Professor/Wissenschaftler."},
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        searchQuery = completionReq.choices[0].message.content
                
        if not searchQuery:
            return False
            
        # 2. Schritt: Suche durchführen
        self.callbackFunction(67, f"Suche nach \"{searchQuery}\" wird durchgeführt . . .")
        
        # Playwright intialisieren
        with sync_playwright() as p:        
            self.playwright = {}
            
            if self.UniProxy:
                self.playwright["browser"] = p.chromium.launch(headless=False, proxy={"server": self.UniProxy["https"]})
            else:
                self.playwright["browser"] = p.chromium.launch(headless=False)
            
            # Erstelle einen neuen Browser-Kontext mit dem User-Agent
            self.playwright["context"] = self.playwright["browser"].new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            self.playwright["page"] = self.playwright["browser"].new_page()
            
            # Ggf. juris Autologin durchführen
            if self.portalsSelected == "juris":
                self.req(jurisAutoLogin)
            else:
                # Nutzer zum Login auffordern
                messagebox.showinfo("Login ggf. erforderlich", "Nutze den geöffneten Tab im Browser (und lasse diesen im Anschluss geöffnet), um Dich bei den ausgewählten Plattformen anzumelden. Schließe dieses Fenster, sobald Du Dich angemeldet hast. Die Recherche wird dann fortgesetzt.")
        
            if self.portalsSelected in self.portals:
                portalLink = self.portals[self.portalsSelected]["url"].replace("__Q__", urllib.parse.quote(searchQuery))
                
                # PAGE 1
                portalLink1 = portalLink.replace("__PAGENR__", "1")
                portalLink1 = portalLink1.replace("__PAGESTART__", "0")  # Hinweis: Nicht für Beck-Online benötigt
        
                sources = self.processPortalSearch(portalLink1, self.portalsSelected, True)
                
                if sources:
                    # Erste Quelle abfragen und als Context übergeben
                    text = self.renderDocumentURL(sources[0], True)
                else:
                    text = ""                    
                            
            # 3. Schritt: Antwort generieren
            prompt = "Beantworte die folgende juristische Frage (ohne Formatierung mit Ausnahme von Zeilenumbrüchen): " + query
            
            if text:
                self.callbackFunction(80, f"Antwort wird anhand der Quelle {sources[0]} generiert . . .")
                prompt += " Nutze für die Antwort die folgende Quelle und zitiere sie ggf. in Klammern: " + text
            else:
                self.callbackFunction(80, f"Antwort wird ohne Quelle generiert . . .")
            
            # OpenAI-API
            completionReq = self.OAIClient.chat.completions.create(
                model=self.aiModel,#model="gpt-4o",#
                max_completion_tokens=12000,
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher Assistent für einen Jura-Professor/Wissenschaftler."},
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            answer = completionReq.choices[0].message.content
            
            # Browser am Ende schließen
            self.playwright["browser"].close()
            
            # Antwort zurückgeben
            return answer
        
    
    # Recherche durchführen
    def research(self, projectDir, topic, topicSentence, topicStructure, searchKeywords, portalsSelected, jurisAutoLogin, stopSignal, resumeSearchOption=False):
        self.callbackFunction(-1, "Suche beginnt . . .")
        
        # Projekt aus Datei laden -> verdrängt übergebene Variablen
        self.topic = topic
        
        self.count = [0, 0, 0, 0] # [0] durchgeführte Suchen, [1] durchgeführte Dokumentabrufe, [2] durchgeführte AI-API-Requests, [3] error-Dateibezeichnungen
            
        self.projectDir = projectDir
    
        self.topic = topic
        self.topicSentence = topicSentence
        self.topicStructure = " ".join(topicStructure) if isinstance(topicStructure, list) else topicStructure
                
        self.searchKeywords = searchKeywords
        self.portalsSelected = portalsSelected
        
        self.searchResultsURLs = [] # alle noch zu prüfenden Dokumente
        self.allSearchesProcessed = False # Sobald True, wird der zweite Thread seine Arbeit abschließen
        
        self.sourcesProcessed = [] # alle bereits vollständig verarbeiteten Dokumente (dient auch Duplikatscheck)
        self.addSourcesProcessed = [] # alle Quellen aus Links (d.h. bloße Suchstrings) werden hierüber ggf. gesperrt, wenn bereits einmal abgerufen
        
        # Playwright initialisieren und ggf. juris Autologin durchführen
        with sync_playwright() as p:        
            self.playwright = {}
            
            if self.UniProxy:
                self.playwright["browser"] = p.chromium.launch(headless=False, proxy={"server": self.UniProxy["https"]})
            else:
                self.playwright["browser"] = p.chromium.launch(headless=False)
            
            # Erstelle einen neuen Browser-Kontext mit dem User-Agent
            self.playwright["context"] = self.playwright["browser"].new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            self.playwright["page"] = self.playwright["browser"].new_page()

            # Ggf. juris Autologin durchführen
            if "juris" in self.portalsSelected:
                self.req(jurisAutoLogin)
            
            # Prüfen, ob projectDir existiert
            if not os.path.isdir(projectDir):
                self.callbackFunction(-1, "Abbruch: Der Projektordner existiert nicht.")
                raise ValueError("Der Projektordner existiert nicht")
            
            # Nutzer zum Login auffordern
            messagebox.showinfo("Login ggf. erforderlich", "Nutze den geöffneten Tab im Browser (und lasse diesen im Anschluss geöffnet), um Dich bei den ausgewählten Plattformen anzumelden. Schließe dieses Fenster, sobald Du Dich angemeldet hast. Die Recherche wird dann fortgesetzt.")
            
            # Session ggf. wiederherstellen (Funktion überschreibt diverse Werte) und falls neue Session auch Übersichtsdatei neu anlegen
            if resumeSearchOption:
                if not self.resumeSearch():
                    # Übersichtsdatei anlegen
                    with open(f"{projectDir}\\LITERATUR.txt", 'w', encoding='utf-8') as file:
                        file.write(f"Literatur-Überblick für das Projekt: {self.topic}\r\n\r\n")
            else:
                # Übersichtsdatei anlegen
                with open(f"{projectDir}\\LITERATUR.txt", 'w', encoding='utf-8') as file:
                    file.write(f"Literatur-Überblick für das Projekt: {self.topic}\r\n\r\n")
            
            # Suchen ausführen, um erste Dokument-Links zu speichern
            while self.searchKeywords:
                keyword = self.searchKeywords.pop(0)
                
                for portal in self.portalsSelected:
                    if portal in self.portals:
                        # Suche auf jeweiligem Portal durchführen
                        portalLink = self.portals[portal]["url"].replace("__Q__", urllib.parse.quote(keyword))
                        
                        addedSources = len(self.searchResultsURLs)
                        
                        # PAGE 1
                        portalLink1 = portalLink.replace("__PAGENR__", "1")
                        portalLink1 = portalLink1.replace("__PAGESTART__", "0")  # Hinweis: Nicht für Beck-Online benötigt
                        
                        self.callbackFunction(-1, f"Suche wird ausgeführt für: {keyword} auf {portal} (Seite 1)")
                        self.processPortalSearch(portalLink1, portal, False)
                        
                        time.sleep(self.requestBreak)
                        
                        addedSources = len(self.searchResultsURLs) - addedSources
                  
                        if ("resultsPerPage" in self.portals[portal] and addedSources == self.portals[portal]["resultsPerPage"]):
                            # PAGE 2, falls erste Seite vollständig mit Suchergebnissen gefüllt (und z.B. nicht bei Google Search)
                            portalLink2 = portalLink.replace("__PAGENR__", "2")
                            portalLink2 = portalLink2.replace("__PAGESTART__", f"{self.portals[portal]["resultsPerPage"] * 1 - 1}") # Hinweis: Nicht für Beck-Online benötigt
                            
                            self.callbackFunction(-1, f"Suche wird ausgeführt für: {keyword} auf {portal} (Seite 2)")
                            self.processPortalSearch(portalLink2, portal, False)
                        
                if stopSignal.is_set():
                    self.saveSearch()
                    break
                
                time.sleep(self.requestBreak)
                
            # 2. Schritt: Dokumente abarbeiten
            while 1==1:
                if len(self.sourcesProcessed) >= self.maxSources:
                    self.callbackFunction(-1, "Maximum erreicht. Beenden.")
                    break

                if self.searchResultsURLs:
                    self.renderDocumentURL(self.searchResultsURLs.pop(0), False)
                    self.callbackFunction(round((len(self.sourcesProcessed)) / (self.maxSources) * 100), f"Dokument gerendert (insgesamt {len(self.sourcesProcessed)}). Noch {min(len(self.searchResultsURLs), self.maxSources)} verbleibend")
                else:
                    self.callbackFunction(-1, "Alle Ergebnisse wurden verarbeitet. Beenden.")
                    self.saveSearch()
                    break
                #elif self.allSearchesProcessed:
                    # Endlosschleife und damit Thread 2 beenden
                #    break
                
                sleep_time = self.requestBreak
                while sleep_time > 0:
                    if stopSignal.is_set():
                        self.saveSearch()
                        break
                        
                    # Schlaf für das kleine Intervall
                    time.sleep(0.1)
                    sleep_time -= 0.1     
                
                if stopSignal.is_set():
                    self.saveSearch()
                    break
            
            
            # Browser am Ende schließen
            self.playwright["browser"].close()
    
    # Suche speichern
    def saveSearch(self):
        current_script_path = os.path.realpath(__file__)
        parent_folder_path = os.path.dirname(current_script_path)
        
        serializable_dict = {
            key: value
            for key, value in self.__dict__.items()
            if isinstance(value, (str, int, float, list, dict, bool, type(None)))  # Filter nur serialisierbare Typen
            and key != "playwright"  # Schließt 'playwright' aus
        }
        
        with open(os.path.join(parent_folder_path, f"project{self.safe_string_for_filename(self.topic)}.json"), "w", encoding="utf-8") as f:
            json.dump(serializable_dict, f)
    
    # Gespeicherte Suche aus Datei laden
    def resumeSearch(self):
        current_script_path = os.path.realpath(__file__)
        parent_folder_path = os.path.dirname(current_script_path)
        
        try:
            with open(os.path.join(parent_folder_path, f"project{self.safe_string_for_filename(self.topic)}.json"), "r", encoding="utf-8") as f:
                self.__dict__.update(json.load(f))
                return True
        
        except FileNotFoundError:
            return False
        
    def processPortalSearch(self, searchURL, portal, returnOnly):
        # Portal-Suchergebnisse auswerten und in Linksliste aufnehmen bzw. zurückgeben, wenn returnOnly = true gesetzt ist
        returnLinks = []
        
        if (portal == "google-search"):
            # Google Suche durchführen
            query = urllib.parse.unquote(searchURL)+" filetype:pdf"
            
            '''TODO!for tURL in search(query, num_results=20):
                if not tURL:
                    continue
                
                if returnOnly:
                    # URL in Rückgabeliste aufnehmen
                    returnLinks.append(tURL+"?PDF") 
                else:
                    # URL aufnehmen, wenn nicht bereits in der Liste
                    if tURL not in self.searchResultsURLs and tURL not in self.sourcesProcessed:
                        self.searchResultsURLs.append(tURL+"?PDF")'''
        else:
            # Alle anderen Portale
            response = self.req(searchURL)
                    
            if not response:
                return None
            
            if not returnOnly:
                self.count[0] += 1
            
            # Parsen des HTML-Dokuments
            soup = BeautifulSoup(response["text"], 'html.parser')

            # Alle relevanten Links extrahieren
            if (self.portals[portal]):
                if (self.portals[portal]["findLinksByClass"]):
                    # Links durch Klasse finden (insb. Beck Online)
                    
                    # Finden aller Links-Elemente mit entsprechender Klasse
                    elements = soup.find_all('a', href=True, class_=self.portals[portal]["findLinksByClass"])
                    
                    # Links extrahieren und übernehmen
                    targetURLs = []
                    tURL = ""
                    for element in elements:
                        tURL = element['href']
                        
                        # Ggf. Präfix
                        if tURL.startswith('/'):
                            tURL = self.portals[portal]["baseurl"]+tURL
                    
                        # Referer anhängen
                        tURL += "&__REF__="+searchURL
                    
                        if returnOnly:
                            # URL in Rückgabeliste aufnehmen
                            returnLinks.append(tURL) 
                        else:
                            # URL aufnehmen, wenn nicht bereits in der Liste
                            if tURL not in self.searchResultsURLs and tURL not in self.sourcesProcessed:
                                self.searchResultsURLs.append(tURL)
                else:
                    # Fallback und übrige Plattformen: Übernimmt die zehn längsten Links
                    # Alle Links extrahieren
                    links = [a.get("href", "") for a in soup.find_all("a") if a.get("href")]

                    # Links sortieren und die 10 längsten extrahieren
                    top_10_links = sorted(links, key=len, reverse=True)[:10]

                    # BaseURL generieren
                    #parsed_url = urlparse(searchURL)
                    #base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

                    # Ausgabe
                    for tURL in top_10_links:
                        # Ggf. Präfix
                        if tURL.startswith('/'):
                            tURL = self.portals[portal]["baseurl"]+tURL
                        
                        # Referer anhängen
                        tURL += "&__REF__="+searchURL
                        
                        if returnOnly:
                            # URL in Rückgabeliste aufnehmen
                            returnLinks.append(tURL) 
                        else:
                            # URL aufnehmen, wenn nicht bereits in der Liste
                            if tURL not in self.searchResultsURLs and tURL not in self.sourcesProcessed:
                                self.searchResultsURLs.append(tURL)
                    
        if returnOnly:
            return returnLinks
    
    # Spezifisches Dokument rendern und weiter iRd Recherche verarbeiten bzw. nur Inhalt zurückgeben (returnOnly)
    def renderDocumentURL(self, url, returnOnly): 
        # Abbruch, wenn bereits gerendert 
        if not returnOnly and url in self.sourcesProcessed:
            return False
        
        # BaseURL generieren
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        ref = False
        
        # Ggf. Referer extrahieren ("__REF__")
        match = re.search(r"&__REF__=([^&]+)", url)
        ref = match.group(1) if match else None

        # Ersetzen von &__REF__= und der URL im String
        url = re.sub(r"&__REF__=[^&]+", "", url)
        
        isPDF = False
        
        # Abrufen: Geplantes PDF ("?PDF") oder HTML
        if url.endswith("?PDF"):
            response = self.reqPDF(url[:-4], ref)
            isPDF = True
        else:
            # Abrufen (ggf. mit Referer)
            response = self.req(url, ref)
           
        if not response:
            # Bei Fehler URL speichern und return
            if not returnOnly:
                with open(f"{self.projectDir}\\error_{self.count[3]}.txt", 'w', encoding='utf-8') as file:
                    file.write(f"Fehler: URL nicht abrufbar. Betrifft: {url}")
            
            return False
        
        # Abbruch, wenn bereits gerendert (hier: finale URL nach Weiterleitung)
        if not returnOnly and response["url"] in self.sourcesProcessed:
            return False
        
        if not returnOnly:
            self.count[1] += 1
            
            # Als gerendert speichern
            self.sourcesProcessed.append(url)
        
        if isPDF:
            text = response["text"]
        else:
            # HTML-Dokument vorbereiten
            soup = BeautifulSoup(response["text"], 'html.parser')
            
            # Extrahieren des Textes
            text = ""
            
            if (url.startswith("https://beck-online.beck.de")):
                # Beck Online
                element = soup.find('div', class_='dokcontent')  # Finde ein spezifisches Element
                if element:
                    text = element.get_text(separator='\n', strip=True)
            elif ("juris.de/" in url):
                # juris
                element = soup.find('div', class_='doc-sheet')  # Finde ein spezifisches Element
                if element:
                    text = element.get_text(separator='\n', strip=True)
            else:
                # Andere
                soup.get_text(separator='\n', strip=True)
            
        if text:
            # Text gefunden -> Auswerten
                       
            # Text ggf. nur zurückgeben
            if returnOnly:
                return text
            
            # Nicht nur Rückgabe, sondern fortfahren
            self.count[2] += 1
            
            # OpenAI-API -> Relevanz in Prozent einordnen; relevante weiterführende Quellen
            completionReq = self.OAIClient.chat.completions.create(
                model=self.aiModel,
                max_completion_tokens=12000,
                #response_format: {"type":"json_schema","json_schema":{"strict":true,"schema": ...} },
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher Assistent für einen Jura-Professor/Wissenschaftler."},
                    {
                        "role": "user",
                        "content": f"Du bist der beste Rechtswissenschaftler und schreibst einen juristischen Aufsatz zu dem Thema {self.topic}."
                                   f"{self.topicSentence} "
                                   f"{'Der Aufsatz enthält folgende Gliederungsebenen: ' + self.topicStructure + '.' if self.topicStructure else ''}"
                                   f"Vor diesem Hintergrund sichtest du den folgenden Text. Gib mir im JSON-Format folgende vier Parameter aus: 0. file: Kurzbezeichnung als Dateiname ohne Endung (z.B.: GRUR2020,1) 1. relevance: 0-3 (0: gar nicht (z.B. nur Wiedergabe des Gesetzeswortlauts und kein Aufsatz o.ä.), 1: kaum relevant (z.B. sehr kurze Quelle, überblicksartige Kommentierung), 2: Durchschnitt (im Zweifel anzunehmen), 3: nur selten von Dir anzunehmen, sehr hohe Relevanz für konkretes Thema anhand der Schlagworte und langer, tiefgehender Beitrag) für Relevanz des Textes für deinen Aufsatz. 2. relevantparas: Verweise auf relevante Stellen des Textes (d.h. Seitenzahl oder Rn.) zugeordnet zum jeweiligen Gliederungspunkt des Aufsatzes. 3. additionalsources: für das Thema besonders relevante, einzigartige Quellen (keine §§; nur Rechtsprechung und Literatur; max. 10 Quellen) im Zitierformat ohne Autorname (z.B. GRUR 2020, 1); die Relevanz beurteilst du anhand des Titels und ggf. des Texts, der sich vor der jeweiligen Fußnote findet.\n###\n{text}"
                    }
                ]
            )
            
            content = completionReq.choices[0].message.content
            content = content.strip('```json').strip('```').strip()
        
            completion = json.loads(content)
        
            if completion['relevance'].is_integer() and completion['relevance'] > 0:
                self.callbackFunction(-1, "Text KI-basiert ausgewertet . . .")
                
                # Text entsprechend Relevanz speichern bzw. Link anlegen
                if (self.sourcesDownload):
                    with open(f"{self.projectDir}\\{completion['relevance']}_{self.safe_string_for_filename(completion['file'])}.html", 'w', encoding='utf-8') as file:
                        file.write(f"<base href=\"{base_url}\" />{response["text"]}")
                else:
                    with open(f"{self.projectDir}\\{completion['relevance']}_{self.safe_string_for_filename(completion['file'])}.url", 'w', encoding='utf-8') as file:
                        file.write(f"[InternetShortcut]\nURL={url}\n")                    

                
                # Überblicks-Datei ergänzen
                with open(f"{self.projectDir}\\LITERATUR.txt", 'a', encoding='utf-8') as file:
                    file.write(f"\r\n- {completion['file']} -\r\n")
                    
                    for i, v in completion['relevantparas'].items():
                        file.write(f"{i}\r\n->{v}\r\n")
                        
                # Ergänzende Quellen aus den Fußnoten aufnehmen
                self.callbackFunction(-1, "Fußnoten berücksichtigen . . .")
                for add in completion['additionalsources']:
                    # Nur aufnehmen, wenn nicht bereits Suchanfrage gelistet
                    if add not in self.addSourcesProcessed:
                        # Einschlägiges Portal prüfen
                        match = re.match(r"([A-Za-z\-]+)\s(\d{4}),\s(\d+)", add)
                        
                        if match:
                            journalName = match.group(1)
                            year = match.group(2)
                            page = match.group(3)
                            
                            if year and page and journalName in self.journalsAccess:
                                year = int(year)
                                page = int(page)
                                
                                for entry in self.journalsAccess[journalName]:
                                    year1 = int(entry["YEAR1"])
                                    year2 = int(entry["YEAR2"])
                                    
                                    # YEAR2 = -1 bedeutet unbegrenztes Ende
                                    if (year2 == -1 and year1 <= year) or (year1 <= year <= year2):
                                        # URL hinzufügen, wenn nicht bereits vorhanden
                                        add = entry["URL"].replace("__YEAR__", str(year)).replace("__PAGE__", str(page))
                                        
                                        if add not in self.searchResultsURLs:
                                            self.searchResultsURLs.append(add)
                                        
                        else:
                            # Nicht identifizierte Quellen zum Überblick über weitere Literatur hinzufügen
                            with open(f"{self.projectDir}\\WEITERE-LITERATUR.txt", 'a', encoding='utf-8') as file:
                                file.write(f"{add}\r\n")
            
                self.callbackFunction(-1, "Beitrag analysiert")
            
            elif not completion['relevance'].is_integer():
                # ChatGPT-Ausgabe bei Fehler in Datei speichern
                self.count[3] += 1
                
                with open(f"{self.projectDir}\\error_{self.count[3]}.txt", 'w', encoding='utf-8') as file:
                    file.write(completionReq.choices[0].message)
            else:
                self.callbackFunction(-1, "Irrelevanten Beitrag ignoriert.")
                
        else:
            # Kein Text gefunden -> Dann gesamte Seite abspeichern
            if (self.sourcesDownload):
                with open(f"{self.projectDir}\\CHECK_{self.safe_string_for_filename(str(uuid.uuid4().hex[:8]))}.html", 'w', encoding='utf-8') as file:
                    file.write(f"<base href=\"{base_url}\" />{response["text"]}")
            else:
                with open(f"{self.projectDir}\\CHECK_{self.safe_string_for_filename(str(uuid.uuid4().hex[:8]))}.url", 'w', encoding='utf-8') as file:
                    file.write(f"[InternetShortcut]\nURL={url}\n")  
        
    def safe_string_for_filename(self, value):
        # Entfernt alle unerlaubten Zeichen (und auch Leerzeichen) durch einen regulären Ausdruck
        # Erlaubte Zeichen sind Buchstaben, Zahlen, Bindestriche und Unterstriche
        safe_string = re.sub(r'[\/:*?"<>|\s]', '_', value)
        
        # Optionale Anpassungen, um sicherzustellen, dass der Dateiname nicht mit Punkt oder Leerzeichen beginnt/endet
        safe_string = safe_string.strip().strip('.').strip()

        max_length = 255
        safe_string = safe_string[:max_length]

        # Rückgabe des umgewandelten, sicheren Strings
        return safe_string 
        
    def req(self, url, ref=False):
        # Führt einen Request bei Aufruf innerhalb einer Playwright-Session durch (ermöglicht insb. Ausführung von Javascript), setzt vorherige Ausführung von research() voraus!
        page = self.playwright["page"]
        try:
            # Anfrage durchführen, ggf. mit Referer
            if ref:
                page.route("**/*", lambda route, request: self.playwright_intercept_request(route, request, ref))
                response = page.goto(url, wait_until="networkidle")
            else:
                response = page.goto(url, wait_until="networkidle")
            
            # Warte zusätzlich 3 Sekunden für etwaige Weiterleitungen
            page.wait_for_timeout(3000)
            
            if response and response.status == 200:
                return {"text": page.content(), "url": page.url}
            else:
                return None
        except Exception as e:
            self.callbackFunction(-1, f"Fehler beim Abrufen der Seite: {e}")
            return None 

    def playwright_intercept_request(self, route, request, referer):
        headers = request.headers.copy()
        headers["Referer"] = referer
        route.continue_(headers=headers)   
        
    def reqPDF(self, url, ref=False):
        # Lädt eine PDF-Datei und wandelt diese in einen Text um
        try:
            headers = {"Referer": ref} if ref else {}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            images = convert_from_bytes(response.content, poppler_path=self.popplerPath)
            text = "\n".join([pytesseract.image_to_string(img) for img in images])
            return {"text": text, "url": url}
        except Exception as e:
            self.callbackFunction(-1, f"Fehler beim OCR-Verarbeiten der PDF: {e}")
            return None