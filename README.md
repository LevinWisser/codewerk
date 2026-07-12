# CODEWERK

CODEWERK ist ein spielbarer Vertical Slice eines 2D-Automatisierungsspiels. Eine Drohne wird mit echtem, kontrolliert ausgefuehrtem Python gesteuert, um eine Rasterfabrik zu versorgen und Produktionsauftraege zu erfuellen.

## Start

Voraussetzung ist Python 3.11 oder neuer mit Tkinter. Es gibt keine externen Abhaengigkeiten.

```powershell
python main.py
```

## Enthalten

- acht aufeinander aufbauende Tutorialauftraege
- Materiallager, Presse, Fraese, Montage und Versand
- integrierter Python-Editor mit Start, Pause, Einzelschritt und Tempo
- IntelliSense fuer Spielbefehle, Python-Schluesselwoerter, Variablen und eigene Funktionen (`Ctrl+Leertaste`)
- mehrere Python-Dateien pro Auftrag mit Tabs und lokalen `import`-/`from ... import ...`-Anweisungen
- separater Python-Worker mit eingeschraenkten Systemzugriffen
- durchsuchbare, progressiv freigeschaltete Hilfe mit Codebeispielen
- persistente Credits, Freischaltungen und Programme
- deterministische Simulation und automatisierte Tests

## Tests

```powershell
python -m unittest discover -v
```

Der Spielstand liegt unter `~/.codewerk/save.json`.

## Mehrere Dateien

`main.py` ist der Einstiegspunkt. Ueber `+` lassen sich weitere Module anlegen:

```python
# paths.py
def go_east():
    move(East)

# main.py
from paths import go_east
go_east()
```

Nur Dateien des aktuellen Spielprojekts koennen importiert werden. Externe Python-Pakete und Systemmodule bleiben aus Sicherheitsgruenden gesperrt.
