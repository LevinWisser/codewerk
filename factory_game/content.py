from __future__ import annotations

from factory_game.models import Mission


DIRECTIONS = {"North": (0, -1), "East": (1, 0), "South": (0, 1), "West": (-1, 0)}

ITEM_NAMES = {
    "steel": "Stahlrohling",
    "plate": "Metallplatte",
    "gear": "Zahnrad",
    "module": "Getriebemodul",
    "copper": "Kupferrohling",
    "polymer": "Polymergranulat",
    "wire": "Kupferdraht",
    "housing": "Kunststoffgehaeuse",
    "actuator": "Aktuator",
}

MACHINE_DEFINITIONS = {
    "press": ("Presse", ["steel"], "plate", 3),
    "mill": ("Fraese", ["plate"], "gear", 4),
    "assembly": ("Montage", ["plate", "gear"], "module", 5),
}

FACTORY_MACHINE_DEFINITIONS = {
    "press": {"name": "Presse", "inputs": ["steel"], "output": "plate", "duration": 3, "cost": 500},
    "mill": {"name": "Fraese", "inputs": ["plate"], "output": "gear", "duration": 4, "cost": 800},
    "wire_drawer": {"name": "Drahtzieher", "inputs": ["copper"], "output": "wire", "duration": 4, "cost": 700},
    "injection": {"name": "Spritzguss", "inputs": ["polymer"], "output": "housing", "duration": 4, "cost": 900},
    "assembly": {"name": "Montage", "inputs": ["gear", "wire", "housing"], "output": "actuator", "duration": 6, "cost": 1200},
}

RAW_MATERIAL_PRICES = {"steel": 10, "copper": 12, "polymer": 8}

