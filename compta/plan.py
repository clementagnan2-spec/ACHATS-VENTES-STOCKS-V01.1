"""Plan comptable SYSCOHADA révisé (principaux comptes). Extensible depuis l'application."""

_PLAN = """
10|Capital
101|Capital social
104|Primes liées au capital social
105|Écarts de réévaluation
106|Réserves
109|Actionnaires, capital souscrit non appelé
11|Réserves
111|Réserve légale
118|Autres réserves
12|Report à nouveau
121|Report à nouveau créditeur
129|Report à nouveau débiteur
13|Résultat net de l'exercice
131|Résultat net : bénéfice
139|Résultat net : perte
14|Subventions d'investissement
15|Provisions réglementées et fonds assimilés
16|Emprunts et ressources assimilées
161|Emprunts obligataires
162|Emprunts auprès des établissements de crédit
165|Dépôts et cautionnements reçus
17|Dettes de location-acquisition
18|Dettes liées à des participations et comptes de liaison
19|Provisions pour risques et charges
21|Immobilisations incorporelles
211|Frais de développement et de prospection
212|Brevets, licences, logiciels
22|Terrains
23|Bâtiments, installations techniques et agencements
231|Bâtiments
24|Matériel, mobilier et actifs biologiques
241|Matériel et outillage industriel et commercial
244|Matériel et mobilier de bureau
245|Matériel de transport
25|Avances et acomptes versés sur immobilisations
26|Titres de participation
27|Autres immobilisations financières
28|Amortissements
281|Amortissements des immobilisations incorporelles
283|Amortissements des bâtiments
284|Amortissements du matériel
29|Dépréciations des immobilisations
31|Marchandises
311|Marchandises A
312|Marchandises B
32|Matières premières et fournitures liées
33|Autres approvisionnements
34|Produits en cours
36|Produits finis
39|Dépréciations des stocks
40|Fournisseurs et comptes rattachés
401|Fournisseurs, dettes en compte
408|Fournisseurs, factures non parvenues
409|Fournisseurs débiteurs
41|Clients et comptes rattachés
411|Clients
416|Clients douteux ou litigieux
418|Clients, produits non encore facturés
419|Clients créditeurs
42|Personnel
421|Personnel, avances et acomptes
422|Personnel, rémunérations dues
43|Organismes sociaux
431|Sécurité sociale
44|État et collectivités publiques
441|État, impôt sur les bénéfices
443|État, TVA facturée
4431|TVA facturée sur ventes
4432|TVA facturée sur prestations de services
444|État, TVA due ou crédit de TVA
445|État, TVA récupérable
4451|TVA récupérable sur immobilisations
4452|TVA récupérable sur achats
447|État, impôts retenus à la source
4471|Impôt sur les salaires
45|Organismes internationaux
46|Associés et groupe
461|Associés, opérations sur le capital
462|Associés, comptes courants
47|Débiteurs et créditeurs divers
471|Débiteurs et créditeurs divers
476|Charges constatées d'avance
477|Produits constatés d'avance
48|Créances et dettes hors activités ordinaires
481|Fournisseurs d'investissements
485|Créances sur cessions d'immobilisations
49|Dépréciations et provisions pour risques à court terme
491|Dépréciations des comptes clients
50|Titres de placement
51|Valeurs à encaisser
513|Chèques à encaisser
52|Banques
521|Banques locales
53|Établissements financiers et assimilés
56|Banques, crédits de trésorerie et d'escompte
561|Crédits de trésorerie
57|Caisse
571|Caisse siège
58|Régies d'avances, accréditifs et virements internes
585|Virements de fonds
59|Dépréciations et provisions pour risques à court terme
60|Achats et variations de stocks
601|Achats de marchandises
602|Achats de matières premières et fournitures liées
603|Variations de stocks de biens achetés
6031|Variations de stocks de marchandises
6032|Variations de stocks de matières premières
604|Achats stockés de matières et fournitures consommables
605|Autres achats
608|Achats d'emballages
61|Transports
611|Transports sur achats
612|Transports sur ventes
613|Transports pour le compte de tiers
614|Transports du personnel
62|Services extérieurs A
621|Sous-traitance générale
622|Locations et charges locatives
624|Entretien, réparations et maintenance
625|Primes d'assurance
627|Publicité, publications, relations publiques
628|Frais de télécommunications
63|Services extérieurs B
631|Frais bancaires
632|Rémunérations d'intermédiaires et de conseils
633|Frais de formation du personnel
635|Cotisations
637|Rémunérations de personnel extérieur à l'entreprise
638|Autres charges externes
64|Impôts et taxes
641|Impôts et taxes directs
645|Impôts et taxes indirects
646|Droits d'enregistrement
647|Pénalités et amendes fiscales
65|Autres charges
651|Pertes sur créances clients
658|Charges diverses
66|Charges de personnel
661|Rémunérations directes versées au personnel national
662|Rémunérations directes versées au personnel non national
664|Charges sociales
67|Frais financiers et charges assimilées
671|Intérêts des emprunts
674|Autres intérêts
676|Pertes de change
68|Dotations aux amortissements
681|Dotations aux amortissements d'exploitation
69|Dotations aux provisions et dépréciations
691|Dotations aux provisions d'exploitation
70|Ventes
701|Ventes de marchandises
702|Ventes de produits finis
703|Ventes de produits intermédiaires
704|Ventes de produits résiduels
705|Travaux facturés
706|Services vendus
707|Produits accessoires
71|Subventions d'exploitation
72|Production immobilisée
73|Variations de stocks de biens et de services produits
75|Autres produits
758|Produits divers
77|Revenus financiers et produits assimilés
771|Intérêts de prêts
776|Gains de change
78|Transferts de charges
79|Reprises de provisions, dépréciations et autres
81|Valeurs comptables des cessions d'immobilisations
82|Produits des cessions d'immobilisations
83|Charges hors activités ordinaires (HAO)
84|Produits hors activités ordinaires (HAO)
85|Dotations hors activités ordinaires
86|Reprises hors activités ordinaires
87|Participation des travailleurs
88|Subventions d'équilibre
89|Impôts sur le résultat
891|Impôts sur les bénéfices
"""

PLAN = [tuple(l.split("|", 1)) for l in _PLAN.strip().splitlines()]
