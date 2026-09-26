package com.orbital.iptv.ui.search

import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.orbital.iptv.R
import com.orbital.iptv.data.model.*
import com.orbital.iptv.utils.FavouritesManager
import com.orbital.iptv.utils.ThemeManager

class SearchAdapter(
    private val onClick: (Item) -> Unit
) : RecyclerView.Adapter<SearchAdapter.VH>() {

    sealed class Item {
        data class Movie(val value: VodStream) : Item()
        data class Series(val value: SeriesStream) : Item()
        data class Live(val value: LiveStream) : Item()
        data class Category(val value: LiveCategory) : Item()
    }

    private val items = mutableListOf<Item>()

    companion object {
        private const val MOVIE = 1
        private const val SERIES = 2
        private const val LIVE = 3
        private const val CATEGORY = 4
        private const val POSTER_WIDTH_DP = 170
        private const val LIVE_WIDTH_DP = 182
        private const val LIVE_HEIGHT_DP = 168
    }

    fun submitList(values: List<Item>) {
        items.clear()
        items.addAll(values)
        notifyDataSetChanged()
    }

    override fun getItemCount(): Int = items.size

    override fun getItemViewType(position: Int): Int = when (items[position]) {
        is Item.Movie -> MOVIE
        is Item.Series -> SERIES
        is Item.Live -> LIVE
        is Item.Category -> CATEGORY
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val layout = when (viewType) {
            MOVIE -> R.layout.item_vod_movie
            SERIES -> R.layout.item_series_show
            LIVE -> R.layout.item_live_channel
            else -> R.layout.item_favourite_category
        }
        val root = LayoutInflater.from(parent.context).inflate(layout, parent, false)
        val d = parent.resources.displayMetrics.density
        root.layoutParams = when (viewType) {
            MOVIE, SERIES -> RecyclerView.LayoutParams(
                (POSTER_WIDTH_DP * d).toInt(),
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins((5 * d).toInt(), (4 * d).toInt(), (5 * d).toInt(), (8 * d).toInt())
            }
            else -> RecyclerView.LayoutParams(
                (LIVE_WIDTH_DP * d).toInt(),
                (LIVE_HEIGHT_DP * d).toInt()
            ).apply {
                setMargins((5 * d).toInt(), (4 * d).toInt(), (5 * d).toInt(), (8 * d).toInt())
            }
        }
        return VH(root, viewType)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(items[position], position)
    }

    inner class VH(private val root: View, private val viewType: Int) : RecyclerView.ViewHolder(root) {
        fun bind(item: Item, position: Int) {
            root.setOnClickListener { onClick(item) }
            when (item) {
                is Item.Movie -> bindMovie(item.value)
                is Item.Series -> bindSeries(item.value)
                is Item.Live -> bindLive(item.value, position)
                is Item.Category -> bindCategory(item.value)
            }
        }

        private fun bindMovie(movie: VodStream) {
            val poster = root.findViewById<ImageView>(R.id.iv_poster)
            val title = root.findViewById<TextView>(R.id.tv_title)
            val rating = root.findViewById<TextView>(R.id.tv_rating)
            val fav = root.findViewById<TextView>(R.id.btn_fav)
            title.text = movie.name
            rating.text = buildString {
                movie.rating?.trim()?.takeIf { it.isNotBlank() && it != "0" && it != "0.0" }?.let { append("★ $it") }
                movie.releaseDate?.let { Regex("\\\\d{4}").find(it)?.value }?.let {
                    if (isNotEmpty()) append("  •  ")
                    append(it)
                }
            }
            rating.setTextColor(ThemeManager.palette().accent)
            val favId = "movie_${movie.streamId}"
            fun syncFav() {
                val yes = FavouritesManager.contains(root.context, favId)
                fav.text = if (yes) "♥" else "♡"
                fav.setTextColor(if (yes) 0xFFFF2222.toInt() else 0xFFFFFFFF.toInt())
            }
            syncFav()
            fav.setOnClickListener {
                if (FavouritesManager.contains(root.context, favId)) FavouritesManager.remove(root.context, favId)
                else FavouritesManager.addOrUpdate(root.context, FavouriteItem(favId, FavType.MOVIE, movie.name, movie.streamIcon ?: "", streamId = movie.streamId))
                syncFav()
            }
            poster.setImageDrawable(null)
            poster.setBackgroundColor(ThemeManager.palette().bgMid)
            if (!movie.streamIcon.isNullOrBlank()) Glide.with(root.context).load(movie.streamIcon).centerCrop().into(poster)
            applyFocus(title)
        }

        private fun bindSeries(show: SeriesStream) {
            val poster = root.findViewById<ImageView>(R.id.iv_poster)
            val title = root.findViewById<TextView>(R.id.tv_title)
            val rating = root.findViewById<TextView>(R.id.tv_rating)
            val fav = root.findViewById<TextView>(R.id.btn_fav)
            title.text = show.name
            rating.text = buildString {
                show.rating?.trim()?.takeIf { it.isNotBlank() && it != "0" && it != "0.0" }?.let { append("★ $it") }
                show.releaseDate?.let { Regex("\\\\d{4}").find(it)?.value }?.let {
                    if (isNotEmpty()) append("  •  ")
                    append(it)
                }
            }
            rating.setTextColor(ThemeManager.palette().accent)
            val favId = "series_${show.seriesId}"
            fun syncFav() {
                val yes = FavouritesManager.contains(root.context, favId)
                fav.text = if (yes) "♥" else "♡"
                fav.setTextColor(if (yes) 0xFFFF2222.toInt() else 0xFFFFFFFF.toInt())
            }
            syncFav()
            fav.setOnClickListener {
                if (FavouritesManager.contains(root.context, favId)) FavouritesManager.remove(root.context, favId)
                else FavouritesManager.addOrUpdate(root.context, FavouriteItem(favId, FavType.SERIES, show.name, show.cover ?: "", seriesId = show.seriesId))
                syncFav()
            }
            poster.setImageDrawable(null)
            poster.setBackgroundColor(ThemeManager.palette().bgMid)
            if (!show.cover.isNullOrBlank()) Glide.with(root.context).load(show.cover).centerCrop().into(poster)
            applyFocus(title)
        }

        private fun bindLive(channel: LiveStream, position: Int) {
            val number = root.findViewById<TextView>(R.id.tv_number)
            val name = root.findViewById<TextView>(R.id.tv_name)
            val now = root.findViewById<TextView>(R.id.tv_now)
            val fav = root.findViewById<TextView>(R.id.btn_fav)
            number.text = String.format("%03d", position + 1)
            name.text = channel.name
            now.text = "LIVE TV"
            fun syncFav() {
                val yes = FavouritesManager.containsLive(root.context, channel.streamId)
                fav.text = if (yes) "♥" else "♡"
                fav.setTextColor(if (yes) 0xFFFF3030.toInt() else 0xFFFFFFFF.toInt())
            }
            syncFav()
            fav.setOnClickListener {
                if (FavouritesManager.containsLive(root.context, channel.streamId)) FavouritesManager.removeLive(root.context, channel.streamId)
                else FavouritesManager.addLiveChannel(root.context, channel.name, channel.streamId, "", channel.streamIcon)
                syncFav()
            }
            applyFocus(name)
        }

        private fun bindCategory(category: LiveCategory) {
            root.findViewById<TextView>(R.id.tv_category_title).text = category.categoryName
            root.findViewById<TextView>(R.id.tv_category_subtitle).text = "LIVE TV CATEGORY"
            applyFocus(root.findViewById(R.id.tv_category_title))
        }

        private fun applyFocus(title: TextView) {
            val d = root.resources.displayMetrics.density
            root.setOnFocusChangeListener { _, hasFocus ->
                val p = ThemeManager.palette()
                root.scaleX = if (hasFocus) 1.07f else 1f
                root.scaleY = if (hasFocus) 1.07f else 1f
                root.elevation = if (hasFocus) 8f * d else 0f
                title.setTextColor(if (hasFocus) p.accent else Color.WHITE)
            }
        }
    }
}
