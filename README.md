# Compta SYSCOHADA v0.1

Logiciel de comptabilité pour Windows (Python + Tkinter + SQLite), conforme au plan comptable
SYSCOHADA révisé. Aucune dépendance : un seul fichier `.exe`.

## Modules
- **Saisie** : écritures OD / banque / caisse (équilibre contrôlé, contrepartie proposée)
- **Achats / Ventes** : factures multi-lignes, TVA (18 % par défaut, modifiable), règlement comptant ou à crédit,
  écritures automatiques (601/4452/401 et 411/701/4431)
- **Règlements** : encaissements clients / paiements fournisseurs, imputation automatique sur les plus anciennes factures
- **Tiers** : clients et fournisseurs avec soldes
- **Articles & stocks** : CMUP, entrées / sorties / inventaire, écriture de variation de stocks (31 / 6031)
- **États** : journal, grand livre, balance, compte de résultat (marge commerciale, résultat d'exploitation,
  financier, HAO, net), bilan actif / passif, tableau de bord
- Export CSV (Excel) de tous les états, sauvegarde de la base, plan comptable extensible

## Obtenir le .exe (GitHub Actions)
1. Créez un dépôt GitHub et envoyez-y ce dossier :
   ```
   git init && git add . && git commit -m "Compta SYSCOHADA v0.1"
   git branch -M main
   git remote add origin https://github.com/VOTRE_COMPTE/compta-syscohada.git
   git push -u origin main
   ```
2. Onglet **Actions** : le workflow *Build Windows EXE* se lance (relancez-le avec *Run workflow* si besoin).
3. Téléchargez `ComptaSyscohada.exe` dans les **Artifacts** de l'exécution.
4. Pour une version publique : `git tag v0.1.0 && git push origin v0.1.0` publie le `.exe` dans **Releases**.

## Lancer / compiler en local
```
python main.py
pip install pyinstaller && pyinstaller --onefile --windowed --name ComptaSyscohada main.py
python -m unittest discover -s tests -v
```

## Données
Base SQLite : `%APPDATA%\ComptaSyscohada\compta.db` (menu *Fichier > Sauvegarder la base*).

## Principes comptables et limites de la v0.1
- Stocks en **inventaire intermittent** (SYSCOHADA) : achats en 601, puis bouton « variation de stocks » qui
  ajuste le compte 311 au stock réel valorisé au CMUP et solde 6031.
- Le bilan est **cumulé** à la date de fin de période ; le résultat n'est pas clôturé (pas d'écriture de
  clôture / report à nouveau automatique).
- Pas encore : avoirs, immobilisations et amortissements, paie, multi-sociétés, impression PDF, utilisateurs.
- Les factures ne sont pas supprimables (piste d'audit) ; seules les saisies manuelles le sont.
- Les états sont des états de gestion : vérifiez avec votre expert-comptable avant dépôt officiel
  (les états financiers SYSCOHADA officiels ont une présentation plus détaillée).
