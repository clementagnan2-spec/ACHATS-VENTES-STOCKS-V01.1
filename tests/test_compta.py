import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from compta import reports
from compta.db import Compta, ComptaError


class TestCompta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = Compta(self.tmp.name)
        self.cli = self.db.add_tiers("C", "Client Test")
        self.fou = self.db.add_tiers("F", "Fournisseur Test")
        self.art = self.db.add_article("A1", "Article 1", prix_achat=1000, prix_vente=1500, tva=18)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_entree_desequilibree(self):
        with self.assertRaises(ComptaError):
            self.db.post_entry("01/01/2026", "OD", "x", [("101", 0, 100, None), ("521", 90, 0, None)])

    def test_cycle_complet(self):
        self.db.post_entry("01/01/2026", "OD", "Capital", [("521", 1000000, 0, None), ("101", 0, 1000000, None)])
        self.db.create_facture("A", "05/01/2026", self.fou, [(self.art, 100, 1000, 18)], reglement="521")
        n = self.db.create_facture("V", "10/01/2026", self.cli, [(self.art, 40, 1500, 18)])
        self.assertTrue(n.startswith("FV2026-"))
        with self.assertRaises(ComptaError):
            self.db.create_facture("V", "11/01/2026", self.cli, [(self.art, 61, 1500, 18)])
        self.db.reglement("15/01/2026", self.cli, 30000, "571")
        sold = {r[0]: r[5] for r in self.db.tiers_soldes()}
        self.assertEqual(sold[self.cli], 70800 - 30000)
        self.assertEqual(sold[self.fou], 0)
        self.assertEqual(self.db.valeur_stock(), 60000)
        self.db.generer_variation_stock("31/12/2026")
        self.assertIsNone(self.db.generer_variation_stock("31/12/2026"))

        bal = reports.balance(self.db, "2026-01-01", "2026-12-31")
        self.assertEqual(sum(r[2] for r in bal), sum(r[3] for r in bal))

        lignes, net = reports.compte_resultat(self.db, "2026-01-01", "2026-12-31")
        self.assertEqual(net, 20000)
        marge = [l for l in lignes if l[0] == "XA"][0][2]
        self.assertEqual(marge, 20000)
        self.assertFalse([l for l in lignes if l[0] == "ZZ"])

        actif, passif, ta, tp = reports.bilan(self.db, "2026-12-31")
        self.assertEqual(ta, tp)
        self.assertGreater(ta, 0)

        gl = reports.grand_livre(self.db, "2026-01-01", "2026-12-31", "411")
        self.assertEqual(gl[0]["solde"], 40800)

    def test_aucune_saisie_apres_31_12_2026(self):
        ok = [("521", 100, 0, None), ("101", 0, 100, None)]
        self.db.post_entry("31/12/2026", "OD", "limite autorisée", ok)
        with self.assertRaises(ComptaError):
            self.db.post_entry("01/01/2027", "OD", "trop tard", ok)
        with self.assertRaises(ComptaError):
            self.db.create_facture("A", "01/01/2027", self.fou, [(self.art, 1, 1000, 18)])
        with self.assertRaises(ComptaError):
            self.db.reglement("15/02/2027", self.cli, 1000, "571")
        with self.assertRaises(ComptaError):
            self.db.mouvement_stock("01/01/2027", self.art, "E", 5)
        with self.assertRaises(ComptaError):
            self.db.generer_variation_stock("31/12/2027")
        # rien n'a été enregistré en 2027
        self.assertEqual(self.db.journal("2027-01-01", None), [])
        self.assertEqual(self.db.articles_list()[0]["qte"], 0)

    def test_suppression_piece_facture_interdite(self):
        self.db.create_facture("A", "05/01/2026", self.fou, [(self.art, 1, 1000, 18)])
        with self.assertRaises(ComptaError):
            self.db.delete_piece("FA2026-00001")


if __name__ == "__main__":
    unittest.main()
