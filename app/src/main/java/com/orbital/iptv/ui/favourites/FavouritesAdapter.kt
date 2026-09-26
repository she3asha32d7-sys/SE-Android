package com.orbital.iptv.ui.favourites

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.orbital.iptv.R
import com.orbital.iptv.data.model.FavType
import com.orbital.iptv.data.model.FavouriteItem
import com.orbital.iptv.utils.FavouritesManager
import com.orbital.iptv.utils.ThemeManager

class FavouritesAdapter(
    private val onClick: (FavouriteItem) -> Unit,
    private val onLongPress: (FavouriteItem) -> Unit
) : RecyclerView.Adapter<FavouritesAdapter.VH>() {

    private var items: List<FavouriteItem> = emptyList()

    companion object {
        private const val MOVIE = 1
        private const val SERIES = 2
        private const val LIVE = 3
        private const val CATEGORY = 4
        private const val MOVIE_SERIES_WIDTH_DP = 170
        private const val LIVE_CATEGORY_WIDTH_DP = 182
        private const val LIVE_CATEGORY_HEIGHT_DP = 168
    }

    fun submitList(list: List<FavouriteItem>) {
        items = list
        notifyDataSetChanged()
    }

    override fun getItemCount() = items.size

    override fun getItemViewType(position: Int) = when (items[position].type) {
        FavType.MOVIE -> MOVIE
        FavType.SERIES, FavType.EPISODE -> SERIES
        FavType.LIVE -> LIVE
        FavType.CATEGORY -> CATEGORY
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
                (MOVIE_SERIES_WIDTH_DP * d).toInt(),
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                setMargins((5 * d).toInt(), (4 * d).toInt(), (5 * d).toInt(), (8 * d).toInt())
            }
            else -> RecyclerView.LayoutParams(
                (LIVE_CATEGORY_WIDTH_DP * d).toInt(),
                (LIVE_CATEGORY_HEIGHT_DP * d).toInt()
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
        fun bind(item: FavouriteItem, position: Int) {
            root.setOnClickListener { onClick(item) }
            root.setOnLongClickListener { onLongPress(item); true }
            when (viewType) {
                MOVIE, SERIES -> bindPoster(item)
                LIVE -> bindLive(item, position)
                CATEGORY -> bindCategory(item)
            }
        }

        private fun bindPoster(item: FavouriteItem) {
            val poster = root.findViewById<ImageView>(R.id.iv_poster)
            val title = root.findViewById<TextView>(R.id.tv_title)
            val rating = root.findViewById<TextView>(R.id.tv_rating)
            val fav = root.findViewById<TextView>(R.id.btn_fav)
            title.text = if (item.type == FavType.SERIES || item.type == FavType.EPISODE) {
                item.title.substringBefore(" — ").ifBlank { item.title }
            } else item.title
            rating.text = when {
                item.hasResume -> "▶ ${FavouritesManager.formatDuration(item.resumePositionMs)}" +
                    if (item.durationMs > 0) " / ${FavouritesManager.formatDuration(item.durationMs)}" else ""
                item.type == FavType.SERIES || item.type == FavType.EPISODE -> {
                    if (item.season.isNotBlank() && item.episodeNum > 0) "S${item.season}E${"%02d".format(item.episodeNum)}" else "SERIES"
                }
                else -> "MOVIE"
            }
            rating.setTextColor(ThemeManager.palette().accent)
            fun syncFav() {
                val checked = FavouritesManager.contains(root.context, item.id)
                fav.text = if (checked) "♥" else "♡"
                fav.setTextColor(if (checked) 0xFFFF2222.toInt() else 0xFFFFFFFF.toInt())
            }
            syncFav()
            fav.setOnClickListener {
                if (FavouritesManager.contains(root.context, item.id)) FavouritesManager.remove(root.context, item.id)
                else FavouritesManager.addOrUpdate(root.context, item)
                syncFav()
            }
            poster.setBackgroundColor(ThemeManager.palette().bgMid)
            poster.setImageDrawable(null)
            if (item.artUrl.isNotBlank()) Glide.with(root.context).load(item.artUrl).centerCrop().into(poster)
            applyFocus(root, title)
        }

        private fun bindLive(item: FavouriteItem, position: Int) {
            val number = root.findViewById<TextView>(R.id.tv_number)
            val name = root.findViewById<TextView>(R.id.tv_name)
            val now = root.findViewById<TextView>(R.id.tv_now)
            val fav = root.findViewById<TextView>(R.id.btn_fav)
            number.text = String.format("%03d", position + 1)
            name.text = item.title
            now.text = "LIVE TV"
            fun syncFav() {
                val checked = FavouritesManager.containsLive(root.context, item.streamId)
                fav.text = if (checked) "♥" else "♡"
                fav.setTextColor(if (checked) 0xFFFF3030.toInt() else 0xFFFFFFFF.toInt())
            }
            syncFav()
            fav.setOnClickListener {
                if (FavouritesManager.containsLive(root.context, item.streamId)) FavouritesManager.removeLive(root.context, item.streamId)
                else FavouritesManager.addLiveChannel(root.context, item.title, item.streamId, item.streamUrl, item.artUrl)
                syncFav()
            }
            applyFocus(root, name)
        }

        private fun bindCategory(item: FavouriteItem) {
            val title = root.findViewById<TextView>(R.id.tv_category_title)
            val subtitle = root.findViewById<TextView>(R.id.tv_category_subtitle)
            title.text = item.title
            subtitle.text = when (item.categoryType.uppercase()) {
                "MOVIES" -> "MOVIES CATEGORY"
                "SERIES" -> "SERIES CATEGORY"
                "LIVE" -> "LIVE TV CATEGORY"
                else -> "CATEGORY"
            }
            applyFocus(root, title)
        }

        private fun applyFocus(view: View, title: TextView) {
            val d = view.resources.displayMetrics.density
            view.setOnFocusChangeListener { _, hasFocus ->
                val p = ThemeManager.palette()
                view.scaleX = if (hasFocus) 1.035f else 1f
                view.scaleY = if (hasFocus) 1.035f else 1f
                view.elevation = if (hasFocus) 8f * d else 0f
                title.setTextColor(if (hasFocus) p.accent else 0xFFFFFFFF.toInt())
            }
        }
    }
}