-- Draws a date + clock in the top-right corner of the mpv window during the slideshow.
local mp = require "mp"

local obj_overlay = mp.create_osd_overlay("ass-events")
obj_overlay.res_x = 1280   -- virtual canvas; mpv scales it to the real screen
obj_overlay.res_y = 720

local int_margin_x    = 24   -- gap from the right edge
local int_offset_down = 70   -- how far below the top corner to sit (~8% of height)
local int_date_size   = 30   -- date font size
local int_time_size   = 54   -- clock font size
local str_date_format = "%a %d %b %Y"
local str_time_format = "%H:%M"

local function update()
    local str_date = os.date(str_date_format)
    local str_time = os.date(str_time_format)
    -- \an9 = anchor top-right; white fill, black outline so it reads on any photo.
    obj_overlay.data = string.format(
        "{\\an9\\pos(%d,%d)\\b1\\bord2.5\\shad1\\1c&HFFFFFF&\\3c&H000000&\\4c&H000000&}" ..
        "{\\fs%d}%s\\N{\\fs%d}%s",
        obj_overlay.res_x - int_margin_x, int_offset_down,
        int_date_size, str_date, int_time_size, str_time)
    obj_overlay:update()
end

mp.add_periodic_timer(1, update)
mp.register_event("file-loaded", update)
update()
