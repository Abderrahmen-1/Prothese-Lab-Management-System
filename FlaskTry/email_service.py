from flask import Flask, request, render_template, redirect, url_for, session
from flask_mail import Message, Mail


def send_deadline_emails(user_email, deadline_diff, deadline, mail, patient_number, patient_firstname, patient_lastname, type=None, dentistName=None, prothesist=None, ProFinished=None):

    msg = Message(
        subject="DentaFlow - Rappel de date limite",
        sender=mail.username,
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
            DentaFlow
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
            DentaFlow
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
            DentaFlow
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
            DentaFlow
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
            DentaFlow
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
            DentaFlow
            """

    if msg.body:
        mail.send(msg)


def send_quantity_email(user_email, mail, sel3a_name, quantity, max_quantity, unit, low_stock_notified, out_of_stock_notified):
    msg = Message(
        subject="Quantity Email",
        sender=mail.username,
        recipients=[user_email]
    )

    low_quantity = (max_quantity * 5 )/100

    if quantity <= low_quantity and quantity != 0 and low_stock_notified == False:
        msg.body = f"""
                    Bonjour,
                    Ceci est une notification automatique de votre système de gestion DentaFlow.
                    Le produit suivant a atteint un niveau de stock faible et pourrait nécessiter un réapprovisionnement :
                    **Produit :** { sel3a_name }
                    **Quantité disponible :** { quantity } { unit }
                    Nous vous recommandons de vérifier votre stock et de prévoir un réapprovisionnement si nécessaire afin d'éviter toute rupture.
                    Cette notification a été générée automatiquement par DentaFlow.
                    
                    Cordialement,
                    **DentaFlow**
                    *Gestion des stocks — Laboratoire de prothèse*
                    """
        low_stock_notified = True

    if quantity == 0 and out_of_stock_notified == False :
        msg.body = f"""
                    Bonjour,
                    Une alerte automatique vous informe que le produit suivant est actuellement **en rupture de stock** dans votre inventaire :
                    **Produit :** { sel3a_name }
                    **Quantité disponible :** 0 { unit }
                    Ce produit n'est actuellement plus disponible en stock. Nous vous invitons à vérifier votre inventaire et à procéder à son réapprovisionnement afin d'éviter toute interruption de votre activité.
                    Cette notification a été générée automatiquement par **DentaFlow**.
                    
                    Cordialement,
                    **DentaFlow**
                    *Gestion des stocks — Laboratoire de prothèse*
                    """
        out_of_stock_notified = True

    if msg.body:
        mail.send(msg)

    return (low_stock_notified, out_of_stock_notified)
