# Fichier : ui/panels/agents_panel.py
# CORRECTION BUG REFACTORING : Le panneau reçoit maintenant une référence explicite
# à l'application principale (main_app) pour appeler les méthodes globales.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from core.constants import SoldeStatus
from ui.forms.agent_form import AgentForm
from ui.ui_utils import treeview_sort_column
from utils.file_utils import export_agents_to_excel, import_agents_from_excel

class AgentsPanel(ttk.Frame):
    def __init__(self, parent_widget, main_app, manager, base_dir, on_agent_select_callback):
        super().__init__(parent_widget, padding=5)
        self.main_app = main_app  # Référence à MainWindow
        self.manager = manager
        self.base_dir = base_dir
        self.on_agent_select_callback = on_agent_select_callback

        self.annee_exercice = self.manager.get_annee_exercice()
        
        self.current_page = 1
        self.items_per_page = 50
        self.total_pages = 1
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.search_agents())

        self._create_widgets()
        self.refresh_agents_list()

    def _create_widgets(self):
        agents_frame = ttk.LabelFrame(self, text="Agents")
        agents_frame.pack(fill=tk.BOTH, expand=True)

        search_frame = ttk.Frame(agents_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="Rechercher:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X, expand=True, side=tk.LEFT)
        
        an_n, an_n1, an_n2 = self.annee_exercice, self.annee_exercice - 1, self.annee_exercice - 2
        self.cols_agents = ["ID", "Nom", "Prénom", "PPR", "Grade", f"Solde {an_n2}", f"Solde {an_n1}", f"Solde {an_n}", "Solde Total"]
        self.list_agents = ttk.Treeview(agents_frame, columns=self.cols_agents, show="headings", selectmode="browse")
        
        for col in self.cols_agents:
            self.list_agents.heading(col, text=col, command=lambda c=col: treeview_sort_column(self.list_agents, c, False))

        self.list_agents.column("ID", width=0, stretch=False)
        self.list_agents.column("Nom", width=120)
        # ... (le reste est inchangé)
        
        self.list_agents.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.list_agents.bind("<<TreeviewSelect>>", self._on_agent_select)
        self.list_agents.bind("<Double-1>", lambda e: self.modify_selected_agent())

        pagination_frame = ttk.Frame(agents_frame)
        pagination_frame.pack(fill=tk.X, padx=5, pady=5)
        self.prev_button = ttk.Button(pagination_frame, text="<< Précédent", command=self.prev_page)
        self.prev_button.pack(side=tk.LEFT)
        self.page_label = ttk.Label(pagination_frame, text="Page 1 / 1")
        self.page_label.pack(side=tk.LEFT, expand=True)
        self.next_button = ttk.Button(pagination_frame, text="Suivant >>", command=self.next_page)
        self.next_button.pack(side=tk.RIGHT)
        
        self.btn_frame_agents = ttk.Frame(agents_frame)
        self.btn_frame_agents.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(self.btn_frame_agents, text="Ajouter", command=self.add_agent_ui).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.btn_frame_agents, text="Modifier", command=self.modify_selected_agent).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.btn_frame_agents, text="Supprimer", command=self.delete_selected_agent).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.io_frame_agents = ttk.Frame(agents_frame)
        self.io_frame_agents.pack(fill=tk.X, padx=5, pady=(5, 5))
        ttk.Button(self.io_frame_agents, text="Importer Agents (Excel)", command=self.import_agents).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(self.io_frame_agents, text="Exporter Agents (Excel)", command=self.export_agents).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

    def get_selected_agent_id(self):
        selection = self.list_agents.selection()
        return int(self.list_agents.item(selection[0])["values"][0]) if selection else None

    def refresh_agents_list(self, agent_to_select_id=None):
        for row in self.list_agents.get_children():
            self.list_agents.delete(row)
        
        term = self.search_var.get().strip().lower() or None
        total_items = self.manager.get_agents_count(term)
        self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(self.current_page, self.total_pages)
        offset = (self.current_page - 1) * self.items_per_page
        
        agents = self.manager.get_all_agents(term=term, limit=self.items_per_page, offset=offset)
        
        selected_item_id = None
        an_n, an_n1, an_n2 = self.annee_exercice, self.annee_exercice - 1, self.annee_exercice - 2
        for agent in agents:
            soldes = {s.annee: s.solde for s in agent.soldes_annuels if s.statut == SoldeStatus.ACTIF}
            solde_total = agent.get_solde_total_actif()
            values = (agent.id, agent.nom, agent.prenom, agent.ppr, agent.grade, 
                      f"{soldes.get(an_n2, 0.0):.1f} j", f"{soldes.get(an_n1, 0.0):.1f} j", 
                      f"{soldes.get(an_n, 0.0):.1f} j", f"{solde_total:.1f} j")
            item_id = self.list_agents.insert("", "end", values=values)
            if agent.id == agent_to_select_id:
                selected_item_id = item_id

        if selected_item_id:
            self.list_agents.selection_set(selected_item_id)
            self.list_agents.focus(selected_item_id)
        
        self.page_label.config(text=f"Page {self.current_page} / {self.total_pages}")
        self.prev_button.config(state="normal" if self.current_page > 1 else "disabled")
        self.next_button.config(state="normal" if self.current_page < self.total_pages else "disabled")
        self.main_app.set_status(f"{len(agents)} agents affichés sur {total_items} au total.") # CORRIGÉ

    def search_agents(self):
        self.current_page = 1
        self.refresh_agents_list()
    
    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_agents_list(self.get_selected_agent_id())
            
    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_agents_list(self.get_selected_agent_id())

    def _on_agent_select(self, event=None):
        agent_id = self.get_selected_agent_id()
        self.on_agent_select_callback(agent_id)

    def add_agent_ui(self):
        AgentForm(self.main_app, self.manager) # CORRIGÉ
        
    def modify_selected_agent(self):
        agent_id = self.get_selected_agent_id()
        if agent_id:
            AgentForm(self.main_app, self.manager, agent_id_to_modify=agent_id) # CORRIGÉ
        else:
            messagebox.showwarning("Aucune sélection", "Veuillez sélectionner un agent à modifier.")
            
    def delete_selected_agent(self):
        agent_id = self.get_selected_agent_id()
        if not agent_id: return
        
        agent = self.manager.get_agent_by_id(agent_id)
        if not agent: return

        if messagebox.askyesno("Confirmation", f"Supprimer l'agent '{agent.nom} {agent.prenom}' ?"):
            try:
                self.manager.delete_agent(agent.id)
                self.main_app.set_status(f"Agent '{agent.nom}' supprimé.")
                self.main_app.refresh_all() # CORRIGÉ
            except Exception as e:
                messagebox.showerror("Erreur", f"Une erreur est survenue : {e}")
                
    def import_agents(self):
        source_path = filedialog.askopenfilename(title="Sélectionner un fichier Excel", filetypes=[("Fichiers Excel", "*.xlsx")])
        if not source_path: return
        self.main_app._run_long_task( # CORRIGÉ
            lambda: import_agents_from_excel(self.manager.db.db_file, self.manager.certificats_dir, source_path), 
            self.main_app._on_import_complete, "Importation en cours..."
        )

    def export_agents(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"Export_Agents_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
        if not save_path: return
        self.main_app._run_long_task( # CORRIGÉ
            lambda: export_agents_to_excel(self.manager.db.db_file, self.manager.certificats_dir, save_path), 
            self.main_app._on_task_complete, "Exportation en cours..."
        )

    def toggle_buttons_state(self, state):
        for frame in [self.btn_frame_agents, self.io_frame_agents]:
            for child in frame.winfo_children():
                if isinstance(child, ttk.Button): child.config(state=state)
        self.search_entry.config(state=state)
        self.list_agents.config(selectmode="browse" if state == "normal" else "none")