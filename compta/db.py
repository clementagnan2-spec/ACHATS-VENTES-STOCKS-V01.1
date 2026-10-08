"""Moteur comptable : base SQLite, écritures, factures, règlements, stocks."""
import math
import os
import sqlite3
from datetime import date, datetime

from .plan import PLAN

VERSION = "0.1"

JOURNAUX = {
    "AC": "Achats",
    "VT": "Ventes",
    "BQ": "Banque",
    "CA": "Caisse",
    "OD": "Opérations diverses",
}

C_CLIENT = "411"
C_FOURN = "401"
C_TVA_COLL = "4431"
C_TVA_DED = "4452"
C_BANQUE = "521"
C_CAISSE = "571"
C_STOCK = "311"
C_VAR_STOCK = "6031"


class ComptaError(Exception):
    """Erreur fonctionnelle affichable à l'utilisateur."""


def rnd(x):
    """Arrondi commercial à l'entier (le FCFA n'a pas de décimales)."""
    return int(math.floor(x + 0.5))


def parse_date(s):
    if isinstance(s, (date, datetime)):
        return s.strftime("%Y-%m-%d")
    s = str(s).strip()
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ComptaError(f"Date invalide : « {s} » (format attendu JJ/MM/AAAA).")


def fmt_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def fmt_amount(n, blank_zero=False):
    n = rnd(n or 0)
    if n == 0 and blank_zero:
        return ""
    return f"{n:,}".replace(",", " ")


def parse_amount(s, default=0.0):
    s = str(s).strip().replace(" ", "").replace("\u202f", "").replace("\u00a0", "").replace(",", ".")
    if s == "":
        return float(default)
    try:
        return float(s)
    except ValueError:
        raise ComptaError(f"Nombre invalide : « {s} ».")


def default_path():
    p = os.environ.get("COMPTA_DB")
    if p:
        return p
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, "ComptaSyscohada")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "compta.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS parametres(cle TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS comptes(numero TEXT PRIMARY KEY, libelle TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tiers(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('C','F')),
    nom TEXT NOT NULL, telephone TEXT DEFAULT '', adresse TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS articles(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL, libelle TEXT NOT NULL, unite TEXT DEFAULT 'U',
    prix_achat REAL DEFAULT 0, prix_vente REAL DEFAULT 0, tva REAL DEFAULT 18,
    stockable INTEGER DEFAULT 1,
    compte_achat TEXT DEFAULT '601', compte_vente TEXT DEFAULT '701',
    qte REAL DEFAULT 0, cmup REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS factures(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('A','V')),
    numero TEXT UNIQUE NOT NULL, date TEXT NOT NULL,
    tiers_id INTEGER NOT NULL REFERENCES tiers(id),
    total_ht INTEGER, total_tva INTEGER, total_ttc INTEGER, regle INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS facture_lignes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facture_id INTEGER NOT NULL REFERENCES factures(id),
    article_id INTEGER NOT NULL REFERENCES articles(id),
    qte REAL, pu REAL, tva REAL, montant_ht INTEGER);
