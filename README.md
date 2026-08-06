# Fly-in — Simulateur de trafic de drones

Fly-in simule le déplacement d'un essaim de drones sur une carte de zones
(hubs) reliées entre elles, en respectant des contraintes de capacité (par
zone et par connexion) et des coûts de déplacement qui dépendent du type de
zone traversée. La simulation s'affiche en temps réel dans une fenêtre
Tkinter.

## Sommaire

- [Fonctionnement général](#fonctionnement-général)
- [Structure du projet](#structure-du-projet)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Format des fichiers de carte](#format-des-fichiers-de-carte)
- [Qualité du code](#qualité-du-code)

## Fonctionnement général

1. `Parser` lit un fichier de carte texte et construit un `Graph` (zones +
   connexions).
2. `Pathfinder` calcule, avec l'algorithme de Dijkstra, le chemin le moins
   coûteux entre la zone `start` et la zone `goal`.
3. `DroneFactory` crée un drone par unité déclarée dans `nb_drones`, tous
   placés initialement sur la zone `start` et suivant le même chemin.
4. La boucle principale de `fly-in.py` fait avancer les drones tour par
   tour : un drone tente d'entrer dans la zone suivante de son chemin ; si
   la zone ou la connexion est pleine, il rejoint une file d'attente. Si
   cette file dépasse une certaine taille, le drone recalcule un nouveau
   chemin.
5. `Visualizer` affiche à chaque tour l'état de la carte : zones, capacité
   occupée, files d'attente et position des drones.

### Types de zone et coûts de déplacement

| Type de zone | Coût pour l'entrer | Remarque |
|---|---|---|
| `normal`     | 2 tours | comportement par défaut |
| `priority`   | 1 tour  | favorisée par le pathfinder |
| `restricted` | 3 tours | ralentit le chemin |
| `blocked`    | 4 tours | inaccessible (`is_accessible()` renvoie 0) |

## Structure du projet

```
.
├── fly-in.py       # point d'entrée : pathfinding + boucle de simulation
├── system.py       # modèles de données (Zone, Connection, Drone, Graph)
├── parser.py       # parseur des fichiers de carte texte
├── visualizer.py   # affichage Tkinter de la simulation
└── maps/           # exemples de cartes (easy / medium / hard / challenger)
```

## Installation

Le projet nécessite Python 3.10+ (utilisation de la syntaxe `X | None`) et
la bibliothèque [pydantic](https://docs.pydantic.dev/) pour la validation
des modèles de données. Tkinter fait partie de la bibliothèque standard
mais doit parfois être installé séparément selon votre distribution
(`sudo apt install python3-tk` sur Debian/Ubuntu).

```bash
pip install pydantic
```

## Utilisation

Le chemin du fichier de carte est actuellement codé en dur dans le bloc
`if __name__ == "__main__":` de `fly-in.py`. Modifiez la ligne suivante pour
pointer vers la carte que vous souhaitez simuler :

```python
graph = parser.parse_file("/chemin/vers/votre/carte.txt")
```

Puis lancez la simulation :

```bash
python fly-in.py
```

Une fenêtre s'ouvre et affiche la carte ainsi que le déplacement des
drones, tour par tour, jusqu'à ce qu'ils soient tous arrivés (ou que la
simulation atteigne la limite de sécurité de 50 tours).

## Format des fichiers de carte

Un fichier de carte est un fichier texte, lu ligne par ligne. Les lignes
vides et celles commençant par `#` sont ignorées.

```txt
# Nombre total de drones à simuler
nb_drones: 4

# Zone de départ (obligatoire, nom "start")
start_hub: start 0 0 [color=green]

# Zones intermédiaires
hub: junction 1 0 [color=yellow max_drones=2]
hub: path_a 2 1 [color=blue]

# Zone d'arrivée (obligatoire, nom "goal")
end_hub: goal 3 0 [color=red]

# Connexions entre zones : "zoneA-zoneB [options]"
connection: start-junction [max_link_capacity=2]
connection: junction-path_a
connection: path_a-goal
```

Attributs disponibles entre crochets `[...]` :

- Sur une zone (`hub:`, `start_hub:`, `end_hub:`) :
  `zone=restricted|blocked|priority|normal`, `color=...`, `max_drones=N`.
- Sur une connexion (`connection:`) :
  `max_link_capacity=N`, `current_usage=N`.

Des exemples complets sont disponibles dans `maps/` (niveaux `easy`,
`medium`, `hard` et `challenger`).

## Qualité du code

Le code respecte :

- **flake8** (PEP8) : `flake8 system.py parser.py fly-in.py visualizer.py`
  ne remonte aucune erreur.
- **mypy** : `mypy --ignore-missing-imports system.py parser.py
  visualizer.py fly-in.py` ne remonte aucune erreur. Les valeurs
  potentiellement `None` (issues des champs `Optional` de pydantic) sont
  vérifiées explicitement avant utilisation plutôt qu'ignorées, afin que
  le code documente aussi les hypothèses qu'il fait sur les données.

### Limites connues

- La boucle de simulation s'arrête automatiquement après 50 tours par
  sécurité ; certaines cartes complexes (voir `maps/challenger/`) peuvent
  ne pas être résolues dans cette limite.
- Le chemin du fichier de carte est codé en dur dans `fly-in.py` : il n'y a
  pas encore d'argument en ligne de commande pour le choisir.
