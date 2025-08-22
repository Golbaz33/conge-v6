# Fichier : ui/panels/conges_panel.py
# CORRECTION BUG REFACTORING : Le panneau reçoit maintenant une référence explicite
# à l'application principale (main_app) pour appeler les méthodes globales.

import tkinter as tk
from tkinter import ttk, messagebox
from collections import defaultdict
import logging
import os

from ui.forms.conge_form import CongeForm
from ui.ui_utils import treeview_sort_column
from utils.date_utils import format_date_for_display_short, calculate_reprise_date
from utils.config_loader import CONFIG

class CongesPanel(ttk.LabelFrame):
    """
    Panneau de l'interface utilisateur dédié à l'affichage des congés de l'agent sélectionné.
    """
    def __init__(self, parent_widget, main_app, manager, on_conge_select_callback):
        super().__init__(parent_widget, text="Congés de l'agent sélectionné")
        self.main_app = main_app  # Référence à MainWindow
        self.manager = manager
        self.on_conge_select_callback = on_conge_select_callback

        self.current_agent_id = None
        self.conge_filter_var = tk.StringVar(value="Tous")

        self._create_widgets()

    def _create_widgets(self):
        """Crée et organise tous les widgets de ce panneau."""
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(filter_frame, text="Filtrer par type:").pack(side=tk.LEFT, padx=(0, 5))
        self.conge_filter_combo = ttk.Combobox(filter_frame, textvariable=self.conge_filter_var, 
                                          values=["Tous"] + CONFIG['ui']['types_conge'], state="readonly")
        self.conge_filter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.conge_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.display_conges_for_agent(self.current_agent_id))

        cols_conges = ("CongeID", "Certificat", "Type", "Début", "Fin", "Date Reprise", "Jours", "Justification", "Intérimaire")
        self.list_conges = ttk.Treeview(self, columns=cols_conges, show="headings", selectmode="browse")
        
        for col in cols_conges:
            self.list_conges.heading(col, text=col, command=lambda c=col: treeview_sort_column(self.list_conges, c, False))
        
        self.list_conges.column("CongeID", width=0, stretch=False)
        self.list_conges.column("Certificat", width=80, anchor="center")
        self.list_conges.column("Type", width=120)
        self.list_conges.column("Début", width=90, anchor="center")
        self.list_conges.column("Fin", width=90, anchor="center")
        self.list_conges.column("Date Reprise", width=90, anchor="center")
        self.list_conges.column("Jours", width=50, anchor="center")
        self.list_conges.column("Intérimaire", width=150)

        self.list_conges.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.list_conges.tag_configure("summary", background="#e6f2ff", font=("Helvetica", 10, "bold"))
        self.list_conges.tag_configure("annule", foreground="grey", font=('Helvetica', 10, 'overstrike'))
        self.list_conges.bind("<Double-1>", self.on_conge_double_click)
        self.list_conges.bind("<<TreeviewSelect>>", lambda e: self.on_conge_select_callback())

        self.btn_frame_conges = ttk.Frame(self)
        self.btn_frame_conges.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(self.btn_frame_conges, text="Ajouter", command=self.add_conge_ui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.btn_frame_conges, text="Modifier", command=self.modify_selected_conge).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.btn_frame_conges, text="Supprimer", command=self.delete_selected_conge).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
    def get_selected_conge_id(self):
        selection = self.list_conges.selection()
        if not selection: return None
        item = self.list_conges.item(selection[0])
        return int(item["values"][0]) if "summary" not in item["tags"] and item["values"] else None

    def display_conges_for_agent(self, agent_id):
        self.current_agent_id = agent_id
        self.list_conges.delete(*self.list_conges.get_children())

        if not agent_id:
            return

        filtre = self.conge_filter_var.get()
        conges_data = self.manager.get_conges_for_agent(agent_id)
        
        conges_par_annee = defaultdict(list)
        for c in conges_data:
            if filtre != "Tous" and c.type_conge != filtre:
                continue
            if c.date_debut:
                conges_par_annee[c.date_debut.year].append(c)
            else:
                logging.warning(f"Date de début invalide pour congé ID {c.id}")

        for annee in sorted(conges_par_annee.keys(), reverse=True):
            total_jours = sum(c.jours_pris for c in conges_par_annee[annee] if c.type_conge == 'Congé annuel' and c.statut == 'Actif')
            summary_id = self.list_conges.insert("", "end", values=("", "", f"📅 ANNÉE {annee}", "", "", "", total_jours, f"{total_jours} jours pris", ""), tags=("summary",), open=True)
            
            holidays_set = self.manager.get_holidays_set_for_period(annee, annee + 1)
            for conge in sorted(conges_par_annee[annee], key=lambda c: c.date_debut):
                cert_status = "✅ Fourni" if self.manager.get_certificat_for_conge(conge.id) else "❌ Manquant" if conge.type_conge == 'Congé de maladie' else ""
                interim_info = ""
                if conge.interim_id:
                    interim = self.manager.get_agent_by_id(conge.interim_id)
                    interim_info = f"{interim.nom} {interim.prenom}" if interim else "Agent Supprimé"
                
                reprise_date = calculate_reprise_date(conge.date_fin, holidays_set)
                reprise_date_str = format_date_for_display_short(reprise_date) if reprise_date else ""
                
                tags = ('annule',) if conge.statut == 'Annulé' else ()
                self.list_conges.insert(summary_id, "end", values=(
                    conge.id, cert_status, conge.type_conge, 
                    format_date_for_display_short(conge.date_debut), 
                    format_date_for_display_short(conge.date_fin), 
                    reprise_date_str, conge.jours_pris, conge.justif or "", 
                    interim_info
                ), tags=tags)

    def add_conge_ui(self):
        if not self.current_agent_id:
            messagebox.showwarning("Aucun agent", "Veuillez sélectionner un agent.")
            return
        CongeForm(self.main_app, self.manager, self.current_agent_id) # CORRIGÉ

    def modify_selected_conge(self):
        conge_id = self.get_selected_conge_id()
        if not self.current_agent_id or not conge_id:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un congé à modifier.")
            return
        CongeForm(self.main_app, self.manager, self.current_agent_id, conge_id=conge_id) # CORRIGÉ

    def delete_selected_conge(self):
        conge_id = self.get_selected_conge_id()
        if not conge_id:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un congé à supprimer.")
            return
        if messagebox.askyesno("Confirmation", "Êtes-vous sûr de vouloir supprimer ce congé ?"):
            try:
                if self.manager.delete_conge(conge_id):
                    self.main_app.set_status("Congé supprimé.") # CORRIGÉ
                    self.main_app.refresh_all(self.current_agent_id) # CORRIGÉ
            except Exception as e:
                messagebox.showerror("Erreur de suppression", str(e))

    def on_conge_double_click(self, event=None):
        conge_id = self.get_selected_conge_id()
        if not conge_id:
            return
        
        cert = self.manager.get_certificat_for_conge(conge_id)
        if cert and cert[2] and os.path.exists(cert[2]):
            try:
                self.main_app._open_file(cert[2]) # CORRIGÉ
            except Exception as e:
                messagebox.showerror("Erreur d'ouverture", f"Impossible d'ouvrir le fichier:\n{e}", parent=self.main_app) # CORRIGÉ
        else:
            self.modify_selected_conge()

    def toggle_buttons_state(self, state):
        """Active ou désactive tous les widgets interactifs du panneau."""
        for child in self.btn_frame_conges.winfo_children():
            if isinstance(child, ttk.Button):
                child.config(state=state)
        self.conge_filter_combo.config(state="readonly" if state == "normal" else "disabled")
        self.list_conges.config(selectmode="browse" if state == "normal" else "none")