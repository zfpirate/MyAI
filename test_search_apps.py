from actions.app_catalog import search_catalog_apps

for query in ["discord", "steam", "chrome", "note", "riot"]:
    print(f"\nRecherche : {query}")

    for app in search_catalog_apps(query):
        print(app["name"], "->", app["shortcut_path"])