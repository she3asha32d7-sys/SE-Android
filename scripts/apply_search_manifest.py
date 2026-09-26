from pathlib import Path

path = Path("app/src/main/AndroidManifest.xml")
s = path.read_text()
needle = '        <activity\n            android:name=".ui.favourites.FavouritesActivity"\n            android:exported="false" />\n'
if "android:name=\".ui.search.SearchActivity\"" not in s:
    if needle not in s: raise SystemExit("FavouritesActivity manifest entry not found")
    s = s.replace(needle, needle + '        <activity android:name=".ui.search.SearchActivity" android:exported="false" />\n\n', 1)
path.write_text(s)
print("SearchActivity manifest entry added")