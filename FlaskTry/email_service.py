from datetime import datetime, timedelta, date
from flask import Flask, request, render_template, redirect, url_for, session
from flask_mail import Message, Mail
from FlaskTry.flasktry import app

Gmail = app.config['email_account']

def send_deadline_emails(user_email, deadline_diff, deadline, mail, patient_number, patient_firstname, patient_lastname, type=None, dentistName=None, prothesist=None, ProFinished=None):

    msg = Message(
        subject="ManageMyLab - Rappel de date limite",
        sender=Gmail,
        recipients=[user_email]
    )

    patient_name = patient_lastname + " " + patient_firstname

    prothesist_info = ""

    if prothesist and ProFinished == "yes":
        prothesist_info = f"""Le travail est actuellement pris en charge par le prothésiste : {prothesist}"""

    if type == "patient":
        if deadline_diff == 2:
            msg.body = f"""
            Bonjour,
            Ceci est un rappel concernant le travail suivant, dont la date limite approche :
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Il reste 2 jours avant la date limite.
            Nous vous invitons à vérifier le dossier et à vous assurer que le travail nécessaire sera terminé dans les délais prévus.
            
            Cordialement,
            ManageMyLab
            """

        elif deadline_diff == 1:
            msg.body = f"""
            Bonjour,
            Ceci est un rappel concernant le travail suivant, dont la date limite est prévue pour demain :
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Il reste 1 jour avant la date limite.
            Veuillez vérifier le dossier et vous assurer que le travail nécessaire sera terminé à temps.
            
            Cordialement,
            ManageMyLab
            """

        elif deadline_diff == 0:
            msg.body = f"""
            Bonjour,
            Nous vous informons que le travail suivant arrive à sa date limite aujourd'hui :
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Nous vous recommandons de vérifier le dossier et de prendre les mesures nécessaires afin de finaliser le travail dans les meilleurs délais.
            
            Cordialement,
            ManageMyLab
            """

    elif type == "dentist":
        if deadline_diff == 2:
            msg.body = f"""
            Bonjour,
            Ceci est un rappel concernant le travail suivant, dont la date limite approche :
            Nom du dentiste : {dentistName}
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Il reste 2 jours avant la date limite.
            Nous vous invitons à vérifier le dossier et à vous assurer que le travail nécessaire sera terminé dans les délais prévus.
            
            Cordialement,
            ManageMyLab
            """

        elif deadline_diff == 1:
            msg.body = f"""
            Bonjour,
            Ceci est un rappel concernant le travail suivant, dont la date limite est prévue pour demain :
            Nom du dentiste : {dentistName}
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Il reste 1 jour avant la date limite.
            Veuillez vérifier le dossier et vous assurer que le travail nécessaire sera terminé à temps.
            
            Cordialement,
            ManageMyLab
            """

        elif deadline_diff == 0:
            msg.body = f"""
            Bonjour,
            Nous vous informons que le travail suivant arrive à sa date limite aujourd'hui :
            Nom du dentiste : {dentistName}
            Nom du patient : {patient_name}
            Numéro du patient : {patient_number}
            Date limite : {deadline}
            {prothesist_info}
            Nous vous recommandons de vérifier le dossier et de prendre les mesures nécessaires afin de finaliser le travail dans les meilleurs délais.
            
            Cordialement,
            ManageMyLab
            """

    if msg.body:
        mail.send(msg)


def send_quantity_email(user_email, mail, sel3a_name, quantity, max_quantity, unit, low_stock_notified, out_of_stock_notified):

    msg = Message(
        subject="Quantity Email",
        sender=Gmail,
        recipients=[user_email]
    )

    # Determine the low-stock threshold
    if max_quantity <= 5:
        low_quantity = 1

    elif max_quantity <= 10:
        low_quantity = 2

    elif max_quantity <= 20:
        low_quantity = 3

    elif max_quantity <= 50:
        low_quantity = 5

    elif max_quantity <= 100:
        low_quantity = 10

    elif max_quantity <= 200:
        low_quantity = 20

    else:
        low_quantity = 30


    # OUT OF STOCK
    if quantity == 0 and out_of_stock_notified is False:

        msg.body = f"""
                Bonjour,
                
                Une alerte automatique vous informe que le produit suivant est actuellement en rupture de stock dans votre inventaire :
                
                Produit : {sel3a_name}
                Quantité disponible : 0 {unit}
                
                Ce produit n'est actuellement plus disponible en stock.
                Nous vous invitons à vérifier votre inventaire et à procéder à son réapprovisionnement afin d'éviter toute interruption de votre activité.
                
                Cette notification a été générée automatiquement par ManageMyLab.
                
                Cordialement,
                ManageMyLab
                Gestion des stocks — Laboratoire de prothèse
                """

        mail.send(msg)
        out_of_stock_notified = True


    # LOW STOCK
    elif quantity <= low_quantity and quantity > 0 and low_stock_notified is False:

        msg.body = f"""
                    Bonjour,
                    
                    Ceci est une notification automatique de votre système de gestion ManageMyLab.
                    
                    Le produit suivant a atteint un niveau de stock faible et pourrait nécessiter un réapprovisionnement :
                    
                    Produit : {sel3a_name}
                    Quantité disponible : {quantity} {unit}
                    Seuil de stock faible : {low_quantity} {unit}
                    
                    Nous vous recommandons de vérifier votre stock et de prévoir un réapprovisionnement si nécessaire afin d'éviter toute rupture.
                    
                    Cette notification a été générée automatiquement par ManageMyLab.
                    
                    Cordialement,
                    ManageMyLab
                    Gestion des stocks — Laboratoire de prothèse
                    """

        mail.send(msg)
        low_stock_notified = True


    return low_stock_notified, out_of_stock_notified

