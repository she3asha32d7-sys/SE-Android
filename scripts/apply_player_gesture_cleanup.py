from pathlib import Path

path = Path("app/src/main/java/com/orbital/iptv/ui/player/PlayerActivity.kt")
s = path.read_text()

old_move = '''            MotionEvent.ACTION_MOVE->{val dy=e.y-downY; if(kotlin.math.abs(dy)>16){ if(e.x<widthOfPlayer()/3){adjustBrightness(-dy/250f);downY=e.y}else if(e.x>widthOfPlayer()*2/3){adjustVolume(-dy/200f);downY=e.y} } }
'''
if old_move not in s:
    if 'adjustBrightness(' not in s and 'adjustVolume(' not in s:
        raise SystemExit("gesture code already absent; refusing unrelated rewrite")
    raise SystemExit("expected player volume/brightness gesture block not found")
s = s.replace(old_move, '''            # Vertical touch movement is intentionally ignored. Brightness/volume are not changed by screen-side gestures.
''', 1)

old_helpers = '''    private fun adjustVolume(delta:Float){val am=getSystemService(AUDIO_SERVICE) as AudioManager; val cur=am.getStreamVolume(AudioManager.STREAM_MUSIC); val max=am.getStreamMaxVolume(AudioManager.STREAM_MUSIC); am.setStreamVolume(AudioManager.STREAM_MUSIC,(cur+(delta*max)).toInt().coerceIn(0,max),0); Toast.makeText(this,"VOLUME ${am.getStreamVolume(AudioManager.STREAM_MUSIC)*100/max}%",Toast.LENGTH_SHORT).show()}
    private fun adjustBrightness(delta:Float){val lp=window.attributes;lp.screenBrightness=(if(lp.screenBrightness<0)0.5f else lp.screenBrightness)+delta;lp.screenBrightness=lp.screenBrightness.coerceIn(0.05f,1f);window.attributes=lp;Toast.makeText(this,"BRIGHTNESS ${(lp.screenBrightness*100).toInt()}%",Toast.LENGTH_SHORT).show()}
'''
if old_helpers in s:
    s = s.replace(old_helpers, '', 1)
elif 'adjustBrightness(' in s or 'adjustVolume(' in s:
    raise SystemExit("gesture helpers found but with unexpected formatting")

s = s.replace('import android.media.AudioManager\\n', '', 1)
path.write_text(s)
print("Removed player screen-side volume/brightness gestures.")