MISSIONS = [
    Mission("boot", "01  Systemstart", "Die Wartungsdrohne reagiert wieder. Bewege sie zwei Felder nach Osten.", "Ein Befehl wird von oben nach unten ausgefuehrt.", "Erreiche Position (3, 1).", "move(East)\nmove(East)\n", ["move", "directions"], {"position": [3, 1]}, 100),
    Mission("delivery", "02  Erste Lieferung", "Hole einen Stahlrohling im Materiallager ab und bringe ihn zum Versand.", "Die Drohne kann genau ein Teil tragen.", "Liefere 1 Stahlrohling.", "move(South)\npick_up()\n# Bewege dich zum Versand\n", ["move", "directions", "pick_up", "drop"], {"delivered": {"steel": 1}}, 150),
    Mission("series", "03  Kleine Serie", "Der Kunde braucht drei Rohlinge. Eine Schleife vermeidet wiederholten Code.", "for wiederholt einen eingerueckten Block.", "Liefere 3 Stahlrohlinge.", "for cycle in range(3):\n    # Lager: (1, 2), Versand: (6, 6)\n    pass\n", ["move", "directions", "pick_up", "drop", "loops", "position"], {"delivered": {"steel": 3}}, 220),
    Mission("press", "04  Die Presse", "Verarbeite einen Stahlrohling in der Presse und versende die Platte.", "drop() uebergibt ein Teil an die Maschine; pick_up() nimmt das fertige Produkt auf.", "Liefere 1 Metallplatte.", "# Presse: (3, 2)\n# Belade mit drop(), starte und nimm das Ergebnis mit pick_up() auf.\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "start_machine", "wait"], {"delivered": {"plate": 1}}, 300),
    Mission("sensors", "05  Maschinengefuehl", "Produziere zwei Platten. Frage den Zustand ab, statt feste Wartezeiten zu raten.", "while und Sensoren machen Programme robust.", "Liefere 2 Metallplatten.", "# Beispiel:\n# while not machine_is_done():\n#     wait()\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "start_machine", "wait", "conditions", "machine_is_done"], {"delivered": {"plate": 2}}, 400),
    Mission("coordinates", "06  Navigation", "Nutze die aktuelle Position, um einen Rohling unabhaengig vom Startpunkt zu liefern.", "Koordinaten beginnen links oben bei (0, 0).", "Liefere 1 Stahlrohling und verwende get_position().", "x, y = get_position()\n# Navigiere von jeder Position zuerst zum Lager bei (1, 2).\n", ["move", "directions", "pick_up", "drop", "position", "conditions", "loops"], {"delivered": {"steel": 1}, "requires_call": "get_position"}, 450),
    Mission("milling", "07  Praezisionsteil", "Presse eine Platte, fraese daraus ein Zahnrad und versende es.", "Produkte einer Maschine werden Rohstoffe der naechsten.", "Liefere 1 Zahnrad.", "# Presse: (3, 2), Fraese: (5, 2)\n", ["move", "directions", "pick_up", "drop", "machine", "press_machine", "mill_machine", "start_machine", "wait", "machine_is_done", "functions"], {"delivered": {"gear": 1}}, 600),
    Mission("final", "08  Produktionszelle", "Fertige ein Getriebemodul aus einer Platte und einem Zahnrad.", "Eine gute Funktion kapselt Navigation oder Maschinenbedienung.", "Liefere 1 Getriebemodul.", "def go_to(target_x, target_y):\n    # Implementiere eine wiederverwendbare Navigation.\n    pass\n\n# Montage: (4, 4)\n", ["all"], {"delivered": {"module": 1}}, 1000),
]

HELP = {
    "move": ("move(direction)", "Bewegt die Drohne ein Feld. Blockierte Bewegungen erzeugen einen Fehler.", "move(East)\nmove(South)"),
    "directions": ("Richtungen", "North, East, South und West sind vordefinierte Konstanten.", "for _ in range(3):\n    move(West)"),
    "pick_up": ("pick_up(item=None)", "Nimmt im Tutorial den vorhandenen Rohstoff auf. In der Hauptfabrik waehlt pick_up(item) gezielt einen Rohstoff aus dem Eingangslager; an einem Maschinenausgang wird pick_up() ohne Argument verwendet.", "pick_up('steel')  # Eingangslager\npick_up()         # Maschinenausgang"),
    "drop": ("drop()", "Uebergibt das getragene Teil kontextabhaengig: Auf einer Maschine wird es geladen, am Versandfeld wird es in das unbegrenzte Versandlager gelegt.", "# Auf Maschine oder Versand stehen\ndrop()"),
    "position": ("get_position()", "Gibt die aktuelle Position als (x, y) zurueck.", "x, y = get_position()\nwhile x < 5:\n    move(East)\n    x, y = get_position()"),
    "loops": ("Schleifen", "for wiederholt eine bekannte Anzahl, while solange eine Bedingung gilt.", "for _ in range(4):\n    move(East)"),
    "conditions": ("Bedingungen", "if fuehrt Code nur aus, wenn seine Bedingung wahr ist.", "if can_move(East):\n    move(East)"),
    "functions": ("Eigene Funktionen", "def fasst wiederverwendbare Schritte unter einem Namen zusammen.", "def step_right():\n    move(East)\n\nstep_right()"),
    "machine": ("Maschinen bedienen", "Stelle dich auf eine Maschine, belade sie mit drop(), starte sie mit start_machine() und nimm das fertige Produkt mit pick_up() auf. Sensorabfragen sind sicherer als fest angenommene Wartezeiten.", "drop()\nstart_machine()\nwhile not machine_is_done():\n    wait()\npick_up()"),
    "press_machine": ("Presse", "Position: (3, 2). Eingang: 1 Stahlrohling. Ausgabe: 1 Metallplatte. Verarbeitungszeit: 3 Ticks nach start_machine(), also wait(3).", "drop()\nstart_machine()\nwait(3)\npick_up()"),
    "mill_machine": ("Fraese", "Position: (5, 2). Eingang: 1 Metallplatte. Ausgabe: 1 Zahnrad. Verarbeitungszeit: 4 Ticks nach start_machine(), also wait(4).", "drop()\nstart_machine()\nwait(4)\npick_up()"),
    "assembly_machine": ("Montage", "Position: (4, 4). Eingaenge: 1 Metallplatte und 1 Zahnrad. Ausgabe: 1 Getriebemodul. Verarbeitungszeit: 5 Ticks nach start_machine(), also wait(5). Beide Teile werden nacheinander mit drop() geladen.", "drop()  # erstes Teil\n# zweites Teil holen\ndrop()\nstart_machine()\nwait(5)\npick_up()"),
    "start_machine": ("start_machine()", "Startet die vollstaendig beladene Maschine auf dem aktuellen Feld. Die benoetigte Tickzahl steht im Hilfeeintrag der jeweiligen Maschine.", "start_machine()"),
    "machine_is_done": ("machine_is_done()", "Ist True, wenn die Maschine ein fertiges Produkt bereithaelt.", "while not machine_is_done():\n    wait()"),
    "wait": ("wait(ticks=1)", "Laesst Simulationsticks verstreichen, damit Maschinen arbeiten.", "wait(3)"),
    "all": ("API-Uebersicht", "Im Abschlussauftrag stehen alle bisher erlernten Befehle zur Verfuegung.", "x, y = get_position()"),
    "files": ("Dateien und Imports", "Lege ueber + weitere Python-Dateien an. main.py ist der Einstieg. Lokale Module koennen normal oder mit from modul import * importiert werden; externe Pakete bleiben gesperrt.", "# positions.py\nPRESS = (3, 2)\n\n# main.py\nfrom positions import *\nget_to_pos(PRESS)"),
    "contracts": ("Anfragen und Auftraege", "get_requests() liefert bis zu acht offene Angebote. Nach accept_request(id) erscheint der Auftrag in get_orders(). ticks_left zeigt die verbleibende Bonusfrist. Anfragen bleiben bis zur Annahme oder Ablehnung bestehen.", "for request_id, request in get_requests().items():\n    if request['base_payout'] > 100:\n        accept_request(request_id)"),
    "get_requests": ("get_requests()", "Liefert einen Dictionary-Snapshot aller offenen Anfragen, nach Anfrage-ID indiziert. Enthalten sind product, quantity, base_payout, on_time_bonus und duration.", "requests = get_requests()"),
    "get_orders": ("get_orders()", "Liefert alle aktiven Auftraege. ticks_left wird bei jeder Abfrage neu berechnet und erreicht bei Verspaetung null.", "orders = get_orders()"),
    "accept_request": ("accept_request(request_id)", "Nimmt eine offene Anfrage an, startet ihre Bonusfrist und verbraucht einen Tick.", "accept_request('REQ-0001')"),
    "reject_request": ("reject_request(request_id)", "Lehnt eine offene Anfrage ab. Nach einer kurzen Tickpause erscheint Ersatz.", "reject_request('REQ-0001')"),
    "buy": ("buy(item)", "Kauft genau einen Rohstoff, zieht dessen Preis ab und legt ihn nach einem Tick ins Eingangslager. Kaufbar sind steel, copper und polymer.", "while get_input_stock('steel') < 5:\n    buy('steel')"),
    "get_credits": ("get_credits()", "Liefert die aktuell verfuegbaren Credits. Die Abfrage verbraucht keinen Tick.", "if get_credits() >= 10:\n    buy('steel')"),
    "stocks": ("Lagerbestaende", "get_input_stock() und get_shipping_stock() liefern Dictionaries. Mit einem Item-Argument liefern sie direkt dessen Anzahl. Im Eingangslager wird pick_up(item) verwendet.", "steel_count = get_input_stock('steel')\nall_products = get_shipping_stock()"),
    "get_input_stock": ("get_input_stock(item=None)", "Ohne Argument: Dictionary-Snapshot des Eingangslagers. Mit Item: vorhandene Anzahl dieses Rohstoffs.", "steel = get_input_stock('steel')"),
    "get_shipping_stock": ("get_shipping_stock(item=None)", "Ohne Argument: Dictionary-Snapshot des Versandlagers. Mit Item: vorhandene Anzahl dieses Produkts.", "plates = get_shipping_stock('plate')"),
    "shipping": ("Auftraege versenden", "ship(order_id) funktioniert nur auf dem Versandfeld und nur als Komplettlieferung. Fehlen Produkte, bleiben Lager und Auftrag unveraendert.", "orders = get_orders()\nfor order_id in orders:\n    ship(order_id)"),
    "ship": ("ship(order_id)", "Liefert den gewaehlten Auftrag auf dem Versandfeld komplett aus. Gibt die tatsaechliche Auszahlung zurueck und verbraucht einen Tick.", "payout = ship('ORD-0001')"),
    "get_tick": ("get_tick()", "Liefert den aktuellen globalen Fabriktick, ohne selbst einen Tick zu verbrauchen.", "now = get_tick()"),
    "building": ("Baumodus", "Der Baumodus pausiert laufenden Code. Leere Maschinen koennen kostenlos verschoben oder fuer 75 Prozent des Kaufpreises verkauft werden. Belegte oder laufende Maschinen sind gesperrt.", "# BAUEN in der oberen Werkzeugleiste"),
    "factory_press": ("Presse kaufen", "Kosten: 500 Credits. Eingang: steel. Ausgabe: plate. Dauer: 3 Ticks.", "buy('steel')"),
    "factory_mill": ("Fraese kaufen", "Kosten: 800 Credits. Eingang: plate. Ausgabe: gear. Dauer: 4 Ticks.", "# Freischaltung nach zwei Auftraegen"),
    "factory_wire": ("Drahtzieher kaufen", "Kosten: 700 Credits. Eingang: copper. Ausgabe: wire. Dauer: 4 Ticks.", "buy('copper')"),
    "factory_injection": ("Spritzguss kaufen", "Kosten: 900 Credits. Eingang: polymer. Ausgabe: housing. Dauer: 4 Ticks.", "buy('polymer')"),
    "factory_assembly": ("Aktuator-Montage", "Kosten: 1200 Credits. Eingaenge: gear, wire und housing. Ausgabe: actuator. Dauer: 6 Ticks.", "# Alle drei Teile nacheinander mit drop() laden"),
}
