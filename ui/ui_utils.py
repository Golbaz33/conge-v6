# Fichier : ui/ui_utils.py
# NOUVEAU FICHIER : Contient les fonctions utilitaires partagées par les composants de l'interface.

def treeview_sort_column(tv, col, reverse):
    """Fonction utilitaire pour trier une colonne de Treeview."""
    items_list = [(tv.set(k, col), k) for k in tv.get_children('')]
    
    # Définition des colonnes qui doivent être triées numériquement
    numeric_cols = ['Solde Total', 'Jours', 'PPR']
    if 'Solde ' in col:
        numeric_cols.append(col)
        
    try:
        if col in numeric_cols:
            # Tente un tri numérique robuste
            items_list.sort(key=lambda t: float(str(t[0]).replace('j', '').replace(',', '.').strip()), reverse=reverse)
        else:
            # Tri alphabétique insensible à la casse pour les autres colonnes
            items_list.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)
    except (ValueError, IndexError):
        # Fallback en cas d'erreur de conversion (tri simple)
        items_list.sort(key=lambda t: str(t[0]), reverse=reverse)
        
    # Réorganisation des items dans le Treeview
    for index, (val, k) in enumerate(items_list):
        tv.move(k, '', index)
        
    # Réassigne la commande de tri à l'en-tête pour permettre le tri inversé au prochain clic
    tv.heading(col, command=lambda: treeview_sort_column(tv, col, not reverse))

print("Le fichier ui/ui_utils.py a été créé avec succès.")