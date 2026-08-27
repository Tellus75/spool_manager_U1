"""Traductions de l'interface. Français par défaut, anglais au choix."""

from __future__ import annotations

LANGUAGES = (
    ("fr", "Français"),
    ("en", "English"),
)

DEFAULT_LANGUAGE = "fr"

_language = DEFAULT_LANGUAGE

_STRINGS: dict[str, dict[str, str]] = {
    # --- général ----------------------------------------------------------
    "yes": {"fr": "Oui", "en": "Yes"},
    "no": {"fr": "Non", "en": "No"},
    "cancel": {"fr": "Annuler", "en": "Cancel"},
    "save": {"fr": "Enregistrer", "en": "Save"},
    "ok": {"fr": "OK", "en": "OK"},
    "choose": {"fr": "Choisir…", "en": "Choose…"},
    "browse": {"fr": "Parcourir…", "en": "Browse…"},
    "apply": {"fr": "Appliquer", "en": "Apply"},
    "window.title": {
        "fr": "Spool Manager — suivi des bobines",
        "en": "Spool Manager — spool tracking",
    },
    "ready": {
        "fr": "Prêt · en attente d'un tranchage",
        "en": "Ready · waiting for a slice",
    },
    "about.title": {"fr": "À propos", "en": "About"},
    "about.body": {
        "fr": "Spool Manager\n\nSuivi des bobines de filament couplé à Snapmaker Orca, "
        "Orca Slicer et Bambu Studio.",
        "en": "Spool Manager\n\nFilament spool tracking coupled with Snapmaker Orca, "
        "Orca Slicer and Bambu Studio.",
    },
    "filter.all_materials": {"fr": "Toutes les matières", "en": "All materials"},
    # --- onglets ----------------------------------------------------------
    "tab.dashboard": {"fr": "Tableau de bord", "en": "Dashboard"},
    "tab.spools": {"fr": "Bobines", "en": "Spools"},
    "tab.printer": {"fr": "Imprimante", "en": "Printer"},
    "tab.history": {"fr": "Historique", "en": "History"},
    "tab.history_pending": {"fr": "Historique ({count})", "en": "History ({count})"},
    "tab.settings": {"fr": "Réglages", "en": "Settings"},
    # --- zone de notification --------------------------------------------
    "tray.open": {"fr": "Ouvrir Spool Manager", "en": "Open Spool Manager"},
    "tray.add": {"fr": "Ajouter une bobine…", "en": "Add a spool…"},
    "tray.quit": {"fr": "Quitter", "en": "Quit"},
    "tray.running.title": {
        "fr": "Spool Manager continue de tourner",
        "en": "Spool Manager is still running",
    },
    "tray.running.body": {
        "fr": "Les tranchages restent décomptés automatiquement. "
        "Clic droit sur l'icône pour quitter.",
        "en": "Slices keep being deducted automatically. "
        "Right-click the icon to quit.",
    },
    # --- tableau de bord --------------------------------------------------
    "dashboard.title": {"fr": "Mon étagère", "en": "My shelf"},
    "dashboard.add": {"fr": "Ajouter une bobine", "en": "Add a spool"},
    "dashboard.stat.stock": {"fr": "Filament en stock", "en": "Filament in stock"},
    "dashboard.stat.spools": {"fr": "Bobines actives", "en": "Active spools"},
    "dashboard.stat.value": {"fr": "Valeur du stock", "en": "Stock value"},
    "dashboard.stat.printed": {"fr": "Filament imprimé", "en": "Filament printed"},
    "dashboard.subtitle": {
        "fr": "{count} bobines suivies, {loaded} chargées dans {printer}",
        "en": "{count} tracked spools, {loaded} loaded in {printer}",
    },
    "dashboard.search": {
        "fr": "Rechercher une bobine, une couleur, une case…",
        "en": "Search a spool, a colour, a bin…",
    },
    "dashboard.low": {"fr": "Stock bas", "en": "Low stock"},
    "dashboard.loaded": {"fr": "Dans l'imprimante", "en": "In the printer"},
    "dashboard.empty": {
        "fr": "Aucune bobine ne correspond.\n\n"
        "Ajoutez vos bobines pour que le trancheur puisse décompter "
        "automatiquement le filament à chaque tranchage.",
        "en": "No spool matches.\n\n"
        "Add your spools so the slicer can automatically deduct "
        "filament on every slice.",
    },
    "dashboard.see": {"fr": "Voir", "en": "View"},
    "dashboard.verify": {"fr": "Vérifier", "en": "Review"},
    "dashboard.banner.review": {
        "fr": "{count} tranchage{plural} en attente de vérification : "
        "la bobine à décompter n'a pas pu être déterminée avec certitude.",
        "en": "{count} slice{plural} waiting for review: "
        "the spool to deduct could not be determined with certainty.",
    },
    "dashboard.banner.empty": {
        "fr": "{count} bobine{plural} vide{plural}",
        "en": "{count} empty spool{plural}",
    },
    "dashboard.banner.low": {
        "fr": "{count} sous les {threshold:.0f} g",
        "en": "{count} below {threshold:.0f} g",
    },
    "dashboard.banner.stock": {
        "fr": "Stock à surveiller : {alerts}.",
        "en": "Stock to watch: {alerts}.",
    },
    # --- bobines ----------------------------------------------------------
    "spools.title": {"fr": "Bobines", "en": "Spools"},
    "spools.weigh": {"fr": "Peser…", "en": "Weigh…"},
    "spools.adjust": {"fr": "Corriger…", "en": "Adjust…"},
    "spools.edit": {"fr": "Modifier…", "en": "Edit…"},
    "spools.add": {"fr": "Ajouter une bobine", "en": "Add a spool"},
    "spools.search": {"fr": "Rechercher…", "en": "Search…"},
    "spools.archived": {"fr": "Afficher les archivées", "en": "Show archived"},
    "spools.col.color": {"fr": "", "en": ""},
    "spools.col.spool": {"fr": "Bobine", "en": "Spool"},
    "spools.col.material": {"fr": "Matière", "en": "Material"},
    "spools.col.colour": {"fr": "Couleur", "en": "Colour"},
    "spools.col.remaining": {"fr": "Restant", "en": "Remaining"},
    "spools.col.fill": {"fr": "Remplissage", "en": "Fill"},
    "spools.col.slot": {"fr": "Emplacement", "en": "Slot"},
    "spools.col.bin": {"fr": "Case", "en": "Bin"},
    "spools.col.state": {"fr": "État", "en": "State"},
    "spools.col.value": {"fr": "Valeur", "en": "Value"},
    "spools.movements": {"fr": "Mouvements", "en": "Movements"},
    "spools.movements_of": {
        "fr": "Mouvements de « {name} »",
        "en": "Movements of “{name}”",
    },
    "spools.mov.date": {"fr": "Date", "en": "Date"},
    "spools.mov.type": {"fr": "Type", "en": "Type"},
    "spools.mov.delta": {"fr": "Variation", "en": "Change"},
    "spools.mov.detail": {"fr": "Détail", "en": "Detail"},
    "spools.count": {
        "fr": "{count} bobine{plural} affichée{plural} · {kg:.2f} kg au total",
        "en": "{count} spool{plural} shown · {kg:.2f} kg in total",
    },
    "spools.fill_of": {
        "fr": "{pct:.0f} % de {net:.0f} g",
        "en": "{pct:.0f} % of {net:.0f} g",
    },
    "spools.gross_tip": {
        "fr": "Poids attendu sur la balance : {g:.0f} g",
        "en": "Expected weight on the scale: {g:.0f} g",
    },
    # --- imprimante -------------------------------------------------------
    "printer.title": {"fr": "Imprimante", "en": "Printer"},
    "printer.custom": {"fr": "Autre imprimante", "en": "Other printer"},
    "printer.subtitle": {
        "fr": "Indiquez quelle bobine occupe chaque emplacement. Le décompte automatique "
        "s'appuie sur cette correspondance pour attribuer sans ambiguïté le filament "
        "consommé à chaque tranchage.",
        "en": "Say which spool occupies each slot. Automatic deduction relies on this "
        "mapping to assign consumed filament to the right spool on every slice.",
    },
    "printer.available": {
        "fr": "Bobines disponibles sur l'étagère",
        "en": "Spools available on the shelf",
    },
    "printer.hint": {
        "fr": "Faites glisser une bobine vers un emplacement pour la charger.",
        "en": "Drag a spool onto a slot to load it.",
    },
    "printer.slot": {"fr": "Emplacement {slot}", "en": "Slot {slot}"},
    "printer.ams": {"fr": "AMS {slot}", "en": "AMS {slot}"},
    "printer.empty": {"fr": "Vide", "en": "Empty"},
    "printer.drop": {"fr": "Déposez une bobine ici", "en": "Drop a spool here"},
    "printer.pick": {"fr": "Choisir…", "en": "Choose…"},
    "printer.remove": {"fr": "Retirer", "en": "Unload"},
    "printer.freed": {"fr": "{place} libéré", "en": "{place} freed"},
    "printer.none": {"fr": "Aucune bobine disponible", "en": "No spool available"},
    "printer.currently": {
        "fr": " (actuellement en {slot})",
        "en": " (currently in {slot})",
    },
    "card.slot": {"fr": "Empl. {slot}", "en": "Slot {slot}"},
    "card.ams": {"fr": "AMS {slot}", "en": "AMS {slot}"},
    "card.bin": {"fr": "case {name}", "en": "bin {name}"},
    "card.tip": {
        "fr": "{name}\n{remaining:.0f} g restants sur {net:.0f} g\n"
        "Poids attendu sur la balance : {gross:.0f} g\n"
        "Valeur restante : {value:.2f} EUR",
        "en": "{name}\n{remaining:.0f} g remaining of {net:.0f} g\n"
        "Expected weight on the scale: {gross:.0f} g\n"
        "Remaining value: {value:.2f} EUR",
    },
    # --- historique -------------------------------------------------------
    "history.title": {
        "fr": "Historique des tranchages",
        "en": "Slice history",
    },
    "history.verify": {"fr": "Vérifier…", "en": "Review…"},
    "history.undo": {"fr": "Annuler le décompte", "en": "Undo deduction"},
    "history.partial": {"fr": "Impression arrêtée…", "en": "Stopped print…"},
    "history.partial.done": {
        "fr": "Décompte de « {name} » ajusté à {grams:.1f} g",
        "en": "Deduction of “{name}” adjusted to {grams:.1f} g",
    },
    "history.partial.mark": {
        "fr": "impression inachevée",
        "en": "stopped early",
    },
    "history.qty.revised": {
        "fr": "{actual:.2f} g / {sliced:.2f} g",
        "en": "{actual:.2f} g / {sliced:.2f} g",
    },
    "history.filter.all": {"fr": "Tous les tranchages", "en": "All slices"},
    "history.filter.review": {"fr": "À vérifier", "en": "To review"},
    "history.filter.applied": {"fr": "Décomptés", "en": "Deducted"},
    "history.filter.reverted": {"fr": "Annulés", "en": "Undone"},
    "history.col.date": {"fr": "Date", "en": "Date"},
    "history.col.project": {"fr": "Projet", "en": "Project"},
    "history.col.filament": {"fr": "Filament", "en": "Filament"},
    "history.col.cost": {"fr": "Coût", "en": "Cost"},
    "history.col.status": {"fr": "Statut", "en": "Status"},
    "history.detail": {"fr": "Détail", "en": "Detail"},
    "history.select": {"fr": "Sélectionnez un tranchage.", "en": "Select a slice."},
    "history.unnamed": {"fr": "Sans nom", "en": "Untitled"},
    "history.source.hook": {"fr": "le hook Orca", "en": "the Orca hook"},
    "history.source.watch": {
        "fr": "la surveillance de dossier",
        "en": "folder watching",
    },
    "history.detected": {"fr": "détecté par {source}", "en": "detected by {source}"},
    "history.tree.filament": {
        "fr": "Filament du tranchage",
        "en": "Slice filament",
    },
    "history.tree.spool": {"fr": "Bobine décomptée", "en": "Deducted spool"},
    "history.tree.qty": {"fr": "Quantité", "en": "Quantity"},
    "history.slot": {"fr": "Emplacement {slot}", "en": "Slot {slot}"},
    "history.filament": {"fr": "Filament", "en": "Filament"},
    "history.unassigned": {"fr": "Non attribué", "en": "Unassigned"},
    "history.ignored": {"fr": "Tranchage ignoré", "en": "Slice ignored"},
    "history.applied": {"fr": "Décompte appliqué", "en": "Deduction applied"},
    "history.undone": {
        "fr": "Décompte de « {name} » annulé, le filament a été restitué",
        "en": "Deduction of “{name}” undone, filament was restored",
    },
    "history.subtitle": {
        "fr": "{count} tranchage{plural} · {kg:.2f} kg décomptés au total",
        "en": "{count} slice{plural} · {kg:.2f} kg deducted in total",
    },
    "history.pending": {
        "fr": " · {count} en attente de vérification",
        "en": " · {count} waiting for review",
    },
    "partial.title": {"fr": "Impression arrêtée", "en": "Stopped print"},
    "partial.heading": {
        "fr": "Corriger « {name} »",
        "en": "Adjust “{name}”",
    },
    "partial.explain": {
        "fr": "Si l'impression a été annulée avant la fin, indiquez le filament "
        "réellement consommé. Le reste est recrédité sur la bobine. Vous pourrez "
        "corriger à nouveau tant que le décompte n'est pas annulé.",
        "en": "If the print was cancelled before the end, enter the filament actually "
        "used. The unused amount is credited back to the spool. You can correct "
        "again until the deduction is undone.",
    },
    "partial.progress": {"fr": "Avancement", "en": "Completion"},
    "partial.progress_tip": {
        "fr": "Applique le même pourcentage à tous les filaments.",
        "en": "Applies the same percentage to every filament.",
    },
    "partial.used": {"fr": "Réellement utilisé", "en": "Actually used"},
    "partial.sliced": {"fr": "tranché {grams:.2f} g", "en": "sliced {grams:.2f} g"},
    "partial.preview_restore": {
        "fr": "{grams:.1f} g seront recrédités au total.",
        "en": "{grams:.1f} g will be credited back in total.",
    },
    "partial.preview_deduct": {
        "fr": "{grams:.1f} g supplémentaires seront décomptés.",
        "en": "{grams:.1f} g more will be deducted.",
    },
    "partial.preview_none": {
        "fr": "Aucun écart par rapport au décompte actuel.",
        "en": "No change from the current deduction.",
    },
    "partial.apply": {"fr": "Ajuster le décompte", "en": "Adjust deduction"},
    # --- revue ------------------------------------------------------------
    "review.title": {"fr": "Vérifier un tranchage", "en": "Review a slice"},
    "review.unnamed": {"fr": "Tranchage sans nom", "en": "Untitled slice"},
    "review.unknown_printer": {"fr": "imprimante inconnue", "en": "unknown printer"},
    "review.summary": {
        "fr": "{grams:.1f} g au total · {printer} · tranché le {when}",
        "en": "{grams:.1f} g in total · {printer} · sliced on {when}",
    },
    "review.explain": {
        "fr": "L'attribution automatique n'a pas été assez sûre. Confirmez la bobine à "
        "décompter pour chaque filament, ou ignorez ce tranchage.",
        "en": "Automatic matching was not confident enough. Confirm the spool to deduct "
        "for each filament, or ignore this slice.",
    },
    "review.no_preset": {
        "fr": "Aucune information de profil dans le G-code",
        "en": "No preset information in the G-code",
    },
    "review.none_needed": {
        "fr": "Aucun décompte nécessaire",
        "en": "No deduction needed",
    },
    "review.skip": {"fr": "— Ne rien décompter —", "en": "— Deduct nothing —"},
    "review.insufficient": {"fr": "  (stock insuffisant)", "en": "  (not enough stock)"},
    "review.other_material": {
        "fr": "({material}, matière différente)",
        "en": "({material}, different material)",
    },
    "review.in_slot": {"fr": " · emplacement {slot}", "en": " · slot {slot}"},
    "review.line": {
        "fr": "{slot} · {grams:.1f} g de {material}",
        "en": "{slot} · {grams:.1f} g of {material}",
    },
    "review.discard": {"fr": "Ignorer ce tranchage", "en": "Ignore this slice"},
    "review.discard_tip": {
        "fr": "Supprime la ligne sans jamais toucher au stock.",
        "en": "Deletes the row without ever touching stock.",
    },
    "review.deduct": {"fr": "Décompter", "en": "Deduct"},
    "review.later": {"fr": "Plus tard", "en": "Later"},
    # --- dialogue bobine --------------------------------------------------
    "spool.edit_title": {"fr": "Modifier la bobine", "en": "Edit spool"},
    "spool.new_title": {"fr": "Nouvelle bobine", "en": "New spool"},
    "spool.edit_heading": {"fr": "Modifier la bobine", "en": "Edit spool"},
    "spool.new_heading": {
        "fr": "Ajouter une bobine à l'étagère",
        "en": "Add a spool to the shelf",
    },
    "spool.vendor": {"fr": "Marque", "en": "Brand"},
    "spool.vendor_ph": {
        "fr": "Snapmaker, Prusament, Sunlu…",
        "en": "Snapmaker, Prusament, Sunlu…",
    },
    "spool.material": {"fr": "Matière", "en": "Material"},
    "spool.range": {"fr": "Gamme", "en": "Range"},
    "spool.range_ph": {"fr": "PLA Matte, PETG HF…", "en": "PLA Matte, PETG HF…"},
    "spool.colour": {"fr": "Couleur", "en": "Colour"},
    "spool.colour_name": {"fr": "Nom de la couleur", "en": "Colour name"},
    "spool.colour_ph": {
        "fr": "Orange lave, Noir mat…",
        "en": "Lava orange, matte black…",
    },
    "spool.preset": {"fr": "Profil Orca associé", "en": "Linked Orca preset"},
    "spool.density": {"fr": "Densité", "en": "Density"},
    "spool.diameter": {"fr": "Diamètre", "en": "Diameter"},
    "spool.net": {"fr": "Poids net à l'achat", "en": "Net weight at purchase"},
    "spool.remaining": {"fr": "Restant actuel", "en": "Current remaining"},
    "spool.remaining_tip_new": {
        "fr": "Ce qu'il reste aujourd'hui. Laisser égal au poids d'achat pour une bobine neuve.",
        "en": "What is left today. Leave equal to the purchase weight for a new spool.",
    },
    "spool.remaining_tip_edit": {
        "fr": "Le restant se modifie par une pesée ou une correction, "
        "afin de conserver l'historique.",
        "en": "Remaining weight is changed by a weighing or an adjustment, "
        "so history is kept.",
    },
    "spool.tare": {"fr": "Tare (bobine vide)", "en": "Tare (empty spool)"},
    "spool.tare_tip": {
        "fr": "Poids de la bobine vide, utilisé lors des pesées de recalage.",
        "en": "Empty spool weight, used when recalibrating by weighing.",
    },
    "spool.price": {"fr": "Prix payé", "en": "Price paid"},
    "spool.bin": {"fr": "Case sur l'étagère", "en": "Shelf bin"},
    "spool.bin_ph": {"fr": "A3, étagère haut…", "en": "A3, top shelf…"},
    "spool.label": {"fr": "Étiquette", "en": "Label"},
    "spool.label_ph": {
        "fr": "Facultatif, remplace le nom affiché",
        "en": "Optional, replaces the displayed name",
    },
    "spool.purchase": {"fr": "Date d'achat", "en": "Purchase date"},
    "spool.prefill": {
        "fr": "Préremplir depuis un profil filament de Snapmaker Orca",
        "en": "Prefill from a Snapmaker Orca filament preset",
    },
    "spool.import": {"fr": "Importer un profil…", "en": "Import a preset…"},
    "spool.hint_gross": {
        "fr": "Sur une balance, cette bobine devrait afficher environ {g:.0f} g.",
        "en": "On a scale, this spool should read about {g:.0f} g.",
    },
    "spool.color_dialog": {"fr": "Couleur du filament", "en": "Filament colour"},
    "preset.title": {
        "fr": "Profils filament de Snapmaker Orca",
        "en": "Snapmaker Orca filament presets",
    },
    "preset.search": {
        "fr": "Rechercher : PLA, Snapmaker, U1…",
        "en": "Search: PLA, Snapmaker, U1…",
    },
    "preset.use": {"fr": "Utiliser ce profil", "en": "Use this preset"},
    "weigh.title": {"fr": "Peser la bobine", "en": "Weigh the spool"},
    "weigh.heading": {"fr": "Peser « {name} »", "en": "Weigh “{name}”"},
    "weigh.explain": {
        "fr": "Posez la bobine entière sur la balance et saisissez le poids affiché. "
        "La tare enregistrée sera retirée pour recalculer le filament restant.",
        "en": "Put the whole spool on the scale and enter the displayed weight. "
        "The recorded tare will be subtracted to recompute remaining filament.",
    },
    "weigh.gross": {"fr": "Poids total mesuré", "en": "Measured total weight"},
    "weigh.tare": {"fr": "Tare enregistrée", "en": "Recorded tare"},
    "weigh.apply": {"fr": "Appliquer la pesée", "en": "Apply weighing"},
    "weigh.match": {
        "fr": "Le comptage est conforme à la pesée, rien ne changera.",
        "en": "The count matches the weighing, nothing will change.",
    },
    "weigh.preview": {
        "fr": "Restant recalculé : {net:.0f} g, soit {delta:.0f} g {direction} "
        "que les {counted:.0f} g comptés.",
        "en": "Recomputed remaining: {net:.0f} g, {delta:.0f} g {direction} "
        "than the counted {counted:.0f} g.",
    },
    "weigh.less": {"fr": "de moins", "en": "less"},
    "weigh.more": {"fr": "de plus", "en": "more"},
    "adjust.title": {"fr": "Corriger le stock", "en": "Adjust stock"},
    "adjust.heading": {"fr": "Corriger « {name} »", "en": "Adjust “{name}”"},
    "adjust.delta": {"fr": "Variation", "en": "Change"},
    "adjust.delta_tip": {
        "fr": "Négatif pour retirer du filament, positif pour en ajouter.",
        "en": "Negative to remove filament, positive to add some.",
    },
    "adjust.note": {"fr": "Motif", "en": "Reason"},
    "adjust.note_ph": {
        "fr": "Impression ratée, purge, chute réutilisée…",
        "en": "Failed print, purge, reused leftover…",
    },
    "adjust.current": {
        "fr": "Restant actuel : {g:.0f} g",
        "en": "Current remaining: {g:.0f} g",
    },
    # --- actions ----------------------------------------------------------
    "action.added": {"fr": "Bobine ajoutée à l'étagère", "en": "Spool added to the shelf"},
    "action.updated": {
        "fr": "« {name} » mise à jour",
        "en": "“{name}” updated",
    },
    "action.weigh_ok": {
        "fr": "Pesée conforme au comptage, aucun changement",
        "en": "Weighing matches the count, no change",
    },
    "action.weigh_done": {
        "fr": "« {name} » recalée de {delta:+.0f} g d'après la pesée",
        "en": "“{name}” recalibrated by {delta:+.0f} g from the weighing",
    },
    "action.adjusted": {
        "fr": "Correction de {delta:+.0f} g appliquée",
        "en": "Adjustment of {delta:+.0f} g applied",
    },
    "action.loaded": {
        "fr": "« {name} » chargée dans {place}",
        "en": "“{name}” loaded in {place}",
    },
    "action.unloaded": {
        "fr": "Bobine retirée de l'imprimante",
        "en": "Spool unloaded from the printer",
    },
    "action.archive_title": {"fr": "Archiver la bobine", "en": "Archive the spool"},
    "action.archive_body": {
        "fr": "Archiver « {name} » ?\n\n"
        "Elle disparaîtra de l'étagère et ne sera plus proposée lors des tranchages, "
        "mais son historique de consommation sera conservé.",
        "en": "Archive “{name}”?\n\n"
        "It will disappear from the shelf and no longer be offered on slices, "
        "but its usage history will be kept.",
    },
    "action.archived": {"fr": "« {name} » archivée", "en": "“{name}” archived"},
    "action.delete_title": {
        "fr": "Supprimer définitivement",
        "en": "Delete permanently",
    },
    "action.delete_body": {
        "fr": "Supprimer « {name} » et tout son historique ?\n\n"
        "Cette action est irréversible. Préférez l'archivage pour conserver "
        "les statistiques de consommation.",
        "en": "Delete “{name}” and all of its history?\n\n"
        "This cannot be undone. Prefer archiving to keep usage statistics.",
    },
    "action.deleted": {"fr": "Bobine supprimée", "en": "Spool deleted"},
    "action.menu.weigh": {"fr": "Peser…", "en": "Weigh…"},
    "action.menu.adjust": {"fr": "Corriger le stock…", "en": "Adjust stock…"},
    "action.menu.load": {
        "fr": "Charger dans l'imprimante",
        "en": "Load into printer",
    },
    "action.menu.replace": {
        "fr": " (remplace {name})",
        "en": " (replaces {name})",
    },
    "action.menu.unload": {
        "fr": "Retirer de l'imprimante",
        "en": "Unload from printer",
    },
    "action.menu.edit": {"fr": "Modifier…", "en": "Edit…"},
    "action.menu.archive": {"fr": "Archiver", "en": "Archive"},
    "action.menu.delete": {
        "fr": "Supprimer définitivement",
        "en": "Delete permanently",
    },
    # --- réglages ---------------------------------------------------------
    "settings.title": {"fr": "Réglages", "en": "Settings"},
    "settings.hook": {
        "fr": "Intégration des trancheurs",
        "en": "Slicer integration",
    },
    "settings.hook.explain": {
        "fr": "Le hook est un script que le trancheur exécute au moment où il écrit le "
        "fichier G-code. Il en lit le grammage et le transmet à cette application, "
        "qui décompte alors le filament sur les bonnes bobines.\n\n"
        "Sur une imprimante Bambu (A1 Mini, X1, P1…), le hook tourne dès le tranchage. "
        "Sur la Snapmaker U1, Snapmaker Orca ne l'exécute qu'à l'export : le dossier "
        "temporaire est alors surveillé pour décompter dès l'aperçu.\n\n"
        "Ce réglage appartient au profil d'impression : il doit être posé sur chaque "
        "profil que vous utilisez. Seuls vos profils personnels peuvent être modifiés, "
        "car les profils système sont réécrits à chaque mise à jour.",
        "en": "The hook is a script the slicer runs when it writes the G-code file. "
        "It reads the grams used and sends them to this app, which then deducts "
        "filament from the right spools.\n\n"
        "On a Bambu printer (A1 Mini, X1, P1…), the hook runs as soon as you slice. "
        "On the Snapmaker U1, Snapmaker Orca only runs it on export: the temp folder "
        "is therefore watched so a U1 slice is deducted as soon as the preview is ready.\n\n"
        "This setting belongs to the print profile: it must be set on every profile "
        "you use. Only your personal profiles can be modified, because system "
        "profiles are rewritten on every update.",
    },
    "settings.copy": {"fr": "Copier", "en": "Copy"},
    "settings.copy_tip": {
        "fr": "À coller dans le trancheur sous Réglages d'impression > Autres > "
        "Scripts de post-traitement, pour un profil système.",
        "en": "Paste in the slicer under Print settings > Others > "
        "Post-processing scripts, for a system profile.",
    },
    "settings.install": {
        "fr": "Installer le hook sur tous mes profils",
        "en": "Install the hook on all my profiles",
    },
    "settings.remove": {"fr": "Retirer le hook", "en": "Remove the hook"},
    "settings.refresh": {"fr": "Actualiser", "en": "Refresh"},
    "settings.copied": {
        "fr": "Commande du hook copiée dans le presse-papiers",
        "en": "Hook command copied to the clipboard",
    },
    "settings.no_preset_title": {
        "fr": "Aucun profil personnel",
        "en": "No personal profile",
    },
    "settings.no_preset_body": {
        "fr": "Aucun profil d'impression personnel n'a été trouvé dans les trancheurs "
        "sélectionnés.\n\n"
        "Dupliquez le profil que vous utilisez (icône d'enregistrement à côté du nom), "
        "puis revenez ici.",
        "en": "No personal print profile was found in the selected slicers.\n\n"
        "Duplicate the profile you use (save icon next to the profile name), "
        "then come back here.",
    },
    "settings.installed": {
        "fr": "Hook installé sur {count} profil(s) d'impression",
        "en": "Hook installed on {count} print profile(s)",
    },
    "settings.removed": {
        "fr": "Hook retiré de {count} profil(s)",
        "en": "Hook removed from {count} profile(s)",
    },
    "settings.orca_open_title": {
        "fr": "Un trancheur est ouvert",
        "en": "A slicer is open",
    },
    "settings.orca_open_body": {
        "fr": "Le trancheur réécrit ses profils en se fermant et annulerait la modification.\n\n"
        "Fermez-le, puis réessayez. Continuer quand même ?",
        "en": "The slicer rewrites its profiles on exit and would undo the change.\n\n"
        "Close it, then try again. Continue anyway?",
    },
    "settings.orca_missing": {
        "fr": "Aucun trancheur compatible n'a été trouvé sur cet ordinateur "
        "(Snapmaker Orca, Orca Slicer, Bambu Studio).",
        "en": "No compatible slicer was found on this computer "
        "(Snapmaker Orca, Orca Slicer, Bambu Studio).",
    },
    "settings.orca_found": {
        "fr": "Détecté : {names}{running}",
        "en": "Detected: {names}{running}",
    },
    "settings.orca_running": {
        "fr": " (actuellement ouvert)",
        "en": " (currently open)",
    },
    "settings.slicers": {
        "fr": "Trancheurs à relier",
        "en": "Slicers to connect",
    },
    "settings.slicer_found": {"fr": "{name} (détecté)", "en": "{name} (found)"},
    "settings.slicer_missing": {
        "fr": "{name} (non installé)",
        "en": "{name} (not installed)",
    },
    "settings.no_user_preset": {
        "fr": "Aucun profil d'impression personnel dans les trancheurs sélectionnés",
        "en": "No personal print profile in the selected slicers",
    },
    "settings.warn_duplicate": {
        "fr": "Dupliquez dans le trancheur le profil d'impression que vous utilisez pour "
        "pouvoir y poser le hook, ou activez la surveillance de dossier ci-dessous.",
        "en": "Duplicate in the slicer the print profile you use so the hook can be "
        "installed, or enable folder watching below.",
    },
    "settings.warn_none": {
        "fr": "Le hook n'est posé sur aucun profil : aucun tranchage ne sera décompté "
        "automatiquement.",
        "en": "The hook is not installed on any profile: no slice will be deducted "
        "automatically.",
    },
    "settings.watch": {
        "fr": "Surveillance d'un dossier (secours)",
        "en": "Folder watching (fallback)",
    },
    "settings.watch.explain": {
        "fr": "Pour une imprimante Bambu (A1 Mini, X1, P1…), Orca exécute le hook dès le "
        "tranchage. Pour la Snapmaker U1, Orca ne l'exécute qu'à l'export du G-code.\n\n"
        "Spool Manager surveille aussi le dossier temporaire d'Orca : un tranchage U1 "
        "est donc décompté dès que l'aperçu est prêt, sans export.\n\n"
        "Le dossier ci-dessous reste un filet de sécurité si vous exportez ailleurs. "
        "Un même fichier n'est jamais compté deux fois.",
        "en": "On a Bambu printer (A1 Mini, X1, P1…), Orca runs the hook as soon as you "
        "slice. On the Snapmaker U1, Orca only runs it when you export G-code.\n\n"
        "Spool Manager also watches Orca’s temp folder: a U1 slice is therefore "
        "deducted as soon as the preview is ready, with no export.\n\n"
        "The folder below remains a safety net if you export elsewhere. "
        "The same file is never counted twice.",
    },
    "settings.watch.enable": {
        "fr": "Surveiller un dossier d'export",
        "en": "Watch an export folder",
    },
    "settings.watch.ph": {
        "fr": "Dossier où le trancheur exporte vos G-code",
        "en": "Folder where the slicer exports your G-code",
    },
    "settings.watch.pick": {"fr": "Dossier à surveiller", "en": "Folder to watch"},
    "settings.prefs": {"fr": "Préférences", "en": "Preferences"},
    "settings.printer": {"fr": "Imprimante", "en": "Printer"},
    "settings.printer_tip": {
        "fr": "Le nombre d'emplacements suit le modèle choisi, sauf pour « Autre ».",
        "en": "Slot count follows the chosen model, except for “Other”.",
    },
    "settings.language": {"fr": "Langue de l'interface", "en": "Interface language"},
    "settings.language_tip": {
        "fr": "Le changement s'applique immédiatement.",
        "en": "The change applies immediately.",
    },
    "settings.threshold": {
        "fr": "Seuil d'alerte de stock bas",
        "en": "Low-stock alert threshold",
    },
    "settings.threshold_tip": {
        "fr": "En dessous de ce restant, une bobine est signalée.",
        "en": "Below this remaining weight, a spool is flagged.",
    },
    "settings.slots": {
        "fr": "Emplacements de l'imprimante",
        "en": "Printer slots",
    },
    "settings.slots_tip": {
        "fr": "Nombre d'emplacements filament de l'imprimante.",
        "en": "Number of filament slots on the printer.",
    },
    "settings.notifications": {
        "fr": "Afficher une notification à chaque décompte",
        "en": "Show a notification on every deduction",
    },
    "settings.tray": {
        "fr": "Réduire dans la zone de notification au lieu de quitter",
        "en": "Minimise to the notification area instead of quitting",
    },
    "settings.tray_tip": {
        "fr": "L'application doit rester active pour décompter les tranchages en direct.",
        "en": "The app must stay running to deduct slices live.",
    },
    "settings.autostart": {
        "fr": "Démarrer automatiquement avec Windows",
        "en": "Start automatically with Windows",
    },
    "settings.autostart.fail": {
        "fr": "Impossible de modifier le démarrage automatique",
        "en": "Could not change automatic startup",
    },
    "settings.autostart.on": {
        "fr": "Démarrage avec Windows activé",
        "en": "Start with Windows enabled",
    },
    "settings.autostart.off": {
        "fr": "Démarrage avec Windows désactivé",
        "en": "Start with Windows disabled",
    },
    "settings.data": {"fr": "Données et diagnostic", "en": "Data and diagnostics"},
    "settings.open_data": {
        "fr": "Ouvrir le dossier de données",
        "en": "Open data folder",
    },
    "settings.open_log": {
        "fr": "Ouvrir le journal du hook",
        "en": "Open hook log",
    },
    "settings.open_fail": {
        "fr": "Impossible d'ouvrir {path}",
        "en": "Could not open {path}",
    },
    "settings.data_path": {
        "fr": "Base de données et journaux : {data}\n"
        "Boîte de réception des tranchages : {inbox}",
        "en": "Database and logs: {data}\n"
        "Slice inbox: {inbox}",
    },
    "settings.version": {"fr": "Version {version}", "en": "Version {version}"},
    # --- notifications / jobs --------------------------------------------
    "job.duplicate": {
        "fr": "« {name} » a déjà été décompté, ignoré",
        "en": "“{name}” was already deducted, ignored",
    },
    "job.fail": {"fr": "Échec du décompte : {error}", "en": "Deduction failed: {error}"},
    "job.review.title": {"fr": "Tranchage à vérifier", "en": "Slice to review"},
    "job.review.body": {
        "fr": "« {name} » : {grams:.0f} g. La bobine à décompter n'a pas pu être déterminée.",
        "en": "“{name}”: {grams:.0f} g. The spool to deduct could not be determined.",
    },
    "job.review.status": {
        "fr": "« {name} » en attente de vérification",
        "en": "“{name}” waiting for review",
    },
    "job.detail": {
        "fr": "{grams:.0f} g sur {name} ({remaining:.0f} g restants)",
        "en": "{grams:.0f} g from {name} ({remaining:.0f} g left)",
    },
    "job.fallback": {"fr": "{grams:.0f} g décomptés", "en": "{grams:.0f} g deducted"},
    "job.done.title": {
        "fr": "{name} : {grams:.0f} g décomptés",
        "en": "{name}: {grams:.0f} g deducted",
    },
    "job.done.status": {
        "fr": "« {name} » décompté · {grams:.0f} g",
        "en": "“{name}” deducted · {grams:.0f} g",
    },
    "job.low.title": {"fr": "Stock bas", "en": "Low stock"},
    "job.low.body": {
        "fr": "Il ne reste que {remaining:.0f} g sur « {name} ».",
        "en": "Only {remaining:.0f} g left on “{name}”.",
    },
    "watch.unreadable": {
        "fr": "Fichier de tranchage illisible ({name}) : {error}",
        "en": "Unreadable slice file ({name}): {error}",
    },
    "watch.read_fail": {
        "fr": "Lecture impossible de {name} : {error}",
        "en": "Could not read {name}: {error}",
    },
    # --- états / mouvements / statuts ------------------------------------
    "state.new": {"fr": "Neuve", "en": "New"},
    "state.open": {"fr": "Entamée", "en": "Opened"},
    "state.empty": {"fr": "Vide", "en": "Empty"},
    "state.archived": {"fr": "Archivée", "en": "Archived"},
    "reason.init": {"fr": "Mise en stock", "en": "Stocked"},
    "reason.print": {"fr": "Impression", "en": "Print"},
    "reason.weigh": {"fr": "Pesée de recalage", "en": "Weighing"},
    "reason.adjust": {"fr": "Correction manuelle", "en": "Manual adjustment"},
    "reason.undo": {"fr": "Annulation", "en": "Undo"},
    "reason.partial": {
        "fr": "Impression inachevée",
        "en": "Stopped print",
    },
    "job.status.applied": {"fr": "Décompté", "en": "Deducted"},
    "job.status.review": {"fr": "À vérifier", "en": "To review"},
    "job.status.reverted": {"fr": "Annulé", "en": "Undone"},
    "date.format": {"fr": "%d/%m/%Y %H:%M", "en": "%Y-%m-%d %H:%M"},
    "date.display": {"fr": "dd/MM/yyyy", "en": "yyyy-MM-dd"},
    # --- appariement ------------------------------------------------------
    "match.no_usage": {
        "fr": "Aucune consommation sur ce filament",
        "en": "No usage on this filament",
    },
    "match.no_material": {
        "fr": "Aucune bobine de {material} en stock",
        "en": "No {material} spool in stock",
    },
    "match.no_spool": {
        "fr": "Aucune bobine correspondante en stock",
        "en": "No matching spool in stock",
    },
    "match.this_material": {"fr": "cette matière", "en": "this material"},
    "match.ambiguous": {
        "fr": "Choix ambigu entre {best} et {other}",
        "en": "Ambiguous choice between {best} and {other}",
    },
    "match.weak": {
        "fr": "Correspondance trop faible pour {name}",
        "en": "Match too weak for {name}",
    },
    "match.short": {
        "fr": "{name} n'a que {remaining:.0f} g pour {needed:.0f} g demandés",
        "en": "{name} has only {remaining:.0f} g for {needed:.0f} g requested",
    },
    "match.material": {"fr": "matière {material}", "en": "material {material}"},
    "match.slot": {
        "fr": "chargée dans l'emplacement {slot}",
        "en": "loaded in slot {slot}",
    },
    "match.other_slot": {
        "fr": "chargée dans un autre emplacement ({slot})",
        "en": "loaded in another slot ({slot})",
    },
    "match.preset": {"fr": "profil Orca identique", "en": "identical Orca preset"},
    "match.color_same": {"fr": "couleur identique", "en": "identical colour"},
    "match.color_close": {"fr": "couleur proche", "en": "close colour"},
    "match.color_far": {"fr": "couleur différente", "en": "different colour"},
    "match.vendor": {"fr": "marque {vendor}", "en": "brand {vendor}"},
    "match.low_stock": {"fr": "stock restant insuffisant", "en": "not enough remaining stock"},
}


def current_language() -> str:
    return _language


def set_language(code: str) -> str:
    """Active une langue connue et la renvoie. Inconnue → français."""
    global _language
    known = {item[0] for item in LANGUAGES}
    _language = code if code in known else DEFAULT_LANGUAGE
    return _language


def t(key: str, **kwargs) -> str:
    """Traduit une clé dans la langue courante, avec repli sur le français."""
    entry = _STRINGS.get(key)
    if not entry:
        text = key
    else:
        text = entry.get(_language) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        return text.format(**kwargs)
    return text


def plural(count: int) -> str:
    """Marque de pluriel française/anglaise : 's' dès que count != 1."""
    return "" if count == 1 else "s"


def state_label(state: str) -> str:
    return t(f"state.{state}") if f"state.{state}" in _STRINGS else state


def reason_label(reason: str) -> str:
    return t(f"reason.{reason}") if f"reason.{reason}" in _STRINGS else reason


def job_status_label(status: str) -> str:
    return t(f"job.status.{status}") if f"job.status.{status}" in _STRINGS else status
