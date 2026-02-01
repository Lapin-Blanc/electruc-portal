# Electruc Portal

Electruc Portal est une **application web pédagogique** développée avec **Django**,
qui simule un **portail client de fournisseur d’énergie en Belgique**.

L’objectif n’est pas d’enseigner Django, mais de permettre à des apprenants
(notamment des seniors et des adultes en formation)
de s’exercer à des **usages numériques réels** à travers un site de services crédible.

Ce projet est **fictif**, **neutre**, et conçu exclusivement à des fins pédagogiques.

---

## 🎯 Objectifs pédagogiques

Les apprenants peuvent s’exercer à :
- créer et utiliser un compte en ligne
- se connecter à un espace client
- naviguer dans un site de services
- consulter un contrat et des données personnelles
- télécharger des factures (PDF)
- encoder un relevé de compteur
- envoyer une demande au service client avec pièce jointe
- comprendre des messages de confirmation et des statuts

L’interface et le vocabulaire s’inspirent de portails de services réels
(sans reproduire aucune marque existante).

---

## 🧱 Périmètre fonctionnel (MVP)

### Pages publiques (sans connexion)
- Accueil
- Nos services
- Aide / FAQ
- Contact (formulaire simple)

### Espace client (connexion requise)
- Tableau de bord
- Mon profil
- Mon contrat
- Mes factures (liste + téléchargement PDF)
- Mes relevés (formulaire + historique)
- Mes demandes (tickets + pièces jointes)
- Domiciliation bancaire (activation via dépôt de document)

### Administration
- Interface d’administration Django pour :
  - la gestion des utilisateurs (clients)
  - les contrats
  - les factures
  - les demandes
  - la remise à zéro des données de démonstration

---

## 🚫 Hors périmètre

Pour rester simple et pédagogique :
- aucun paiement réel
- aucune connexion bancaire réelle
- aucun calcul tarifaire réel
- aucune API externe
- envoi d’e-mails réel optionnel ou simulé

---

## 🛠️ Stack technique

- Python 3
- Django
- Templates Django (rendu côté serveur)
- SQLite ou PostgreSQL
- Bootstrap (interface)
- Docker et Docker Compose

---

## 🔐 Sécurité (niveau pédagogique)

- hachage des mots de passe (par défaut Django)
- protection CSRF
- contrôle basique des fichiers envoyés
- accès restreint aux pages privées

---

## 🧪 Données de démonstration

Le projet inclut des données fictives pour l’apprentissage :
- plusieurs clients
- contrats
- factures
- relevés
- demandes au service client

Un mécanisme permet de **réinitialiser facilement** l’environnement
entre deux groupes d’apprenants.

---

## ⚖️ Mentions légales

Ce projet est **fictif** et destiné à un **usage pédagogique**.

Il n’est affilié à aucune entreprise réelle
et n’utilise aucune donnée, marque ou service existant.

---

## 📦 Licence

Projet open source — voir le fichier LICENSE.
