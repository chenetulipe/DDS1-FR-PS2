# Digital Devil Saga 1 FR — Audio & Translation Lab

Cet outil permet d'extraire, de traduire et de recompiler les textes du jeu **Shin Megami Tensei: Digital Devil Saga 1** (Version Européenne, SLES_534.58).

---

## Architecture du projet

```
dds1_tool/
├── backend/
│   ├── app.py                   # Serveur Flask (API REST + UI)
│   ├── core/
│   │   ├── ddt_img.py           # Parseur de l'archive DDS3.DDT / DDS3.IMG
│   │   └── script_manager.py   # Décompilateur / Recompilateur de scripts
│   ├── tools/
│   │   ├── dotnet/              # Runtime .NET 8 portable (bundlé, aucune install requise)
│   │   ├── AtlusScriptCompiler.dll  # Compilateur officiel des scripts Atlus
│   │   └── Charsets/           # Tables de caractères connues (P3, P4, P5...)
│   └── static/
│       └── index.html           # Interface Web (HTML/JS/CSS, aucune dépendance externe)
└── README.md                    # Ce fichier
```

---

## Comment ça marche

### Étape A — Extraction de l'ISO
Analyse le fichier `.iso` du jeu pour extraire les 3 fichiers vitaux :
- `SLES_534.58` — l'exécutable PS2
- `DDS3.DDT` — la table des matières (index de l'archive)
- `DDS3.IMG` — le conteneur massif de données (~1.4 Go)

### Étape B — Extraction de l'archive DDS3
Le module `ddt_img.py` lit le format **DDS3** (moteur Atlus PS2, commun à Nocturne, DDS1, DDS2).

**Format du DDT :** Arbre binaire de 12 bytes par nœud :
| Champ | Taille | Description |
|---|---|---|
| `name_offset` | 4 bytes (uint) | Pointeur vers le nom du fichier dans le DDT |
| `location` | 4 bytes (uint) | Secteur de départ dans le DDS3.IMG |
| `size` | 4 bytes (int signé) | **Si négatif** → dossier (`abs = nb d'enfants`) ; **Si positif** → taille fichier en bytes |

L'extracteur parcourt l'arbre récursivement et recrée la structure de dossiers d'origine sous `work dds/dds3data/` :
```
dds3data/
├── battle/script/0x46.bmd
├── battle/script/nego.bf
├── event/e500/e501/scr/e501.bf
├── event/e700/e703/scr/e703.bf    ← les vrais dialogues !
└── ...
```

**Résultat :** 7 664 fichiers dans 604 dossiers, dont **158 scripts** `.bf` / `.bmd`.

### Étape C — Décompilation des Scripts
Le module `script_manager.py` utilise **AtlusScriptCompiler** (via .NET 8) pour décompiler les scripts binaires. L'outil :
1. Passe en revue tous les `.bmd`/`.bf` de manière récursive dans `dds3data/`
2. Décompile chaque fichier en `.msg` (format texte intermédiaire Atlus)
3. Parse le `.msg` pour extraire uniquement les blocs de dialogue
4. Génère un fichier `.json` par script, en préservant la structure de dossiers

Les JSON sont sauvegardés dans `work dds/traduction/scripts/` avec la même arborescence.

### Éditeur Web
L'interface Web (Flask + HTML/JS pur) permet :
- De parcourir et sélectionner les fichiers JSON de scripts
- De voir le texte original en clair et de saisir la traduction
- De sauvegarder : le JSON est recompilé en `.bmd` binaire via `AtlusScriptCompiler`

---

## Encodage du texte (version européenne)

La version européenne (Ghostlight) utilise l'**encodage standard anglais** — le même que la version américaine. Les scripts contiennent du vrai texte ASCII lisible directement.

Les rares fichiers en japonais (`[x 0x81 0xB9]...`) sont des **artefacts de développement** laissés par Atlus dans l'archive et ne font pas partie du script du jeu final.

Pour la **traduction française**, les accents courants sont mappés dans `script_manager.py` :
| Caractère | Code interne |
|---|---|
| é | `[x 0x82 0xA0]` |
| è | `[x 0x82 0xA1]` |
| à | `[x 0x82 0xA2]` |
| ç | `[x 0x82 0xA3]` |
| ... | ... |

---

## Lancer l'outil

```powershell
# Depuis le dossier dds1_tool/
python backend/app.py
# Puis ouvrir http://localhost:5000 dans un navigateur
```

---

## Environnement requis

- **Python 3.10+** (Windows)
- **Aucune installation externe** : le runtime .NET 8 et AtlusScriptCompiler sont **bundlés** dans `backend/tools/`
