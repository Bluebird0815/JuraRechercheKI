# JuraRechercheKI Version 0.9.0.
Das Tool ermöglicht die KI-gestützte juristische Recherche. Anhand von vorgegebenen Suchbegriffen werden Suchen auf den unterstützten juristischen Portalen durchgeführt, sofern der Nutzer Zugang zu den Portalen hat (z.B. im VPN).
Die geladenen Quellen werden KI-gestützt auf deren Relevanz insgesamt (1-3) und für einzelne Gliederungspunkte ausgewertet. Außerdem werden besonders relevante Fußnoten aus dem Dokument ausgelesen und ebenfalls berücksichtigt.
Alle Dateien werden als Links sowie ein Literatur-Überblick als .txt im gewählten Projektordner gespeichert.

JuraRechercheKI ist in der BETA-Version und soll vor allem die Innovationspotenziale in der Rechtswissenschaft aufzeigen, wie sie dargelegt wurden in der Abhandlung ZGE 17 (2025), 1 (https://www.mohrsiebeck.com/artikel/das-urheberrecht-als-kiinnovationsbremse-in-der-rechtswissenschaft-101628zge-2025-0002/).

-- Hintergrund des Tools --
Das Tool will den Einsatz von KI-gestützter Recherche in der Rechtswissenschaft allen ermöglichen, die bereits Zugriff auf die unterstützten juristischen Portale haben.

-- Beachtung des Urheberrechts (s. hierzu ZGE 17 (2025), 1) --
Das deutsche Urheberrecht erlaubt Text und Data Mining für wissenschaftliche Forschungszwecke (§ 60d UrhG) und darf nicht durch technische Schutzmaßnahmen vereitelt werden (§ 95 Abs. 1 Nr. 11 UrhG). Für kommerzielle Zwecke gelten Einschränkungen (§ 44b UrhG).

JuraRechercheKI selbst legt keine dauerhaften Vervielfältigungen an. Es benötigt im Einsatz nur temporäre Vervielfältigungen und legt lediglich Links zu den jeweiligen Dokumenten dauerhaft im Projektordner ab. Abhängig davon, welche KI-Schnittstelle zum Einsatz kommt, kann es zu weiteren, dauerhaften Vervielfältigungen kommen.

Das Tool ist vor diesem Hintergrund nur für wissenschaftliche Forschungszwecke vorgesehen. Die urheberrechtliche Zulässigkeit bedarf einer Prüfung im Einzelfall unter Berücksichtigung der Nutzungshandlungen (z.B. Vervielfältigungen in Abhängigkeit von der gewählten KI-Schnittstelle).

-- Einrichtung --
1. Tool starten
2. Es öffnet sich der Tab "Einstellungen". Hier sind anzugeben:
	a. OpenAI-API-URL: Hier kann jede beliebige URL angegeben werden, die auf Basis der OpenAI-API-Struktur basiert. Das ermöglicht z.B. den lokalen Einsatz von OLlama.
	b. OpenAI-API-Key: Sofern ein Key benötigt wird, ist er hier anzugeben.
	c. Proxy-URL: Sofern Deine Universität einen Proxy benötigt, kann dieser hier angegeben werden. Z.B. https://proxy.universitaet.de:8000
	d.

-- Einsatz des Tools --
## AB HIER: u.a. "noch verbleibend" erklären; Funktionsweise Kurzantwort etc., DANN: License
## Build -> googlesearch Problem lösen, dann: Playwright und "Ext" zusätzlich in main.spec aufnehmen