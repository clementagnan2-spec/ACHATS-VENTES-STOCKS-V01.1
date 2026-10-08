"""Interface graphique Tkinter de Compta SYSCOHADA."""
import csv
import re
import tkinter as tk
from datetime import date
from functools import wraps
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

from . import reports
from .db import (C_BANQUE, C_CAISSE, JOURNAUX, VERSION, Compta, ComptaError, fmt_amount, fmt_date,
                 parse_amount, parse_date, rnd)

TITRE = "Compta SYSCOHADA"


def guard(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except ComptaError as e:
            messagebox.showwarning(TITRE, str(e))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(TITRE, f"{type(e).__name__} : {e}")
    return wrapper


def today():
    return date.today().strftime("%d/%m/%Y")


# --------------------------------------------------------------------------- widgets
class Table(ttk.Frame):
    """Treeview avec défilement, lignes en-tête/total et export CSV."""

    def __init__(self, master, cols, height=12):
        super().__init__(master)
        self.cols = cols
        ids = [f"c{i}" for i in range(len(cols))]
        self.tree = ttk.Treeview(self, columns=ids, show="headings", height=height, selectmode="browse")
        for i, (titre, w, anchor) in enumerate(cols):
            self.tree.heading(ids[i], text=titre)
            self.tree.column(ids[i], width=w, anchor=anchor, stretch=True)
        vs = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.bold = tkfont.nametofont("TkDefaultFont").copy()
        self.bold.configure(weight="bold")
        self.tree.tag_configure("hdr", background="#dde6f3", font=self.bold)
        self.tree.tag_configure("tot", background="#f0f0f0", font=self.bold)

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def add(self, values, tag=""):
        self.tree.insert("", "end", values=list(values), tags=(tag,) if tag else ())

    def selected(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0], "values") if sel else None

    def selected_index(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    @guard
    def export_csv(self, nom="export"):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=nom + ".csv",
                                            filetypes=[("CSV (Excel)", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([c[0] for c in self.cols])
            for iid in self.tree.get_children():
                row = []
                for v in self.tree.item(iid, "values"):
                    v = str(v)
                    row.append(v.replace(" ", "") if re.fullmatch(r"-?\d{1,3}( \d{3})*", v) else v)
                w.writerow(row)
        messagebox.showinfo(TITRE, f"Export terminé :\n{path}")


class Picker(ttk.Combobox):
    """Liste déroulante filtrable associant une clé à un libellé."""

    def __init__(self, master, width=38, **kw):
        super().__init__(master, width=width, **kw)
        self._items, self._l2k = [], {}
        self.bind("<KeyRelease>", self._filter)

    def set_items(self, items):
        self._items = [(str(k), l) for k, l in items]
        self._l2k = {l: k for k, l in self._items}
        self["values"] = [l for _, l in self._items]

    def _filter(self, e):
        if e.keysym in ("Up", "Down", "Return", "Tab", "Left", "Right", "Escape", "Shift_L", "Shift_R"):
            return
        t = self.get().lower()
        self["values"] = [l for _, l in self._items if not t or t in l.lower()]

    def key(self):
        txt = self.get().strip()
        if txt in self._l2k:
            return self._l2k[txt]
        tok = txt.split(" - ")[0].strip()
        return tok if any(k == tok for k, _ in self._items) else None


def account_items(db):
    return [(n, f"{n} - {l}") for n, l in db.liste_comptes()]


def labeled(parent, text, widget, row, col, **grid):
    ttk.Label(parent, text=text).grid(row=row, column=col, sticky="e", padx=(8, 2), pady=3)
    widget.grid(row=row, column=col + 1, sticky="w", padx=(0, 6), pady=3, **grid)
    return widget


# --------------------------------------------------------------------------- onglets
class Tab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=6)
        self.app, self.db = app, app.db

    def refresh(self):
        pass


class Dashboard(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        ttk.Label(self, text="Tableau de bord", font=("", 14, "bold")).pack(anchor="w", pady=(0, 8))
        self.box = ttk.Frame(self)
        self.box.pack(anchor="w")
        self.vals = {}

    def refresh(self):
        d1, d2 = self.app.period()
        for w in self.box.winfo_children():
            w.destroy()
        for i, (lib, val) in enumerate(reports.indicateurs(self.db, d1, d2)):
            f = ttk.LabelFrame(self.box, text=lib, padding=10)
            f.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="nsew")
            ttk.Label(f, text=fmt_amount(val) + " FCFA", font=("", 16, "bold"), width=22).pack()


class Saisie(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.lines = []
        top = ttk.LabelFrame(self, text="Écriture comptable (opérations diverses, banque, caisse)", padding=6)
        top.pack(fill="x")
        self.date = labeled(top, "Date", ttk.Entry(top, width=12), 0, 0)
        self.date.insert(0, today())
        self.journal = labeled(top, "Journal", ttk.Combobox(top, width=8, state="readonly",
                                                             values=["OD", "BQ", "CA"]), 0, 2)
        self.journal.set("OD")
        self.libelle = labeled(top, "Libellé", ttk.Entry(top, width=50), 0, 4)
        self.compte = labeled(top, "Compte", Picker(top, width=48), 1, 0)
        self.debit = labeled(top, "Débit", ttk.Entry(top, width=14), 1, 2)
        self.credit = labeled(top, "Crédit", ttk.Entry(top, width=14), 1, 4)
        ttk.Button(top, text="Ajouter la ligne", command=self.add_line).grid(row=1, column=6, padx=6)
        self.table = Table(self, [("Compte", 90, "w"), ("Libellé du compte", 380, "w"),
                                  ("Débit", 120, "e"), ("Crédit", 120, "e")], height=10)
        self.table.pack(fill="both", expand=True, pady=6)
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.total = ttk.Label(bar, text="")
        self.total.pack(side="left")
        ttk.Button(bar, text="Valider l'écriture", command=self.valider).pack(side="right", padx=4)
        ttk.Button(bar, text="Vider", command=self.vider).pack(side="right", padx=4)
        ttk.Button(bar, text="Supprimer la ligne", command=self.del_line).pack(side="right", padx=4)

    def refresh(self):
        self.compte.set_items(account_items(self.db))

    @guard
    def add_line(self):
        num = self.compte.key()
        if not num:
            raise ComptaError("Choisissez un compte du plan comptable.")
        d, c = parse_amount(self.debit.get()), parse_amount(self.credit.get())
        if (d > 0) == (c > 0):
            raise ComptaError("Saisissez un montant au débit OU au crédit.")
        self.lines.append((num, self.db.compte_libelle(num), rnd(d), rnd(c)))
        self.debit.delete(0, "end")
        self.credit.delete(0, "end")
        self.compte.set("")
        self.draw()
        diff = sum(l[2] for l in self.lines) - sum(l[3] for l in self.lines)
        if diff > 0:
            self.credit.insert(0, str(diff))
        elif diff < 0:
            self.debit.insert(0, str(-diff))

    def draw(self):
        self.table.clear()
        for n, l, d, c in self.lines:
            self.table.add((n, l, fmt_amount(d, True), fmt_amount(c, True)))
        td, tc = sum(l[2] for l in self.lines), sum(l[3] for l in self.lines)
        self.total.config(text=f"Total débit : {fmt_amount(td)}    Total crédit : {fmt_amount(tc)}    "
                               + ("✔ équilibrée" if td == tc and td else "⚠ non équilibrée"))

    def del_line(self):
        i = self.table.selected_index()
        if i is not None:
            del self.lines[i]
            self.draw()

    def vider(self):
        self.lines = []
        self.draw()

    @guard
    def valider(self):
        piece = self.db.post_entry(self.date.get(), self.journal.get(), self.libelle.get().strip(),
                                   [(n, d, c, None) for n, _, d, c in self.lines])
        messagebox.showinfo(TITRE, f"Écriture enregistrée : pièce {piece}")
        self.vider()
        self.libelle.delete(0, "end")
        self.app.refresh_all()


class FactureTab(Tab):
    MODES = {"À crédit": None, "Comptant - Caisse (571)": C_CAISSE, "Comptant - Banque (521)": C_BANQUE}

    def __init__(self, master, app, kind):
        super().__init__(master, app)
        self.kind = kind
        self.lignes = []
        achat = kind == "A"
        top = ttk.LabelFrame(self, text="Nouvelle facture d'achat" if achat else "Nouvelle facture de vente",
                             padding=6)
        top.pack(fill="x")
        self.date = labeled(top, "Date", ttk.Entry(top, width=12), 0, 0)
        self.date.insert(0, today())
        self.tiers = labeled(top, "Fournisseur" if achat else "Client", Picker(top, width=32), 0, 2)
        self.mode = labeled(top, "Règlement", ttk.Combobox(top, width=24, state="readonly",
                                                            values=list(self.MODES)), 0, 4)
        self.mode.set("À crédit")
        self.art = labeled(top, "Article", Picker(top, width=32), 1, 0)
        self.art.bind("<<ComboboxSelected>>", self.on_article)
        self.qte = labeled(top, "Quantité", ttk.Entry(top, width=10), 1, 2)
        self.pu = labeled(top, "Prix unitaire HT", ttk.Entry(top, width=12), 1, 4)
        self.tva = labeled(top, "TVA %", ttk.Entry(top, width=6), 1, 6)
        ttk.Button(top, text="Ajouter la ligne", command=self.add_line).grid(row=1, column=8, padx=6)
        self.table = Table(self, [("Code", 80, "w"), ("Désignation", 240, "w"), ("Qté", 70, "e"),
                                  ("PU HT", 90, "e"), ("TVA %", 60, "e"), ("Montant HT", 110, "e"),
                                  ("TVA", 90, "e"), ("TTC", 110, "e")], height=6)
        self.table.pack(fill="x", pady=6)
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.total = ttk.Label(bar, text="")
        self.total.pack(side="left")
        ttk.Button(bar, text="Valider la facture", command=self.valider).pack(side="right", padx=4)
        ttk.Button(bar, text="Vider", command=self.vider).pack(side="right", padx=4)
        ttk.Button(bar, text="Supprimer la ligne", command=self.del_line).pack(side="right", padx=4)
        ttk.Label(self, text="Factures enregistrées", font=("", 10, "bold")).pack(anchor="w", pady=(8, 0))
        self.hist = Table(self, [("N°", 110, "w"), ("Date", 80, "w"),
                                 ("Fournisseur" if achat else "Client", 220, "w"), ("HT", 100, "e"),
                                 ("TVA", 90, "e"), ("TTC", 100, "e"), ("Réglé", 100, "e"),
                                 ("Reste à payer" if achat else "Reste à encaisser", 120, "e")], height=8)
        self.hist.pack(fill="both", expand=True)

    def refresh(self):
        self.tiers.set_items([(t["id"], f"{t['id']} - {t['nom']}")
                              for t in self.db.tiers_list("F" if self.kind == "A" else "C")])
        self.art.set_items([(a["id"], f"{a['code']} - {a['libelle']}") for a in self.db.articles_list()])
        self.hist.clear()
        for f in self.db.factures(self.kind):
            self.hist.add((f["numero"], fmt_date(f["date"]), f["tiers"], fmt_amount(f["total_ht"]),
                           fmt_amount(f["total_tva"]), fmt_amount(f["total_ttc"]), fmt_amount(f["regle"]),
                           fmt_amount(f["total_ttc"] - f["regle"])))

    def on_article(self, _e=None):
        k = self.art.key()
        if k:
            a = self.db.article(int(k))
            for w, v in ((self.pu, a["prix_achat"] if self.kind == "A" else a["prix_vente"]),
                         (self.tva, a["tva"])):
                w.delete(0, "end")
                w.insert(0, f"{v:g}")
            if not self.qte.get():
                self.qte.insert(0, "1")

    @guard
    def add_line(self):
        k = self.art.key()
        if not k:
            raise ComptaError("Choisissez un article.")
        a = self.db.article(int(k))
        q, pu, tva = parse_amount(self.qte.get()), parse_amount(self.pu.get()), parse_amount(self.tva.get())
        if q <= 0:
            raise ComptaError("Quantité invalide.")
        self.lignes.append((a["id"], a["code"], a["libelle"], q, pu, tva))
        self.qte.delete(0, "end")
        self.art.set("")
        self.draw()

    def draw(self):
        self.table.clear()
        tht = ttva = 0
        for _, code, des, q, pu, tva in self.lignes:
            ht = rnd(q * pu)
            tv = rnd(ht * tva / 100)
            tht, ttva = tht + ht, ttva + tv
            self.table.add((code, des, f"{q:g}", fmt_amount(pu), f"{tva:g}", fmt_amount(ht),
                            fmt_amount(tv), fmt_amount(ht + tv)))
        self.total.config(text=f"HT : {fmt_amount(tht)}    TVA : {fmt_amount(ttva)}    "
                               f"TTC : {fmt_amount(tht + ttva)} FCFA")

    def del_line(self):
        i = self.table.selected_index()
        if i is not None:
            del self.lignes[i]
            self.draw()

    def vider(self):
        self.lignes = []
        self.draw()

    @guard
    def valider(self):
        k = self.tiers.key()
        if not k:
            raise ComptaError("Choisissez un " + ("fournisseur." if self.kind == "A" else "client.")
                              + " (créez-le d'abord dans l'onglet Tiers si besoin)")
        numero = self.db.create_facture(self.kind, self.date.get(), int(k),
                                        [(l[0], l[3], l[4], l[5]) for l in self.lignes],
                                        self.MODES[self.mode.get()])
        messagebox.showinfo(TITRE, f"Facture enregistrée : {numero}")
        self.vider()
        self.app.refresh_all()


class Reglements(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.LabelFrame(self, text="Encaissement client / paiement fournisseur", padding=6)
        top.pack(fill="x")
        self.type = tk.StringVar(value="C")
        f = ttk.Frame(top)
        f.grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(f, text="Client (encaissement)", variable=self.type, value="C",
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Radiobutton(f, text="Fournisseur (paiement)", variable=self.type, value="F",
                        command=self.refresh).pack(side="left", padx=6)
        self.tiers = labeled(top, "Tiers", Picker(top, width=36), 1, 0)
        self.tiers.bind("<<ComboboxSelected>>", lambda e: self.draw_open())
        self.date = labeled(top, "Date", ttk.Entry(top, width=12), 1, 2)
        self.date.insert(0, today())
        self.montant = labeled(top, "Montant", ttk.Entry(top, width=14), 2, 0)
        self.mode = labeled(top, "Mode", ttk.Combobox(top, width=20, state="readonly",
                                                       values=["Caisse (571)", "Banque (521)"]), 2, 2)
        self.mode.set("Caisse (571)")
        ttk.Button(top, text="Enregistrer le règlement", command=self.valider).grid(row=2, column=4, padx=8)
        ttk.Label(self, text="Factures non soldées du tiers (imputation automatique, plus ancienne d'abord)",
                  font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.table = Table(self, [("N°", 120, "w"), ("Date", 90, "w"), ("TTC", 110, "e"),
                                  ("Réglé", 110, "e"), ("Reste", 110, "e")], height=12)
        self.table.pack(fill="both", expand=True)

    def refresh(self):
        self.tiers.set("")
        self.tiers.set_items([(t["id"], f"{t['id']} - {t['nom']}") for t in self.db.tiers_list(self.type.get())])
        self.table.clear()

    def draw_open(self):
        self.table.clear()
        k = self.tiers.key()
        if k:
            for f in self.db.factures_ouvertes(int(k)):
                self.table.add((f["numero"], fmt_date(f["date"]), fmt_amount(f["total_ttc"]),
                                fmt_amount(f["regle"]), fmt_amount(f["total_ttc"] - f["regle"])))

    @guard
    def valider(self):
        k = self.tiers.key()
        if not k:
            raise ComptaError("Choisissez un tiers.")
        tres = C_CAISSE if self.mode.get().startswith("Caisse") else C_BANQUE
        piece = self.db.reglement(self.date.get(), int(k), parse_amount(self.montant.get()), tres)
        messagebox.showinfo(TITRE, f"Règlement enregistré : pièce {piece}")
        self.montant.delete(0, "end")
        self.draw_open()
        self.app.refresh_all()


class TiersTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.LabelFrame(self, text="Nouveau tiers", padding=6)
        top.pack(fill="x")
        self.type = labeled(top, "Type", ttk.Combobox(top, width=12, state="readonly",
                                                       values=["Client", "Fournisseur"]), 0, 0)
        self.type.set("Client")
        self.nom = labeled(top, "Nom", ttk.Entry(top, width=34), 0, 2)
        self.tel = labeled(top, "Téléphone", ttk.Entry(top, width=16), 0, 4)
        self.adr = labeled(top, "Adresse", ttk.Entry(top, width=34), 1, 2)
        ttk.Button(top, text="Ajouter", command=self.add).grid(row=1, column=5, padx=8)
        self.table = Table(self, [("N°", 50, "w"), ("Type", 90, "w"), ("Nom", 240, "w"),
                                  ("Téléphone", 120, "w"), ("Adresse", 240, "w"),
                                  ("Solde (ils nous doivent / nous devons)", 220, "e")])
        self.table.pack(fill="both", expand=True, pady=6)
        ttk.Button(self, text="Exporter en CSV", command=lambda: self.table.export_csv("tiers")).pack(anchor="e")

    def refresh(self):
        self.table.clear()
        for i, t, nom, tel, adr, s in self.db.tiers_soldes():
            self.table.add((i, "Client" if t == "C" else "Fournisseur", nom, tel, adr, fmt_amount(s)))

    @guard
    def add(self):
        self.db.add_tiers("C" if self.type.get() == "Client" else "F", self.nom.get(), self.tel.get(),
                          self.adr.get())
        for w in (self.nom, self.tel, self.adr):
            w.delete(0, "end")
        self.app.refresh_all()


class ArticlesTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.LabelFrame(self, text="Nouvel article", padding=6)
        top.pack(fill="x")
        self.code = labeled(top, "Code", ttk.Entry(top, width=12), 0, 0)
        self.lib = labeled(top, "Désignation", ttk.Entry(top, width=34), 0, 2)
        self.unite = labeled(top, "Unité", ttk.Entry(top, width=8), 0, 4)
        self.unite.insert(0, "U")
        self.pa = labeled(top, "Prix achat HT", ttk.Entry(top, width=12), 1, 0)
        self.pv = labeled(top, "Prix vente HT", ttk.Entry(top, width=12), 1, 2)
        self.tva = labeled(top, "TVA %", ttk.Entry(top, width=8), 1, 4)
        self.tva.insert(0, "18")
        self.nature = labeled(top, "Nature", ttk.Combobox(top, width=22, state="readonly",
                                                           values=["Marchandise (stockée)", "Service (non stocké)"]), 2, 0)
        self.nature.set("Marchandise (stockée)")
        self.nature.bind("<<ComboboxSelected>>", self.on_nature)
        self.ca = labeled(top, "Compte achat", ttk.Entry(top, width=8), 2, 2)
        self.ca.insert(0, "601")
        self.cv = labeled(top, "Compte vente", ttk.Entry(top, width=8), 2, 4)
        self.cv.insert(0, "701")
        ttk.Button(top, text="Ajouter", command=self.add).grid(row=2, column=6, padx=8)
        self.table = Table(self, [("Code", 80, "w"), ("Désignation", 240, "w"), ("Unité", 50, "w"),
                                  ("Quantité", 80, "e"), ("CMUP", 90, "e"), ("Valeur stock", 110, "e"),
                                  ("Prix vente", 90, "e"), ("Stocké", 60, "w")], height=9)
        self.table.pack(fill="both", expand=True, pady=6)
        mv = ttk.LabelFrame(self, text="Mouvement de stock sur l'article sélectionné", padding=6)
        mv.pack(fill="x")
        self.sens = labeled(mv, "Type", ttk.Combobox(mv, width=22, state="readonly",
                                                      values=["Entrée (stock initial, retour)", "Sortie (casse, perte)",
                                                              "Inventaire (quantité comptée)"]), 0, 0)
        self.sens.set("Inventaire (quantité comptée)")
        self.qte = labeled(mv, "Quantité", ttk.Entry(mv, width=10), 0, 2)
        self.cout = labeled(mv, "Coût unitaire", ttk.Entry(mv, width=10), 0, 4)
        self.mdate = labeled(mv, "Date", ttk.Entry(mv, width=12), 0, 6)
        self.mdate.insert(0, today())
        ttk.Button(mv, text="Enregistrer le mouvement", command=self.mouvement).grid(row=0, column=8, padx=6)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 0))
        self.valeur = ttk.Label(bar, text="")
        self.valeur.pack(side="left")
        ttk.Button(bar, text="Générer l'écriture de variation de stocks (31 / 6031)",
                   command=self.variation).pack(side="right")

    def on_nature(self, _e=None):
        service = self.nature.get().startswith("Service")
        for w, v in ((self.ca, "605" if service else "601"), (self.cv, "706" if service else "701")):
            w.delete(0, "end")
            w.insert(0, v)

    def refresh(self):
        self.table.clear()
        for a in self.db.articles_list():
            self.table.add((a["code"], a["libelle"], a["unite"], f"{a['qte']:g}", fmt_amount(a["cmup"]),
                            fmt_amount(a["qte"] * a["cmup"]), fmt_amount(a["prix_vente"]),
                            "Oui" if a["stockable"] else "Non"))
        self.valeur.config(text=f"Valeur du stock (CMUP) : {fmt_amount(self.db.valeur_stock())} FCFA")

    @guard
    def add(self):
        self.db.add_article(self.code.get(), self.lib.get(), self.unite.get(), parse_amount(self.pa.get()),
                            parse_amount(self.pv.get()), parse_amount(self.tva.get(), 18),
                            self.nature.get().startswith("Marchandise"), self.ca.get().strip(),
                            self.cv.get().strip())
        for w in (self.code, self.lib, self.pa, self.pv):
            w.delete(0, "end")
        self.app.refresh_all()

    @guard
    def mouvement(self):
        v = self.table.selected()
        if not v:
            raise ComptaError("Sélectionnez d'abord un article dans la liste.")
        art = self.db.article_by_code(v[0])
        sens = {"E": "E", "S": "S", "I": "I"}[self.sens.get()[0]]
        cout = parse_amount(self.cout.get()) or None
        self.db.mouvement_stock(self.mdate.get(), art["id"], sens, parse_amount(self.qte.get()), cout)
        self.qte.delete(0, "end")
        self.app.refresh_all()

    @guard
    def variation(self):
        piece = self.db.generer_variation_stock(self.app.period()[1])
        messagebox.showinfo(TITRE, "Aucun écart à constater." if piece is None
                            else f"Écriture de variation de stocks passée : pièce {piece}")
        self.app.refresh_all()


class PlanTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Rechercher").pack(side="left")
        self.q = ttk.Entry(top, width=24)
        self.q.pack(side="left", padx=6)
        self.q.bind("<KeyRelease>", lambda e: self.refresh())
        self.table = Table(self, [("Compte", 90, "w"), ("Libellé", 560, "w")], height=18)
        self.table.pack(fill="both", expand=True, pady=6)
        add = ttk.LabelFrame(self, text="Ajouter un compte", padding=6)
        add.pack(fill="x")
        self.num = labeled(add, "Numéro", ttk.Entry(add, width=10), 0, 0)
        self.lib = labeled(add, "Libellé", ttk.Entry(add, width=50), 0, 2)
        ttk.Button(add, text="Ajouter", command=self.add).grid(row=0, column=4, padx=8)

    def refresh(self):
        self.table.clear()
        for n, l in self.db.liste_comptes(self.q.get().strip() or None):
            self.table.add((n, l), "hdr" if len(n) == 2 else "")

    @guard
    def add(self):
        self.db.add_compte(self.num.get(), self.lib.get())
        self.num.delete(0, "end")
        self.lib.delete(0, "end")
        self.app.refresh_all()


class JournalTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Journal").pack(side="left")
        self.j = ttk.Combobox(top, width=26, state="readonly",
                              values=["Tous"] + [f"{k} - {v}" for k, v in JOURNAUX.items()])
        self.j.set("Tous")
        self.j.pack(side="left", padx=6)
        self.j.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="Actualiser", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Exporter en CSV", command=lambda: self.table.export_csv("journal")).pack(side="right")
        ttk.Button(top, text="Supprimer la pièce sélectionnée (saisie manuelle)",
                   command=self.suppr).pack(side="right", padx=6)
        self.table = Table(self, [("Date", 85, "w"), ("Jnl", 40, "w"), ("Pièce", 110, "w"),
                                  ("Compte", 70, "w"), ("Libellé", 360, "w"),
                                  ("Débit", 110, "e"), ("Crédit", 110, "e")], height=20)
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        d1, d2 = self.app.period()
        j = None if self.j.get() == "Tous" else self.j.get()[:2]
        self.table.clear()
        td = tc = 0
        last = None
        for r in self.db.journal(d1, d2, j):
            self.table.add((fmt_date(r["date"]), r["journal"], r["piece"] if r["piece"] != last else "",
                            r["compte"], r["libelle"], fmt_amount(r["debit"], True), fmt_amount(r["credit"], True)))
            last = r["piece"]
            td, tc = td + r["debit"], tc + r["credit"]
        self.table.add(("", "", "", "", "TOTAUX", fmt_amount(td), fmt_amount(tc)), "tot")

    @guard
    def suppr(self):
        v = self.table.selected()
        if not v:
            raise ComptaError("Sélectionnez une ligne de la pièce à supprimer.")
        piece = v[2]
        if not piece:  # ligne secondaire : remonter à la pièce
            items = self.table.tree.get_children()
            idx = self.table.selected_index()
            while idx >= 0 and not self.table.tree.item(items[idx], "values")[2]:
                idx -= 1
            piece = self.table.tree.item(items[idx], "values")[2]
        if messagebox.askyesno(TITRE, f"Supprimer définitivement la pièce {piece} ?"):
            self.db.delete_piece(piece)
            self.app.refresh_all()


class GrandLivreTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Comptes commençant par").pack(side="left")
        self.p = ttk.Entry(top, width=10)
        self.p.pack(side="left", padx=6)
        ttk.Button(top, text="Actualiser", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Exporter en CSV", command=lambda: self.table.export_csv("grand_livre")).pack(side="right")
        self.table = Table(self, [("Date", 85, "w"), ("Pièce", 110, "w"), ("Jnl", 40, "w"),
                                  ("Libellé", 340, "w"), ("Débit", 105, "e"), ("Crédit", 105, "e"),
                                  ("Solde", 115, "e")], height=20)
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        d1, d2 = self.app.period()
        self.table.clear()
        for g in reports.grand_livre(self.db, d1, d2, self.p.get().strip()):
            self.table.add((g["compte"], "", "", g["libelle"], "", "", ""), "hdr")
            if g["report"]:
                self.table.add(("", "", "", "Report (solde antérieur)", "", "", fmt_amount(g["report"])))
            for dt, pc, jn, lb, d, c, s in g["lignes"]:
                self.table.add((fmt_date(dt), pc, jn, lb, fmt_amount(d, True), fmt_amount(c, True), fmt_amount(s)))
            self.table.add(("", "", "", "Total du compte", fmt_amount(g["total_d"]), fmt_amount(g["total_c"]),
                            fmt_amount(g["solde"])), "tot")


class BalanceTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Actualiser", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Exporter en CSV", command=lambda: self.table.export_csv("balance")).pack(side="right")
        self.table = Table(self, [("Compte", 80, "w"), ("Libellé", 340, "w"), ("Total débit", 110, "e"),
                                  ("Total crédit", 110, "e"), ("Solde débiteur", 115, "e"),
                                  ("Solde créditeur", 115, "e")], height=22)
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        d1, d2 = self.app.period()
        self.table.clear()
        tot = [0, 0, 0, 0]
        for c, l, d, cr, sd, sc in reports.balance(self.db, d1, d2):
            self.table.add((c, l, fmt_amount(d), fmt_amount(cr), fmt_amount(sd, True), fmt_amount(sc, True)))
            tot = [tot[0] + d, tot[1] + cr, tot[2] + sd, tot[3] + sc]
        self.table.add(("", "TOTAUX", *[fmt_amount(x) for x in tot]), "tot")


class ResultatTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Actualiser", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Exporter en CSV", command=lambda: self.table.export_csv("compte_de_resultat")).pack(side="right")
        self.table = Table(self, [("Réf", 50, "w"), ("Libellé", 460, "w"), ("Montant (FCFA)", 140, "e")], height=24)
        self.table.pack(fill="both", expand=True, pady=6)

    def refresh(self):
        d1, d2 = self.app.period()
        self.table.clear()
        lignes, _ = reports.compte_resultat(self.db, d1, d2)
        for ref, lib, val, style in lignes:
            self.table.add((ref, lib, fmt_amount(val)), style)


class BilanTab(Tab):
    def __init__(self, master, app):
        super().__init__(master, app)
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Actualiser", command=self.refresh).pack(side="left")
        self.info = ttk.Label(top, text="")
        self.info.pack(side="left", padx=12)
        ttk.Button(top, text="Exporter l'actif", command=lambda: self.actif.export_csv("bilan_actif")).pack(side="right")
        ttk.Button(top, text="Exporter le passif", command=lambda: self.passif.export_csv("bilan_passif")).pack(side="right", padx=6)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure((0, 1), weight=1)
        body.rowconfigure(1, weight=1)
        ttk.Label(body, text="ACTIF", font=("", 11, "bold")).grid(row=0, column=0)
        ttk.Label(body, text="PASSIF", font=("", 11, "bold")).grid(row=0, column=1)
        cols = [("Réf", 45, "w"), ("Libellé", 260, "w"), ("Montant", 110, "e")]
        self.actif, self.passif = Table(body, cols, height=20), Table(body, cols, height=20)
        self.actif.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        self.passif.grid(row=1, column=1, sticky="nsew", padx=(4, 0))

    def refresh(self):
        _, d2 = self.app.period()
        A, P, ta, tp = reports.bilan(self.db, d2)
        for tbl, rows, tot, nom in ((self.actif, A, ta, "TOTAL ACTIF"), (self.passif, P, tp, "TOTAL PASSIF")):
            tbl.clear()
            for ref, lib, val in rows:
                tbl.add((ref, lib, fmt_amount(val)))
            tbl.add(("", nom, fmt_amount(tot)), "tot")
        self.info.config(text=f"Bilan cumulé au {fmt_date(d2)} — "
                              + ("✔ équilibré" if ta == tp else f"⚠ écart de {fmt_amount(ta - tp)}"))


# ------------------------------------------------------------------------- application
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Compta()
        self.geometry("1200x740")
        self.minsize(1000, 600)
        self._titre()
        self._menu()
        bar = ttk.Frame(self, padding=(8, 6))
        bar.pack(fill="x")
        y = date.today().year
        ttk.Label(bar, text="Période du").pack(side="left")
        self.d1 = ttk.Entry(bar, width=12)
        self.d1.insert(0, f"01/01/{y}")
        self.d1.pack(side="left", padx=4)
        ttk.Label(bar, text="au").pack(side="left")
        self.d2 = ttk.Entry(bar, width=12)
        self.d2.insert(0, f"31/12/{y}")
        self.d2.pack(side="left", padx=4)
        ttk.Button(bar, text="Appliquer", command=self.refresh_all).pack(side="left", padx=6)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        for titre, cls, extra in [
            ("Tableau de bord", Dashboard, ()), ("Saisie", Saisie, ()), ("Achats", FactureTab, ("A",)),
            ("Ventes", FactureTab, ("V",)), ("Règlements", Reglements, ()), ("Tiers", TiersTab, ()),
            ("Articles & stocks", ArticlesTab, ()), ("Journal", JournalTab, ()),
            ("Grand livre", GrandLivreTab, ()), ("Balance", BalanceTab, ()),
            ("Compte de résultat", ResultatTab, ()), ("Bilan", BilanTab, ()), ("Plan comptable", PlanTab, ())]:
            self.nb.add(cls(self.nb, self, *extra), text=titre)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())
        self.refresh_all()

    def _titre(self):
        self.title(f"{TITRE} v{VERSION} — {self.db.get_param('societe', 'Ma Société')}")

    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Sauvegarder la base…", command=self.sauvegarde)
        f.add_command(label="Nom de la société…", command=self.societe)
        f.add_separator()
        f.add_command(label="Quitter", command=self.destroy)
        m.add_cascade(label="Fichier", menu=f)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="À propos", command=lambda: messagebox.showinfo(
            TITRE, f"{TITRE} v{VERSION}\nComptabilité SYSCOHADA : saisie, achats, ventes, stocks,\n"
                   f"journal, grand livre, balance, bilan, compte de résultat.\n\nBase : {self.db.path}"))
        m.add_cascade(label="Aide", menu=h)
        self.config(menu=m)

    @guard
    def sauvegarde(self):
        p = filedialog.asksaveasfilename(defaultextension=".db", initialfile=f"sauvegarde_{date.today():%Y%m%d}.db",
                                         filetypes=[("Base SQLite", "*.db")])
        if p:
            self.db.backup(p)
            messagebox.showinfo(TITRE, "Sauvegarde effectuée.")

    def societe(self):
        n = simpledialog.askstring(TITRE, "Nom de la société :", initialvalue=self.db.get_param("societe"))
        if n:
            self.db.set_param("societe", n.strip())
            self._titre()

    def period(self):
        try:
            d1, d2 = parse_date(self.d1.get()), parse_date(self.d2.get())
        except ComptaError as e:
            messagebox.showwarning(TITRE, str(e))
            y = date.today().year
            return f"{y}-01-01", f"{y}-12-31"
        if d1 > d2:
            messagebox.showwarning(TITRE, "La date de début est postérieure à la date de fin.")
        return d1, d2

    def refresh_all(self):
        try:
            tab = self.nametowidget(self.nb.select())
            tab.refresh()
        except tk.TclError:
            pass
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(TITRE, f"{type(e).__name__} : {e}")


def run():
    App().mainloop()
