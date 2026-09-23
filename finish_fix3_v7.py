from pathlib import Path
p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/utils/FavouritesManager.kt')
s=p.read_text()
bad='category_'+chr(36)+'{categoryType}_'+chr(36)+'{serverUrl.hashCode()}_'+chr(36)+'categoryId'
good='category_'+chr(36)+'{categoryType}_'+chr(36)+'{serverUrl.hashCode()}_'+chr(36)+'categoryId'
s=s.replace('"'+bad+'"','"'+good+'"')
# Also repair the malformed $ form if present.
s=s.replace('"category_'+chr(36)+"{'"+chr(36)+"'}"+'{categoryType}_'+chr(36)+"{'"+chr(36)+"'}"+'{serverUrl.hashCode()}_'+chr(36)+"{'"+chr(36)+"'}"+'categoryId"','"'+good+'"')
# Most robust: replace the whole function line.
lines=s.splitlines()
for i,line in enumerate(lines):
    if 'fun categoryFavoriteId' in line:
        lines[i]='    fun categoryFavoriteId(categoryType: String, serverUrl: String, categoryId: String): String = "category_'+chr(36)+'{categoryType}_'+chr(36)+'{serverUrl.hashCode()}_'+chr(36)+'categoryId"'
s='\n'.join(lines)+'\n'
p.write_text(s)

p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt')
s=p.read_text()
lines=s.splitlines()
for i,line in enumerate(lines):
    if 'tvCount.text=' in line:
        lines[i]=line.replace(chr(36)+"{'"+chr(36)+"'}"+'{m.size+s.size+l.size+c.size}',chr(36)+'{m.size+s.size+l.size+c.size}')
s='\n'.join(lines)+'\n'
p.write_text(s)
print('OK')