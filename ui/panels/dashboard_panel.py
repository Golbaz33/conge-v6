# Fichier : ui/panels/dashboard_panel.py
# CORRECTION BUG REFACTORING : Le panneau reçoit maintenant une référence explicite
# à l'application principale (main_app) pour appeler les méthodes globales.

import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime

from ui.widgets.secondary_windows import AdminWindow, JustificatifsWindow
from utils.date_utils import format_date_for_display, calculate_reprise_date
from utils.file_utils import export_all_conges_to_excel

class DashboardPanel(ttk.LabelFrame):
    """
    Panneau de l'interface utilisateur affichant les statistiques globales et les actions administratives.
    """
    def __init__(self, parent_widget, main_app, manager):
        super().__init__(parent_widget, text="Tableau de Bord")
        self.main_app = main_app  # Référence à MainWindow
        self.manager = manager
        
        self.annee_exercice = self.manager.get_annee_exercice()
        
        self._create_widgets()
        self.refresh_stats()

    def _create_widgets(self):
        """Crée et organise tous les widgets de ce panneau."""
        on_leave_frame = ttk.LabelFrame(self, text="Agents Actuellement en Congé")
        on_leave_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        cols_on_leave = ("Agent", "PPR", "Type Congé", "Date de Reprise")
        self.list_on_leave = ttk.Treeview(on_leave_frame, columns=cols_on_leave, show="headings", height=8)
        for col in cols_on_leave:
            self.list_on_leave.heading(col, text=col)
        
        self.list_on_leave.column("Agent", width=200)
        self.list_on_leave.column("PPR", width=100, anchor="center")
        self.list_on_leave.column("Type Congé", width=150)
        self.list_on_leave.column("Date de Reprise", width=120, anchor="center")
        
        self.list_on_leave.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.global_actions_frame = ttk.Frame(self)
        self.global_actions_frame.pack(fill=tk.X, padx=5, pady=(5, 5))
        
        ttk.Button(self.global_actions_frame, text="Actualiser", command=self.main_app.refresh_all).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2) # CORRIGÉ
        ttk.Button(self.global_actions_frame, text="Suivi Justificatifs", command=self.open_justificatifs_suivi).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.global_actions_frame, text="Administration", command=self.open_admin_window).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.global_actions_frame, text="Exporter Tous les Congés", command=self.export_conges).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def refresh_stats(self):
        """Met à jour la liste des agents actuellement en congé."""
        for row in self.list_on_leave.get_children():
            self.list_on_leave.delete(row)
            
        try:
            holidays_set = self.manager.get_holidays_set_for_period(self.annee_exercice, self.annee_exercice + 1)
            agents_on_leave_data = self.manager.get_agents_on_leave_today()
            
            for nom, prenom, ppr, type_conge, date_fin in agents_on_leave_data:
                reprise_date = calculate_reprise_date(date_fin, holidays_set)
                reprise_date_display = format_date_for_display(reprise_date)
                self.list_on_leave.insert("", "end", values=(f"{nom} {prenom}", ppr, type_conge, reprise_date_display))
        except Exception as e:
            self.list_on_leave.insert("", "end", values=(f"Erreur DB: {e}", "", "", ""))

    def open_admin_window(self):
        """Ouvre la fenêtre d'administration."""
        AdminWindow(self.main_app, self.manager) # CORRIGÉ

    def open_justificatifs_suivi(self):
        """Ouvre la fenêtre de suivi des justificatifs."""
        JustificatifsWindow(self.main_app, self.manager) # CORRIGÉ

    def export_conges(self):
        """Ouvre une boîte de dialogue pour exporter tous les congés."""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", 
            filetypes=[("Fichiers Excel", "*.xlsx")], 
            title="Exporter tous les congés", 
            initialfile=f"Export_Conges_Total_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        )
        if not save_path:
            return
            
        db_path = self.manager.db.db_file
        cert_path = self.manager.certificats_dir
        
        self.main_app._run_long_task( # CORRIGÉ
            lambda: export_all_conges_to_excel(db_path, cert_path, save_path), 
            self.main_app._on_task_complete, 
            "Exportation de tous les congés en cours..."
        )

    def toggle_buttons_state(self, state):
        """Active ou désactive tous les widgets interactifs du panneau."""
        for child in self.global_actions_frame.winfo_children():
            if isinstance(child, ttk.Button):
                child.config(state=state)