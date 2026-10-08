"""États comptables : grand livre, balance, compte de résultat, bilan, indicateurs."""


def grand_livre(db, d1, d2, prefix=""):
    """Retourne une liste de dicts : compte, libelle, report, lignes, total_d, total_c, solde."""
    lib = db.libelles()
    avant = db.totaux(None, _veille(d1)) if d1 else {}
    mouv = {}
    for r in db.journal(d1, d2):
        if r["compte"].startswith(prefix):
            mouv.setdefault(r["compte"], []).append(r)
    comptes = sorted(mouv)
    out = []
    for c in comptes:
        d0, c0 = avant.get(c, (0, 0))
        solde = report = d0 - c0
        lignes, td, tc = [], 0, 0
        for r in mouv[c]:
            solde += r["debit"] - r["credit"]
            td += r["debit"]
            tc += r["credit"]
            lignes.append((r["date"], r["piece"], r["journal"], r["libelle"], r["debit"], r["credit"], solde))
        out.append({"compte": c, "libelle": lib.get(c, ""), "report": report, "lignes": lignes,
                    "total_d": td, "total_c": tc, "solde": solde})
    return out


def _veille(iso):
    from datetime import datetime, timedelta
    return (datetime.strptime(iso, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def balance(db, d1, d2):
    t, lib = db.totaux(d1, d2), db.libelles()
    rows = []
    for c in sorted(t):
        d, cr = t[c]
        s = d - cr
        rows.append((c, lib.get(c, ""), d, cr, s if s > 0 else 0, -s if s < 0 else 0))
    return rows


def _helpers(t):
    def match(k, pref, excl):
        return k.startswith(tuple(pref)) and not (excl and k.startswith(tuple(excl)))

    def cr(pref, excl=()):   # solde créditeur net (C - D)
        return sum(c - d for k, (d, c) in t.items() if match(k, pref, excl))

    def dr(pref, excl=()):   # solde débiteur net (D - C)
        return sum(d - c for k, (d, c) in t.items() if match(k, pref, excl))

    def pos(pref, excl=()):  # somme des soldes débiteurs compte par compte
        return sum(max(d - c, 0) for k, (d, c) in t.items() if match(k, pref, excl))

    def neg(pref, excl=()):  # somme des soldes créditeurs compte par compte
        return sum(max(c - d, 0) for k, (d, c) in t.items() if match(k, pref, excl))

    return cr, dr, pos, neg


def compte_resultat(db, d1, d2):
    """Retourne (lignes, résultat net). Ligne = (ref, libellé, montant, style) ; style '' ou 'tot'.
    Les charges sont affichées en négatif."""
    t = db.totaux(d1, d2)
    cr, dr, _, _ = _helpers(t)
    L = []

    def add(ref, lib, val, style=""):
        L.append((ref, lib, val, style))
        return val

    ta = add("TA", "Ventes de marchandises", cr(["701"]))
    ra = add("RA", "Achats de marchandises", -dr(["601"]))
    rb = add("RB", "Variation de stocks de marchandises", -dr(["6031"]))
    xa = add("XA", "MARGE COMMERCIALE", ta + ra + rb, "tot")
    tb = add("TB", "Ventes de produits fabriqués, travaux et services", cr(["70"], ["701"]))
    tc = add("TC", "Production stockée ou immobilisée", cr(["72", "73"]))
    td = add("TD", "Subventions d'exploitation", cr(["71"]))
    te = add("TE", "Autres produits et reprises", cr(["74", "75", "76", "78", "79"]))
    rc = add("RC", "Achats de matières et fournitures (et variations)", -dr(["60"], ["601", "6031"]))
    rd = add("RD", "Transports", -dr(["61"]))
    re_ = add("RE", "Services extérieurs", -dr(["62", "63"]))
    rf = add("RF", "Impôts et taxes", -dr(["64"]))
    rg = add("RG", "Autres charges", -dr(["65"]))
    rh = add("RH", "Charges de personnel", -dr(["66"]))
    ri = add("RI", "Dotations aux amortissements et provisions", -dr(["68", "69"]))
    xb = add("XB", "RÉSULTAT D'EXPLOITATION", xa + tb + tc + td + te + rc + rd + re_ + rf + rg + rh + ri, "tot")
    tj = add("TJ", "Revenus financiers", cr(["77"]))
    rj = add("RJ", "Frais financiers", -dr(["67"]))
    xc = add("XC", "RÉSULTAT FINANCIER", tj + rj, "tot")
    xd = add("XD", "RÉSULTAT DES ACTIVITÉS ORDINAIRES", xb + xc, "tot")
    tk = add("TK", "Produits hors activités ordinaires (HAO)", cr(["82", "84", "86", "88"]))
    rm = add("RM", "Charges hors activités ordinaires (HAO)", -dr(["81", "83", "85"]))
    xe = add("XE", "RÉSULTAT HAO", tk + rm, "tot")
    rk = add("RK", "Participation des travailleurs", -dr(["87"]))
    rl = add("RL", "Impôts sur le résultat", -dr(["89"]))
    net = xd + xe + rk + rl
    direct = cr(["6", "7", "8"])
    if direct != net:
        net += add("ZZ", "Comptes non classés (écart)", direct - net)
    add("XG", "RÉSULTAT NET", net, "tot")
    return L, net


def bilan(db, d2):
    """Bilan cumulé à la date d2. Retourne (actif, passif, total_actif, total_passif)."""
    t = db.totaux(None, d2)
    cr, dr, pos, neg = _helpers(t)
    resultat = cr(["6", "7", "8"])
    A, P = [], []

    imm_inc = dr(["21", "281", "291"])
    imm_cor = dr(["22", "23", "24", "25", "282", "283", "284", "292", "293", "294"])
    imm_fin = dr(["26", "27", "296", "297"])
    imm_aut = dr(["2"]) - imm_inc - imm_cor - imm_fin
    st_m = dr(["31"])
    st_d = dr(["39"])
    st_a = dr(["3"]) - st_m - st_d
    tresor_pos = pos(["5"], ["59"])
    actif = [
        ("AD", "Immobilisations incorporelles (net)", imm_inc),
        ("AE", "Immobilisations corporelles (net)", imm_cor),
        ("AF", "Immobilisations financières (net)", imm_fin),
        ("AZ", "Autres immobilisations (net)", imm_aut),
        ("BA", "Stocks de marchandises", st_m),
        ("BB", "Autres stocks et encours", st_a),
        ("BC", "Dépréciations des stocks", st_d),
        ("BG", "Fournisseurs débiteurs", pos(["40"])),
        ("BH", "Clients et comptes rattachés", pos(["41"])),
        ("BI", "État, personnel, organismes sociaux", pos(["42", "43", "44"])),
        ("BJ", "Autres créances", pos(["45", "46", "47", "48"])),
        ("BK", "Dépréciations des créances (49)", dr(["49"])),
        ("BQ", "Trésorerie - Actif (banque, caisse)", tresor_pos),
        ("BR", "Dépréciations de trésorerie (59)", dr(["59"])),
    ]
    passif = [
        ("CA", "Capital", cr(["10"])),
        ("CB", "Réserves", cr(["11"])),
        ("CC", "Report à nouveau", cr(["12"])),
        ("CD", "Résultat net de l'exercice", resultat + cr(["13"])),
        ("CE", "Subventions et provisions réglementées", cr(["14", "15"])),
        ("CF", "Emprunts et dettes financières", cr(["16", "17", "18"])),
        ("CG", "Provisions pour risques et charges", cr(["19"])),
        ("DA", "Fournisseurs et comptes rattachés", neg(["40"])),
        ("DB", "Clients créditeurs", neg(["41"])),
        ("DC", "Dettes fiscales et sociales", neg(["42", "43", "44"])),
        ("DD", "Autres dettes", neg(["45", "46", "47", "48"])),
        ("DE", "Trésorerie - Passif (découverts, crédits)", neg(["5"], ["59"])),
    ]
    A = [r for r in actif if r[2] != 0]
    P = [r for r in passif if r[2] != 0]
    return A, P, sum(r[2] for r in actif), sum(r[2] for r in passif)


def indicateurs(db, d1, d2):
    t = db.totaux(d1, d2)
    cr, dr, pos, neg = _helpers(t)
    tc = db.totaux(None, d2)
    cr2, dr2, pos2, neg2 = _helpers(tc)
    _, net = compte_resultat(db, d1, d2)
    return [
        ("Chiffre d'affaires (ventes, classe 70)", cr(["70"])),
        ("Achats de marchandises (601)", dr(["601"])),
        ("Résultat net de la période", net),
        ("Trésorerie (banque + caisse)", dr2(["5"], ["59"])),
        ("Créances clients (411)", dr2(["41"])),
        ("Dettes fournisseurs (401)", -dr2(["40"])),
        ("TVA à reverser (collectée - déductible)", cr2(["443"]) - dr2(["445"])),
        ("Valeur du stock (CMUP)", db.valeur_stock()),
    ]
