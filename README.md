# DDS1 Tool — Digital Devil Saga Translation Tool

> Outil complet d'extraction, décompilation et traduction du jeu **Shin Megami Tensei: Digital Devil Saga** (version européenne, PS2, SLES_534.58).

---

## 🎮 À propos du projet

Ce projet vise à produire une traduction française de *Digital Devil Saga 1* sur PS2.  
L'outil développé ici permet d'extraire les scripts du jeu, de les éditer, et de les réinjecter dans le binaire pour tester la traduction directement dans PCSX2.

---

## 🛠️ Architecture de l'outil

```
dds1_tool/
├── backend/
│   ├── server.py                  # API FastAPI (serveur local)
│   ├── core/
│   │   ├── ddt_img.py             # Parseur d'archive DDS3.DDT / DDS3.IMG
│   │   ├── script_manager.py      # Décompilateur / Recompilateur de scripts Atlus
│   │   ├── iso_handler.py         # Extraction des fichiers depuis l'ISO PS2
│   │   ├── hostfs.py              # Générateur de patch HostFS PCSX2
│   │   └── validator.py           # Validation des traductions
│   ├── tools/
│   │   ├── dotnet/                # Runtime .NET 8 portable (bundlé)
│   │   ├── AtlusScriptCompiler.dll  # Compilateur officiel Atlus
│   │   └── Charsets/              # Tables de caractères connues
│   └── static/
│       └── index.html             # Interface Web (vanilla HTML/CSS/JS)
└── README.md
```

---

## 🔄 Workflow

### Étape A — Extraction ISO
Extrait depuis l'ISO les 3 fichiers essentiels :
- `SLES_534.58` — Exécutable PS2
- `DDS3.DDT` — Index de l'archive (table des matières)
- `DDS3.IMG` — Conteneur de données (~1.4 Go)

### Étape B — Extraction DDS3
L'archive DDS3 utilise un **arbre binaire de 12 bytes par nœud** :

| Champ | Taille | Description |
|---|---|---|
| `name_offset` | 4 bytes uint | Pointeur vers le nom dans le DDT |
| `location` | 4 bytes uint | Secteur de départ dans DDS3.IMG |
| `size` | 4 bytes int signé | **Négatif** = dossier (abs = nb d'enfants) / **Positif** = taille en bytes |

Résultat : **7 664 fichiers dans 604 dossiers**, dont 143 scripts `.bf` et 15 fichiers `.bmd`.

### Étape C — Décompilation des scripts
Utilise [AtlusScriptCompiler](https://github.com/TGEnigma/AtlusScriptTools) pour décompiler les scripts binaires `.bf` / `.bmd` en JSON éditables.

---

## 📁 Structure de travail (Work Dir)

```
work dds/
├── SLES_534.58        ← Exécutable PS2 (Étape A)
├── DDS3.DDT           ← Index archive (Étape A)
├── DDS3.IMG           ← Archive données (Étape A)
├── dds3data/          ← Fichiers extraits (Étape B)
│   ├── battle/
│   │   └── script/*.bmd
│   ├── event/
│   │   └── eXXX/*/scr/*.bf
│   └── ...
└── traduction/
    └── scripts/       ← JSONs éditables (Étape C)
        ├── battle/script/
        └── event/
```

---

## 🚀 Lancer l'outil

```powershell
# Prérequis : Python 3.10+
cd dds1_tool
pip install fastapi uvicorn python-multipart

python backend/server.py
# → Ouvrir http://localhost:8000
```

Le runtime **.NET 8** et **AtlusScriptCompiler** sont bundlés — aucune installation externe requise.

---

## 🔍 Notes techniques

### Format des scripts Atlus (BMD / BF)

- **`.bf`** (FlowScript) : Logique de jeu — conditions, appels de fonctions, cinématiques. Décompile en pseudo-C lisible.
- **`.bmd`** (MessageScript) : Textes de dialogues. Format propriétaire Atlus avec table de pointeurs.

### Encodage du texte

La version européenne utilise le **même encodage que la version américaine** (ASCII standard).  
Les fichiers `.bmd` présents dans l'archive sont des **artéfacts de développement japonais** laissés par Atlus, pas les dialogues finaux du jeu.

---

## 🎯 Roadmap

- [x] Extraction correcte de l'arbre DDS3 (7 664 fichiers, 604 dossiers)
- [x] Décompilation des scripts `.bf` / `.bmd` via AtlusScriptCompiler
- [x] Interface Web d'édition des scripts JSON
- [x] Sauvegarde et réinjection des traductions
- [x] Patch HostFS pour test dans PCSX2 sans recompiler l'ISO
- [ ] Localisation de tous les fichiers de dialogue finaux
- [ ] Traduction française complète
- [ ] Recompilation ISO finale

---

## 📚 Ressources

- [AtlusScriptTools](https://github.com/TGEnigma/AtlusScriptTools) — Compilateur Atlus
- [Nocturne-Randomizer](https://github.com/nmarkro/Nocturne-Randomizer) — Référence du format DDS3FS
- [PCSX2](https://pcsx2.net/) — Émulateur PS2 utilisé pour les tests

---

## 📝 Licence

Projet de fan non-commercial. *Digital Devil Saga* © Atlus / SEGA.
