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
- separater Python-Worker mit eingeschraenkten Systemzugriffen
- durchsuchbare, progressiv freigeschaltete Hilfe mit Codebeispielen
- persistente Credits, Freischaltungen und Programme
- deterministische Simulation und automatisierte Tests

## Tests

```powershell
python -m unittest discover -v
```

Der Spielstand liegt unter `~/.codewerk/save.json`.
