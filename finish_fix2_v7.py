from pathlib import Path
p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt')
s=p.read_text()
s=s.replace('"category_${{categoryType}_${{serverUrl.hashCode()}_${categoryId"','"category_${categoryType}_${serverUrl.hashCode()}_$categoryId"')
p.write_text(s)
p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt')
s=p.read_text().replace('"${{m.size+s.size+l.size+c.size} ITEMS"','"${m.size+s.size+l.size+c.size} ITEMS"')
p.write_text(s)
print('OK')