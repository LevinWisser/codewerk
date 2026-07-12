from __future__ import annotations

from factory_game.models import Mission


DIRECTIONS = {"North": (0, -1), "East": (1, 0), "South": (0, 1), "West": (-1, 0)}

ITEM_NAMES = {
    "steel": "Stahlrohling",
    "plate": "Metallplatte",
    "gear": "Zahnrad",
    "module": "Getriebemodul",
}

MACHINE_DEFINITIONS = {
    "press": ("Presse", ["steel"], "plate", 3),
    "mill": ("Fraese", ["plate"], "gear", 4),
    "assembly": ("Montage", ["plate", "gear"], "module", 5),
}

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
    "pick_up": ("pick_up()", "Nimmt am Materiallager einen Stahlrohling oder am Ausgang einer fertigen Maschine deren Produkt auf. Die Drohne muss auf dem jeweiligen Feld stehen und ihr Inventar muss leer sein.", "if can_pick_up():\n    pick_up()"),
    "drop": ("drop()", "Uebergibt das getragene Teil kontextabhaengig: Auf einer Maschine wird es als Eingangsmaterial geladen, im Versand wird es fuer den Auftrag ausgeliefert.", "# Auf Maschine oder Versand stehen\ndrop()"),
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
    "files": ("Dateien und Imports", "Lege ueber + weitere Python-Dateien an. main.py ist der Einstieg. Lokale Module koennen normal importiert werden; externe Pakete bleiben gesperrt.", "# functions.py\ndef go_east():\n    move(East)\n\n# main.py\nfrom functions import go_east\ngo_east()"),
}