CREATE TABLE IF NOT EXISTS mouvements_stock(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL, article_id INTEGER NOT NULL REFERENCES articles(id),
    sens TEXT NOT NULL CHECK(sens IN ('E','S')),
    qte REAL NOT NULL, cout REAL DEFAULT 0, motif TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS ecritures(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL, journal TEXT NOT NULL, piece TEXT NOT NULL, libelle TEXT DEFAULT '',
    compte TEXT NOT NULL REFERENCES comptes(numero),
    tiers_id INTEGER REFERENCES tiers(id),
    debit INTEGER NOT NULL DEFAULT 0, credit INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_ec_compte ON ecritures(compte, date);
CREATE INDEX IF NOT EXISTS ix_ec_piece ON ecritures(piece);
CREATE INDEX IF NOT EXISTS ix_ec_tiers ON ecritures(tiers_id);
"""


class Compta:
    def __init__(self, path=None):
        self.path = path or default_path()
        self.cx = sqlite3.connect(self.path)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys=ON")
        self.cx.executescript(SCHEMA)
        self._seed()

    def close(self):
        self.cx.close()

    def _seed(self):
        if self.cx.execute("SELECT COUNT(*) FROM comptes").fetchone()[0] == 0:
            with self.cx:
                self.cx.executemany("INSERT INTO comptes(numero, libelle) VALUES (?,?)", PLAN)
                self.cx.execute("INSERT OR IGNORE INTO parametres VALUES ('societe','Ma Société')")

    # ------------------------------------------------------------ paramètres
    def get_param(self, cle, defaut=""):
        r = self.cx.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,)).fetchone()
        return r[0] if r else defaut

    def set_param(self, cle, valeur):
        with self.cx:
            self.cx.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)", (cle, valeur))

    def backup(self, dest):
        out = sqlite3.connect(dest)
        try:
            self.cx.backup(out)
        finally:
            out.close()

    # ---------------------------------------------------------------- comptes
    def liste_comptes(self, search=None):
        q, p = "SELECT numero, libelle FROM comptes", ()
        if search:
            q += " WHERE numero LIKE ? OR libelle LIKE ?"
            p = (search + "%", "%" + search + "%")
        return [(r[0], r[1]) for r in self.cx.execute(q + " ORDER BY numero", p)]

    def libelles(self):
        return {r[0]: r[1] for r in self.cx.execute("SELECT numero, libelle FROM comptes")}

    def compte_libelle(self, numero):
        r = self.cx.execute("SELECT libelle FROM comptes WHERE numero=?", (numero,)).fetchone()
        return r[0] if r else None

    def add_compte(self, numero, libelle):
        numero, libelle = str(numero).strip(), str(libelle).strip()
        if not numero.isdigit() or len(numero) < 2 or numero[0] not in "12345678":
            raise ComptaError("Le numéro de compte doit comporter au moins 2 chiffres (classes 1 à 8).")
        if not libelle:
            raise ComptaError("Le libellé du compte est obligatoire.")
        try:
            with self.cx:
                self.cx.execute("INSERT INTO comptes VALUES (?,?)", (numero, libelle))
        except sqlite3.IntegrityError:
            raise ComptaError(f"Le compte {numero} existe déjà.")

    # ------------------------------------------------------------------ tiers
    def tiers_list(self, type_=None):
        q, p = "SELECT * FROM tiers", ()
        if type_:
            q, p = q + " WHERE type=?", (type_,)
        return self.cx.execute(q + " ORDER BY nom", p).fetchall()

    def add_tiers(self, type_, nom, tel="", adresse=""):
        if type_ not in ("C", "F") or not nom.strip():
            raise ComptaError("Type et nom du tiers obligatoires.")
        with self.cx:
            cur = self.cx.execute("INSERT INTO tiers(type, nom, telephone, adresse) VALUES (?,?,?,?)",
                                  (type_, nom.strip(), tel.strip(), adresse.strip()))
        return cur.lastrowid

    def tiers_soldes(self):
        """Solde positif : le client nous doit / nous devons au fournisseur."""
        rows = self.cx.execute(
            """SELECT t.id, t.type, t.nom, t.telephone, t.adresse,
                      COALESCE(SUM(e.debit - e.credit), 0) AS s
               FROM tiers t LEFT JOIN ecritures e ON e.tiers_id = t.id
               GROUP BY t.id ORDER BY t.nom""").fetchall()
        return [(r["id"], r["type"], r["nom"], r["telephone"], r["adresse"],
                 r["s"] if r["type"] == "C" else -r["s"]) for r in rows]

    # --------------------------------------------------------------- articles
    def articles_list(self):
        return self.cx.execute("SELECT * FROM articles ORDER BY code").fetchall()

    def article(self, art_id):
        r = self.cx.execute("SELECT * FROM articles WHERE id=?", (art_id,)).fetchone()
        if not r:
            raise ComptaError("Article introuvable.")
        return r

    def article_by_code(self, code):
        return self.cx.execute("SELECT * FROM articles WHERE code=?", (code,)).fetchone()

    def add_article(self, code, libelle, unite="U", prix_achat=0, prix_vente=0, tva=18,
                    stockable=True, compte_achat="601", compte_vente="701"):
        code, libelle = code.strip(), libelle.strip()
        if not code or not libelle:
            raise ComptaError("Code et désignation obligatoires.")
        for c in (compte_achat, compte_vente):
            if self.compte_libelle(c) is None:
                raise ComptaError(f"Le compte {c} n'existe pas dans le plan comptable.")
        try:
            with self.cx:
                cur = self.cx.execute(
                    """INSERT INTO articles(code, libelle, unite, prix_achat, prix_vente, tva,
                       stockable, compte_achat, compte_vente) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (code, libelle, unite or "U", prix_achat, prix_vente, tva,
                     1 if stockable else 0, compte_achat, compte_vente))
        except sqlite3.IntegrityError:
            raise ComptaError(f"Le code article « {code} » existe déjà.")
        return cur.lastrowid

    # --------------------------------------------------------------- écritures
    def _next_piece(self, prefix, iso_date):
        year = iso_date[:4]
        pat = f"{prefix}{year}-"
        n = self.cx.execute("SELECT COUNT(DISTINCT piece) FROM ecritures WHERE piece LIKE ?",
                            (pat + "%",)).fetchone()[0]
        return f"{pat}{n + 1:05d}"

    def _insert_entry(self, iso_date, journal, piece, libelle, lines):
        lines = [(str(c).strip(), rnd(d or 0), rnd(cr or 0), t) for c, d, cr, t in lines]
        if len(lines) < 2:
            raise ComptaError("Une écriture comporte au moins deux lignes.")
        for c, d, cr, _ in lines:
            if self.compte_libelle(c) is None:
                raise ComptaError(f"Compte inconnu : {c}")
            if c[0] not in "12345678":
                raise ComptaError(f"Compte {c} : seules les classes 1 à 8 sont imputables.")
            if d < 0 or cr < 0 or (d and cr) or (not d and not cr):
                raise ComptaError(f"Ligne invalide sur le compte {c} (un seul montant positif par ligne).")
        td, tc = sum(l[1] for l in lines), sum(l[2] for l in lines)
        if td != tc:
            raise ComptaError(f"Écriture déséquilibrée : débit {fmt_amount(td)} ≠ crédit {fmt_amount(tc)}.")
        self.cx.executemany(
            """INSERT INTO ecritures(date, journal, piece, libelle, compte, tiers_id, debit, credit)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(iso_date, journal, piece, libelle, c, t, d, cr) for c, d, cr, t in lines])

    def post_entry(self, date_, journal, libelle, lines):
        """lines : [(compte, debit, credit, tiers_id|None)]. Retourne le numéro de pièce."""
        iso = parse_date(date_)
        if journal not in ("OD", "BQ", "CA"):
            raise ComptaError("La saisie manuelle se fait dans les journaux OD, BQ ou CA.")
        with self.cx:
            piece = self._next_piece(journal, iso)
            self._insert_entry(iso, journal, piece, libelle, lines)
        return piece

    def delete_piece(self, piece):
        if piece[:2] not in ("OD", "BQ", "CA"):
            raise ComptaError("Seules les pièces saisies manuellement (OD, BQ, CA) peuvent être supprimées.")
        with self.cx:
            self.cx.execute("DELETE FROM ecritures WHERE piece=?", (piece,))

    def journal(self, d1=None, d2=None, journal=None):
        q, p = "SELECT * FROM ecritures WHERE 1=1", []
        if d1:
            q, p = q + " AND date>=?", p + [d1]
        if d2:
            q, p = q + " AND date<=?", p + [d2]
        if journal:
            q, p = q + " AND journal=?", p + [journal]
        return self.cx.execute(q + " ORDER BY date, piece, id", p).fetchall()

    def totaux(self, d1=None, d2=None):
        q, p = "SELECT compte, SUM(debit) d, SUM(credit) c FROM ecritures WHERE 1=1", []
        if d1:
            q, p = q + " AND date>=?", p + [d1]
        if d2:
            q, p = q + " AND date<=?", p + [d2]
        return {r["compte"]: (r["d"] or 0, r["c"] or 0)
                for r in self.cx.execute(q + " GROUP BY compte", p)}

    # --------------------------------------------------------------- règlements
    def _reglement(self, iso, tiers_id, montant, tresor, libelle=""):
        montant = rnd(montant)
        if montant <= 0:
            raise ComptaError("Le montant du règlement doit être positif.")
        if tresor not in (C_BANQUE, C_CAISSE):
            raise ComptaError("Mode de règlement invalide.")
        t = self.cx.execute("SELECT * FROM tiers WHERE id=?", (tiers_id,)).fetchone()
        if not t:
            raise ComptaError("Tiers introuvable.")
        journal = "CA" if tresor == C_CAISSE else "BQ"
        piece = self._next_piece("RG", iso)
        if t["type"] == "C":
            lines = [(tresor, montant, 0, None), (C_CLIENT, 0, montant, tiers_id)]
            lib = libelle or f"Règlement client {t['nom']}"
        else:
            lines = [(C_FOURN, montant, 0, tiers_id), (tresor, 0, montant, None)]
            lib = libelle or f"Règlement fournisseur {t['nom']}"
        self._insert_entry(iso, journal, piece, lib, lines)
        # imputation automatique sur les factures les plus anciennes
        reste = montant
        typ = "V" if t["type"] == "C" else "A"
        for f in self.cx.execute(
                "SELECT id, total_ttc, regle FROM factures WHERE tiers_id=? AND type=? "
                "AND regle<total_ttc ORDER BY date, id", (tiers_id, typ)).fetchall():
            if reste <= 0:
                break
            part = min(reste, f["total_ttc"] - f["regle"])
            self.cx.execute("UPDATE factures SET regle=regle+? WHERE id=?", (part, f["id"]))
            reste -= part
        return piece

    def reglement(self, date_, tiers_id, montant, tresor, libelle=""):
        iso = parse_date(date_)
        with self.cx:
            return self._reglement(iso, tiers_id, montant, tresor, libelle)

    # ------------------------------------------------------------------ stocks
    def _maj_stock(self, art_id, iso, sens, qte, cout, motif):
        art = self.article(art_id)
        q, cm = art["qte"], art["cmup"]
        if sens == "E":
            nq = q + qte
            ncm = ((q * cm) + (qte * cout)) / nq if nq > 0 else cout
        else:
            if qte > q + 1e-9:
                raise ComptaError(f"Stock insuffisant pour « {art['libelle']} » (disponible : {q:g}).")
            nq, ncm = q - qte, cm
        self.cx.execute("UPDATE articles SET qte=?, cmup=? WHERE id=?", (nq, ncm, art_id))
        self.cx.execute("INSERT INTO mouvements_stock(date, article_id, sens, qte, cout, motif) "
                        "VALUES (?,?,?,?,?,?)", (iso, art_id, sens, qte, cout, motif))

    def mouvement_stock(self, date_, art_id, sens, qte, cout=None, motif=""):
        """sens : 'E' entrée, 'S' sortie, 'I' inventaire (qte = quantité comptée)."""
        iso = parse_date(date_)
        art = self.article(art_id)
        if not art["stockable"]:
            raise ComptaError("Cet article n'est pas géré en stock.")
        if qte < 0 or (qte == 0 and sens != "I"):
            raise ComptaError("Quantité invalide.")
        with self.cx:
            if sens == "I":
                diff = qte - art["qte"]
                if diff > 0:
                    self._maj_stock(art_id, iso, "E", diff, cout or art["cmup"] or art["prix_achat"],
                                    motif or "Inventaire (écart +)")
                elif diff < 0:
                    self._maj_stock(art_id, iso, "S", -diff, art["cmup"], motif or "Inventaire (écart -)")
            elif sens == "E":
                c = cout if cout else (art["cmup"] or art["prix_achat"])
                self._maj_stock(art_id, iso, "E", qte, c, motif or "Entrée de stock")
            elif sens == "S":
                self._maj_stock(art_id, iso, "S", qte, art["cmup"], motif or "Sortie de stock")
            else:
                raise ComptaError("Type de mouvement invalide.")

    def valeur_stock(self):
        r = self.cx.execute("SELECT COALESCE(SUM(qte*cmup),0) FROM articles WHERE stockable=1").fetchone()
        return rnd(r[0])

    def generer_variation_stock(self, date_):
        """Inventaire intermittent SYSCOHADA : ajuste le compte 31 au stock réel valorisé au CMUP
        et constate la variation de stocks (6031). Retourne la pièce ou None si aucun écart."""
        iso = parse_date(date_)
        valeur = self.valeur_stock()
        r = self.cx.execute("SELECT COALESCE(SUM(debit-credit),0) FROM ecritures "
                            "WHERE compte LIKE '31%' AND date<=?", (iso,)).fetchone()
        diff = valeur - rnd(r[0])
        if diff == 0:
            return None
        with self.cx:
            piece = self._next_piece("OD", iso)
            if diff > 0:
                lines = [(C_STOCK, diff, 0, None), (C_VAR_STOCK, 0, diff, None)]
            else:
                lines = [(C_VAR_STOCK, -diff, 0, None), (C_STOCK, 0, -diff, None)]
            self._insert_entry(iso, "OD", piece, "Variation de stocks de marchandises (inventaire)", lines)
        return piece

    # ----------------------------------------------------------------- factures
    def create_facture(self, kind, date_, tiers_id, lignes, reglement=None):
        """kind 'A' achat / 'V' vente ; lignes [(article_id, qte, pu, tva%)] ;
        reglement None (à crédit), '571' (caisse) ou '521' (banque)."""
        iso = parse_date(date_)
        if kind not in ("A", "V"):
            raise ComptaError("Type de facture invalide.")
        if not lignes:
            raise ComptaError("La facture ne contient aucune ligne.")
        tiers = self.cx.execute("SELECT * FROM tiers WHERE id=?", (tiers_id,)).fetchone()
        if not tiers or tiers["type"] != ("F" if kind == "A" else "C"):
            raise ComptaError("Choisissez un " + ("fournisseur." if kind == "A" else "client."))
        with self.cx:
            ht_par_compte, tot_ht, tot_tva, prep = {}, 0, 0, []
            for art_id, qte, pu, tva in lignes:
                if qte <= 0 or pu < 0 or tva < 0:
                    raise ComptaError("Quantité, prix ou TVA invalide.")
                art = self.article(art_id)
                ht = rnd(qte * pu)
                tv = rnd(ht * tva / 100.0)
                compte = art["compte_achat"] if kind == "A" else art["compte_vente"]
                ht_par_compte[compte] = ht_par_compte.get(compte, 0) + ht
                tot_ht += ht
                tot_tva += tv
                prep.append((art_id, qte, pu, tva, ht, art))
            tot_ttc = tot_ht + tot_tva
            if tot_ttc <= 0:
                raise ComptaError("Le montant de la facture est nul.")
            pref = "FA" if kind == "A" else "FV"
            numero = self._next_piece(pref, iso)
            cur = self.cx.execute(
                "INSERT INTO factures(type, numero, date, tiers_id, total_ht, total_tva, total_ttc) "
                "VALUES (?,?,?,?,?,?,?)", (kind, numero, iso, tiers_id, tot_ht, tot_tva, tot_ttc))
            fid = cur.lastrowid
            for art_id, qte, pu, tva, ht, art in prep:
                self.cx.execute("INSERT INTO facture_lignes(facture_id, article_id, qte, pu, tva, montant_ht) "
                                "VALUES (?,?,?,?,?,?)", (fid, art_id, qte, pu, tva, ht))
                if art["stockable"]:
                    if kind == "A":
                        self._maj_stock(art_id, iso, "E", qte, pu, f"Achat {numero}")
                    else:
                        self._maj_stock(art_id, iso, "S", qte, art["cmup"], f"Vente {numero}")
            if kind == "V":
                lines = [(C_CLIENT, tot_ttc, 0, tiers_id)]
                lines += [(c, 0, m, None) for c, m in ht_par_compte.items() if m]
                if tot_tva:
                    lines.append((C_TVA_COLL, 0, tot_tva, None))
                self._insert_entry(iso, "VT", numero, f"Facture de vente {numero} - {tiers['nom']}", lines)
            else:
                lines = [(c, m, 0, None) for c, m in ht_par_compte.items() if m]
                if tot_tva:
                    lines.append((C_TVA_DED, tot_tva, 0, None))
                lines.append((C_FOURN, 0, tot_ttc, tiers_id))
                self._insert_entry(iso, "AC", numero, f"Facture d'achat {numero} - {tiers['nom']}", lines)
            if reglement:
                self._reglement(iso, tiers_id, tot_ttc, reglement, f"Règlement comptant {numero}")
        return numero

    def factures(self, kind):
        return self.cx.execute(
            """SELECT f.*, t.nom AS tiers FROM factures f JOIN tiers t ON t.id=f.tiers_id
               WHERE f.type=? ORDER BY f.date DESC, f.id DESC""", (kind,)).fetchall()

    def factures_ouvertes(self, tiers_id):
        return self.cx.execute("SELECT * FROM factures WHERE tiers_id=? AND regle<total_ttc "
                               "ORDER BY date, id", (tiers_id,)).fetchall()
