# Fichier : ui/main_window.py
# VERSION FINALE CORRIGÉE - Post-Refactorisation (Sprint 2)
# Corrige le bug de démarrage en passant la bonne référence aux panneaux.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import os
import sqlite3
import threading
from datetime import datetime, date
import subprocess
import sys

from core.conges.manager import CongeManager
from utils.file_utils import generate_decision_from_template
from utils.date_utils import format_date_for_display, calculate_reprise_date
from utils.config_loader import CONFIG

# --- Imports des panneaux et utilitaires UI ---
from ui.panels.agents_panel import AgentsPanel
from ui.panels.conges_panel import CongesPanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.ui_utils import treeview_sort_column


class MainWindow(tk.Tk):
    def __init__(self, manager: CongeManager, base_dir: str):
        super().__init__()
        self.manager = manager
        self.base_dir = base_dir
        self.title(f"{CONFIG['app']['title']} - v{CONFIG['app']['version']}")
        self.minsize(1400, 700)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.restart_on_close = False
        self.status_var = tk.StringVar(value="Prêt.")

        self.agents_panel = None
        self.conges_panel = None
        self.dashboard_panel = None

        self.create_widgets()
        self.refresh_all()

    def on_close(self):
        if messagebox.askokcancel("Quitter", "Voulez-vous vraiment quitter ?"):
            self.destroy()

    def trigger_restart(self):
        self.restart_on_close = True
        self.destroy()

    def set_status(self, message):
        self.status_var.set(message)
        self.update_idletasks()

    def create_widgets(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure("Treeview", rowheight=25, font=('Helvetica', 10))
        style.configure("Treeview.Heading", font=('Helvetica', 10, 'bold'), relief="raised")
        style.configure("TLabelframe.Label", font=('Helvetica', 12, 'bold'))

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- CORRECTION : Instanciation des panneaux avec la bonne référence 'main_app' ---
        self.agents_panel = AgentsPanel(parent_widget=main_pane, main_app=self, manager=self.manager, 
                                        base_dir=self.base_dir, on_agent_select_callback=self._on_agent_select)
        main_pane.add(self.agents_panel, weight=3)

        right_pane = ttk.PanedWindow(main_pane, orient=tk.VERTICAL)
        main_pane.add(right_pane, weight=2)

        self.conges_panel = CongesPanel(parent_widget=right_pane, main_app=self, manager=self.manager,
                                        on_conge_select_callback=self._update_conge_action_buttons_state)
        right_pane.add(self.conges_panel, weight=3)
        
        self.dashboard_panel = DashboardPanel(parent_widget=right_pane, main_app=self, manager=self.manager)
        right_pane.add(self.dashboard_panel, weight=1)
        # --- FIN DE LA CORRECTION ---

        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.btn_generate_decision = ttk.Button(self.conges_panel.btn_frame_conges, text="Générer Décision", 
                                                command=self.on_generate_decision_click, state="disabled")
        self.btn_generate_decision.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def refresh_all(self, agent_to_select_id=None):
        if agent_to_select_id is None and self.agents_panel:
            agent_to_select_id = self.agents_panel.get_selected_agent_id()

        if self.agents_panel:
            self.agents_panel.refresh_agents_list(agent_to_select_id)
        if self.conges_panel:
            self.conges_panel.display_conges_for_agent(agent_to_select_id)
        if self.dashboard_panel:
            self.dashboard_panel.refresh_stats()
        
        self._update_conge_action_buttons_state()

    def _on_agent_select(self, agent_id):
        if self.conges_panel:
            self.conges_panel.display_conges_for_agent(agent_id)
        self._update_conge_action_buttons_state()

    def _update_conge_action_buttons_state(self):
        if self.conges_panel and self.btn_generate_decision:
            conge_id = self.conges_panel.get_selected_conge_id()
            state = "normal" if conge_id else "disabled"
            self.btn_generate_decision.config(state=state)

    def on_generate_decision_click(self):
        agent_id = self.agents_panel.get_selected_agent_id()
        conge_id = self.conges_panel.get_selected_conge_id()
        
        if not agent_id or not conge_id:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un agent et un congé.")
            return

        conge = self.manager.get_conge_by_id(conge_id)
        agent = self.manager.get_agent_by_id(agent_id)

        if not conge or not agent:
            messagebox.showerror("Erreur", "Impossible de récupérer les informations.")
            return

        templates_dir_name = CONFIG.get('paths', {}).get('templates_dir', 'templates')
        grade_str = agent.grade.lower().replace(" ", "_")
        template_name = f"{grade_str}.docx"
        template_path = os.path.join(self.base_dir, templates_dir_name, template_name)

        if not os.path.exists(template_path):
            messagebox.showerror("Modèle manquant", f"Le modèle pour le grade '{agent.grade}' est introuvable.\nIl devrait être ici : {template_path}")
            return
            
        details_solde_str = ""
        if conge.type_conge == "Congé annuel":
            details = self.manager.get_deduction_details(agent.id, conge.jours_pris)
            parts = [f"{int(round(days))} {'jour' if int(round(days)) == 1 else 'jours'} au titre de l'année {year}" for year, days in sorted(details.items())]
            details_solde_str = " et ".join(parts)

        holidays_set = self.manager.get_holidays_set_for_period(conge.date_fin.year, conge.date_fin.year + 1)
        date_reprise = calculate_reprise_date(conge.date_fin, holidays_set)

        context = {
            "{{nom_complet}}": f"{agent.nom} {agent.prenom}", "{{grade}}": agent.grade, "{{ppr}}": agent.ppr,
            "{{date_debut}}": format_date_for_display(conge.date_debut), "{{date_fin}}": format_date_for_display(conge.date_fin),
            "{{date_reprise}}": format_date_for_display(date_reprise) if date_reprise else "N/A",
            "{{jours_pris}}": str(conge.jours_pris), "{{details_solde}}": details_solde_str,
            "{{date_aujourdhui}}": date.today().strftime("%d/%m/%Y")
        }

        initial_filename = f"Decision_Conge_{agent.nom}_{conge.date_debut.strftime('%Y-%m-%d')}.docx"
        save_path = filedialog.asksaveasfilename(
            title="Enregistrer la décision", initialfile=initial_filename, defaultextension=".docx",
            filetypes=[("Documents Word", "*.docx"), ("Tous les fichiers", "*.*")]
        )

        if not save_path:
            return

        try:
            generate_decision_from_template(template_path, save_path, context)
            if messagebox.askyesno("Succès", "La décision a été générée.\nVoulez-vous ouvrir le fichier ?", parent=self):
                self._open_file(save_path)
        except Exception as e:
            messagebox.showerror("Erreur de Génération", f"Une erreur est survenue:\n{e}", parent=self)

    def _open_file(self, filepath):
        filepath = os.path.realpath(filepath)
        try:
            if sys.platform == "win32": os.startfile(filepath)
            elif sys.platform == "darwin": subprocess.run(["open", filepath], check=True)
            else: subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror("Erreur d'Ouverture", f"Impossible d'ouvrir le fichier:\n{e}", parent=self)
            
    def _run_long_task(self, task_lambda, on_complete, status_message):
        self.set_status(status_message)
        self.config(cursor="watch")
        self._toggle_buttons_state("disabled")
        
        result_container = []
        def task_wrapper():
            try: result_container.append(task_lambda())
            except Exception as e: result_container.append(e)
                
        worker_thread = threading.Thread(target=task_wrapper)
        worker_thread.start()
        self._check_thread_completion(worker_thread, result_container, on_complete)
    
    def _check_thread_completion(self, thread, result_container, on_complete):
        if thread.is_alive():
            self.after(100, lambda: self._check_thread_completion(thread, result_container, on_complete))
        else:
            result = result_container[0] if result_container else None
            on_complete(result)
            self.config(cursor="")
            self._toggle_buttons_state("normal")
            self.set_status("Prêt.")
    
    def _on_task_complete(self, result):
        if isinstance(result, Exception):
            messagebox.showerror("Erreur", f"L'opération a échoué:\n{result}")
        elif result:
            messagebox.showinfo("Succès", result)
    
    def _on_import_complete(self, result):
        self._on_task_complete(result)
        if not isinstance(result, Exception): self.refresh_all()

    def _toggle_buttons_state(self, state):
        if self.agents_panel: self.agents_panel.toggle_buttons_state(state)
        if self.conges_panel: self.conges_panel.toggle_buttons_state(state)
        if self.btn_generate_decision: self.btn_generate_decision.config(state=state)
        if self.dashboard_panel: self.dashboard_panel.toggle_buttons_state(state)