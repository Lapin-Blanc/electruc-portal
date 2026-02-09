# Découpage des tâches

T1 : Initialisation du projet Django et Docker (structure uniquement)
T2 : Authentification + pages publiques
T3 : Espace client (structure)
T4 : Modèles métier (contrat, facture, relevé, demande)
T5 : Interface admin et données de démonstration
T6 : Auto-inscription par invitation (EAN + code secret) avec activation e-mail
 - Admin: création de MeterPoint, génération d'invitation imprimable, code secret hashé
 - Admin: import CSV "base élèves" vers MeterPoint (sans création d'utilisateur)
 - Admin: génération automatique d'un historique fictif (5 mois) de consommation/relevés/factures par MeterPoint
 - Admin: action de réinitialisation des comptes en ligne pour rejouer le scénario
 - Admin: action "réinitialiser atelier complet" (comptes + invitations) pour nouvelle session
 - Client: /inscription/ puis validation e-mail via /activation/<uidb64>/<token>/
 - Client: tableau de bord avec graphique de consommation sur les 5 derniers mois
 - Sécurité: invitation non réutilisable, expiration, blocage temporaire après 5 échecs