def send_prothesists_email(user_email, mail, user_name, service_name, prothesist_name, patient_number, remain, deadline):
    msg = Message(
        subject="Prothesists DeadLine Services Remaining",
        sender=Gmail,
        recipients=[user_email]
    )

    if remain == 2 :
        msg.body = f"""
                    Bonjour,
                    Nous vous informons qu'un travail prothétique confié à l'un de vos prothésistes arrive prochainement à échéance.
                    
                    **Prothésiste :** { prothesist_name }
                    **Patient :** { patient_number }
                    **Travail :** { service_name }
                    **Date limite :** { deadline }
                    
                    Il reste **2 jours avant la date limite**.
                    
                    Nous vous invitons à vérifier l'avancement de ce travail afin de vous assurer qu'il sera finalisé dans les délais prévus.
                    
                    Cordialement,
                    **ManageMyLab**
                    Système de gestion de laboratoire prothétique
                    """

    if remain == 1 :
        msg.body = f"""
                    Bonjour,
                    Nous vous informons qu'un travail prothétique confié à l'un de vos prothésistes arrive à échéance **demain**.
                    
                    **Prothésiste :** { prothesist_name }
                    **Patient :** { patient_number }
                    **Travail :** { service_name }
                    **Date limite :** { deadline }
                    
                    Il ne reste plus que **1 jour avant la date limite**.
                    
                    Nous vous recommandons de vérifier l'avancement du travail et de vous assurer qu'il pourra être finalisé dans le délai prévu.
                    
                    Cordialement,
                    **ManageMyLab**
                    Système de gestion de laboratoire prothétique """

    if remain == 0 :
        msg.body = f"""
                    Bonjour,
                    Nous vous informons qu'un travail prothétique confié à l'un de vos prothésistes arrive à échéance **aujourd'hui**.
                    
                    **Prothésiste :** { prothesist_name }
                    **Patient :** { patient_number }
                    **Travail :** { service_name }
                    **Date limite :** { deadline }
                    
                    La date limite est **aujourd'hui**.
                    
                    Nous vous invitons à vérifier immédiatement l'état de ce travail et à prendre les mesures nécessaires afin de respecter le délai prévu.
                    
                    Cordialement,
                    **ManageMyLab**
                    Système de gestion de laboratoire prothétique
                    """

    if msg.body :
        mail.send(msg)

def send_abonnement_email(mail, user_mail, user_name):
    msg = Message(
        subject='Votre abonnement ManageMyLab expire dans 4 jours',
        sender=Gmail,
        recipients=[user_mail]
    )
    expiration_date = date.today() + timedelta(days=4)

    msg.body = f"""
                Bonjour { user_name },  
                Nous souhaitons vous informer que votre abonnement ManageMyLab arrivera à expiration dans 4 jours, soit le { expiration_date }.
                Afin de continuer à utiliser ManageMyLab et de conserver l’accès à vos fonctionnalités sans interruption, nous vous invitons à renouveler votre abonnement avant cette date.
                Date d’expiration : { expiration_date }
                Jours restants : 4 jours
                Vous pouvez effectuer le renouvellement directement depuis votre espace ManageMyLab.
                Renouveler mon abonnement
                Nous vous remercions pour votre confiance et pour votre utilisation de ManageMyLab.
                Cordialement,
                L’équipe ManageMyLab
                Solution de gestion pour laboratoires de prothèse dentaire
                """

    mail.send(msg)


