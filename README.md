# Digital Devil Saga 1 - Traduction Française

Ce dépôt centralise le travail, les scripts et les outils nécessaires à la traduction française du jeu **Shin Megami Tensei: Digital Devil Saga** sur PlayStation 2.

## À propos du projet

L'objectif de ce projet est de proposer une localisation française complète et de qualité pour Digital Devil Saga 1. Le jeu n'ayant jamais bénéficié d'une traduction officielle en français, ce dépôt vise à regrouper les efforts de traduction, l'extraction des textes, et la compilation des scripts modifiés.

Le projet utilise des outils développés sur mesure pour faciliter le travail des traducteurs et garantir une intégration parfaite dans le moteur du jeu.

## Structure du Dépôt

- `dds1_tool/` : L'interface web et les scripts Python de l'outil d'extraction et de traduction.
- `traduction/` : Contient les scripts JSON prêts à être traduits (extraits du jeu).
- `DICTIONNAIRE.md` : Lexique collaboratif pour assurer la cohérence des termes (noms, objets, compétences).
- `Lancer DDS1 Tool.bat` : Script de lancement rapide de l'outil pour Windows.

## L'Outil DDS1 Tool

Un outil sur mesure a été développé pour faciliter la traduction. Il offre une interface visuelle pour extraire l'ISO, éditer les textes et recompiler le tout.

### Prérequis
- Windows
- Python 3.10 ou supérieur

### Installation et Démarrage
1. Clonez ou téléchargez ce dépôt.
2. Placez l'ISO de votre jeu (version Europe) à la racine ou dans un dossier accessible.
3. Double-cliquez sur `Lancer DDS1 Tool.bat`.
4. L'outil s'ouvrira automatiquement dans votre navigateur (sur `http://localhost:8000`).

### Mode d'emploi
1. **Étape A** : Sélectionnez l'ISO du jeu pour extraire les fichiers vitaux.
2. **Étape B** : Décompressez l'archive principale du jeu (`DDS3.IMG`).
3. **Étape C** : Décodez les scripts du jeu. L'outil isolera automatiquement les textes anglais et ignorera les reliquats japonais.
4. **Éditeur** : Utilisez l'interface pour traduire les textes. Le format JSON généré est compatible avec les outils de traduction standards (format `texte_orig` et `texte_fr`).
5. **Sauvegarde** : Les traductions sont sauvegardées directement dans `traduction/scripts/`.

## Licence

Ce projet et ses scripts associés sont distribués sous la licence **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.
Vous êtes libre de partager et d'adapter ce travail à condition de créditer l'auteur original, de ne pas en faire d'utilisation commerciale, et de partager vos modifications sous la même licence.

*Note : Les outils de modding tiers (comme AtlusScriptCompiler) inclus dans ce dépôt restent la propriété de leurs auteurs originaux sous leurs licences respectives.*
