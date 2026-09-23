from pathlib import Path
p=Path('SEAndroid_v100.0.6/app/src/main/java/com/orbital/iptv/ui/favourites/FavouritesActivity.kt')
s=p.read_text()
s=s.replace('Intent(this,VodActivity::class.java).putExtra(VodActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId)','Intent(this,VodActivity::class.java)')
s=s.replace('Intent(this,SeriesActivity::class.java).putExtra(SeriesActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId)','Intent(this,SeriesActivity::class.java)')
s=s.replace('Intent(this,HomeActivity::class.java).putExtra(HomeActivity.EXTRA_OPEN_CATEGORY_ID,i.categoryId)','Intent(this,HomeActivity::class.java)')
p.write_text(s)
print('OK')