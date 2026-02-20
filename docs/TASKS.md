# Découpage des tâches

T1 : Initialisation du projet Django et Docker (structure)
T2 : Authentification + pages publiques
T3 : Espace client (structure)
T4 : Modèles métier (contrat, facture, relevé, demande)
T5 : Interface admin et données de démonstration

T6 : Inscription autonome par invitation (EAN + code d'activation unique)
- Admin : création de `MeterPoint`, génération d'invitation imprimable, secret hashé
- Admin : import CSV "base élèves" vers `MeterPoint` (sans création utilisateur)
- Admin : génération automatique d'un historique fictif (5 mois)
- Admin : actions de réinitialisation (comptes en ligne / atelier complet)
- Admin : génération PDF multipage d'invitations (multi-sélection)
- Client : `/inscription/` puis activation email `/activation/<uidb64>/<token>/`
- Client : renvoi possible du mail d'activation tant que le compte reste inactif
- Sécurité : invitation expirée/invalide, verrouillage temporaire après 5 échecs

T7 : Rendu documentaire et qualité d'exploitation
- PDF soignés : facture, contrat, CGV
- PDF modifiable : formulaire de domiciliation (AcroForm)
- Dashboard : graphique de consommation sur 5 mois
- Contrats : tarification fixe / variable
- Factures : calculées depuis consommation + paramètres du contrat
- Documentation de reprise : `docs/HANDOVER.md`
