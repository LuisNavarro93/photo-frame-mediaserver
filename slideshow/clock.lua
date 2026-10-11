-- Draws a date/clock, and current + tomorrow's weather, in the top-right
-- corner of the mpv window during the slideshow.
local mp = require "mp"
local utils = require "mp.utils"

local obj_overlay = mp.create_osd_overlay("ass-events")
obj_overlay.res_x = 1280   -- virtual canvas; mpv scales it to the real screen
obj_overlay.res_y = 720
obj_overlay.z = 1   -- draw above the backing chips

-- a soft rounded "pill badge" chip behind every line (date, time, each
-- weather line), for contrast against bright photos. Each chip is sized to
-- its own line (longest line = widest chip, not a single shared box), and
-- all of them are drawn as one multi-shape ASS vector path in a single
-- lower-z overlay.
local obj_box_overlay = mp.create_osd_overlay("ass-events")
obj_box_overlay.res_x = 1280
obj_box_overlay.res_y = 720
obj_box_overlay.z = 0

-- clock
local int_margin_x    = 65   -- gap from the right edge (incl. ~1cm extra left shift)
local int_offset_down = 70   -- how far below the top corner to sit (~8% of height)
local int_date_size   = 38
local int_time_size   = 68
local str_date_format = "%a %d %b %Y"
local str_time_format = "%H:%M"

-- pill chips
local bool_box_enabled = true
-- mpv/libass expose no real text-measurement API, so chip size comes from
-- an average-glyph-width heuristic (calibrated for the bold sans the OSD
-- falls back to) rather than a pixel-exact metric. The same
-- num_line_height_ratio is used to advance both the text's \N stack and
-- the chips' own vertical cursor, so they can't drift apart from each
-- other even though neither is a real font-metrics value.
local num_char_width_ratio  = 0.58   -- average glyph advance, as a fraction of font size
local num_line_height_ratio = 1.15   -- line pitch, as a multiple of font size
local int_chip_pad_x = 10   -- horizontal breathing room inside each chip
local int_chip_pad_y = 5    -- vertical breathing room inside each chip
local int_gap_size   = 16   -- font-size-equivalent of the blank line between
                             -- chips -- real (if invisible) text, so the gap
                             -- advances the \N stack exactly like any other
                             -- line and can't desync from the chips below it
local str_box_alpha  = "&HCC&"  -- ASS alpha: 00 opaque .. FF transparent (80% transparent)

-- weather (Open-Meteo: free, no API key -- https://open-meteo.com)
local bool_weather_enabled  = true
local str_weather_lat       = "20.9674"   -- Merida, Yucatan, Mexico
local str_weather_lon       = "-89.5926"
local str_weather_tz_param  = "America%2FMerida"  -- URL-encoded timezone
local int_weather_refresh_s = 1800  -- re-fetch every 30 min
local int_weather_size      = 35    -- current temp + condition line
local int_weather_sub_size  = 25    -- feels-like / hi-lo / humidity / wind
local int_label_size        = 20    -- "TOMORROW" label

local str_weather_url = string.format(
    "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s" ..
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day" ..
    "&daily=temperature_2m_max,temperature_2m_min,weather_code" ..
    "&timezone=%s&forecast_days=2&temperature_unit=celsius&wind_speed_unit=kmh",
    str_weather_lat, str_weather_lon, str_weather_tz_param)

-- WMO weather code -> {condition text, glyph}. Glyphs are plain Unicode
-- symbols (not color emoji) so they inherit the clock's fill/outline color.
local dict_wmo = {
    [0]  = {"Clear",            "\226\152\128"},  -- ☀
    [1]  = {"Mostly Clear",     "\226\155\133"},  -- ⛅
    [2]  = {"Partly Cloudy",    "\226\155\133"},  -- ⛅
    [3]  = {"Overcast",         "\226\152\129"},  -- ☁
    [45] = {"Fog",              "\226\152\129"},
    [48] = {"Fog",              "\226\152\129"},
    [51] = {"Light Drizzle",    "\226\152\148"},  -- ☔
    [53] = {"Drizzle",          "\226\152\148"},
    [55] = {"Heavy Drizzle",    "\226\152\148"},
    [56] = {"Freezing Drizzle", "\226\152\148"},
    [57] = {"Freezing Drizzle", "\226\152\148"},
    [61] = {"Light Rain",       "\226\152\148"},
    [63] = {"Rain",             "\226\152\148"},
    [65] = {"Heavy Rain",       "\226\152\148"},
    [66] = {"Freezing Rain",    "\226\152\148"},
    [67] = {"Freezing Rain",    "\226\152\148"},
    [71] = {"Light Snow",       "\226\157\132"},  -- ❄
    [73] = {"Snow",             "\226\157\132"},
    [75] = {"Heavy Snow",       "\226\157\132"},
    [77] = {"Snow Grains",      "\226\157\132"},
    [80] = {"Rain Showers",     "\226\152\148"},
    [81] = {"Rain Showers",     "\226\152\148"},
    [82] = {"Heavy Showers",    "\226\152\148"},
    [85] = {"Snow Showers",     "\226\157\132"},
    [86] = {"Snow Showers",     "\226\157\132"},
    [95] = {"Thunderstorm",     "\226\152\148"},
    [96] = {"Thunderstorm",     "\226\152\148"},
    [99] = {"Thunderstorm",     "\226\152\148"},
}
local str_moon_glyph = "\226\152\190"  -- ☾

local function wx_lookup(int_code, int_is_day)
    local tup_entry = dict_wmo[int_code] or {"\226\128\148", "\226\152\129"}
    local str_cond, str_glyph = tup_entry[1], tup_entry[2]
    if int_code == 0 and int_is_day == 0 then
        str_glyph = str_moon_glyph
    end
    return str_cond, str_glyph
end

local obj_weather = { bool_loaded = false }

-- Number of Unicode codepoints in str_text (not bytes -- multi-byte glyphs
-- like deg/weather symbols must count as one "character").
local function count_chars(str_text)
    local int_count = 0
    for _ in str_text:gmatch("[%z\1-\127\194-\253][\128-\191]*") do
        int_count = int_count + 1
    end
    return int_count
end

local function measure_width(str_text, int_size)
    return count_chars(str_text) * int_size * num_char_width_ratio
end

-- One entry per on-screen line: its text (for width measurement, empty for
-- spacers), its font size (for both width and line pitch) and whether it
-- gets its own pill chip. A thin, chip-less spacer line is interleaved
-- between every pair of real lines so the gap between chips is real (if
-- invisible) vertical space that both the text and the chips advance
-- through identically.
local function build_lines()
    local lst_raw = {
        { str = os.date(str_date_format), size = int_date_size },
        { str = os.date(str_time_format), size = int_time_size },
    }
    if bool_weather_enabled and obj_weather.bool_loaded then
        table.insert(lst_raw, {
            size = int_weather_size,
            str = string.format("%s %d\194\176  %s",
                obj_weather.str_glyph, obj_weather.int_temp, obj_weather.str_condition),
        })
        table.insert(lst_raw, {
            size = int_weather_sub_size,
            str = string.format("Feels %d\194\176 \194\183 H %d\194\176 L %d\194\176",
                obj_weather.int_feels, obj_weather.int_hi, obj_weather.int_lo),
        })
        table.insert(lst_raw, {
            size = int_weather_sub_size,
            str = string.format("%d%% hum \194\183 %d km/h wind",
                obj_weather.int_humidity, obj_weather.int_wind),
        })
        table.insert(lst_raw, { size = int_label_size, str = "TOMORROW" })
        table.insert(lst_raw, {
            size = int_weather_sub_size,
            str = string.format("%s %d\194\176 / %d\194\176  %s",
                obj_weather.str_tomorrow_glyph, obj_weather.int_tomorrow_hi,
                obj_weather.int_tomorrow_lo, obj_weather.str_tomorrow_condition),
        })
    end

    local lst_lines = {}
    for int_i, obj_line in ipairs(lst_raw) do
        if int_i > 1 then
            table.insert(lst_lines, { str = "", size = int_gap_size, bool_chip = false })
        end
        obj_line.bool_chip = true
        table.insert(lst_lines, obj_line)
    end
    return lst_lines
end

local function fmt_num(num_value)
    return string.format("%.1f", num_value)
end

-- A rounded-rect ASS draw path (cubic-bezier corners), in local coordinates
-- with its own top-left at (int_origin_x, int_origin_y).
local function rounded_rect_path(int_origin_x, int_origin_y, int_w, int_h, int_r)
    local num_k = int_r * 0.5523
    local function pt(num_x, num_y)
        return fmt_num(int_origin_x + num_x) .. " " .. fmt_num(int_origin_y + num_y)
    end
    return "m " .. pt(int_r, 0) ..
        " l " .. pt(int_w - int_r, 0) ..
        " b " .. pt(int_w - int_r + num_k, 0) .. " " .. pt(int_w, int_r - num_k) .. " " .. pt(int_w, int_r) ..
        " l " .. pt(int_w, int_h - int_r) ..
        " b " .. pt(int_w, int_h - int_r + num_k) .. " " .. pt(int_w - int_r + num_k, int_h) .. " " .. pt(int_w - int_r, int_h) ..
        " l " .. pt(int_r, int_h) ..
        " b " .. pt(int_r - num_k, int_h) .. " " .. pt(0, int_h - int_r + num_k) .. " " .. pt(0, int_h - int_r) ..
        " l " .. pt(0, int_r) ..
        " b " .. pt(0, int_r - num_k) .. " " .. pt(int_r - num_k, 0) .. " " .. pt(int_r, 0)
end

local function draw_box(lst_lines)
    if not bool_box_enabled then
        obj_box_overlay.data = ""
        obj_box_overlay:update()
        return
    end

    local lst_chips = {}
    local int_max_width = 0
    local int_cursor_y = 0
    for _, obj_line in ipairs(lst_lines) do
        local int_line_h = obj_line.size * num_line_height_ratio
        if obj_line.bool_chip then
            local int_chip_w = measure_width(obj_line.str, obj_line.size) + 2 * int_chip_pad_x
            local int_chip_h = int_line_h + 2 * int_chip_pad_y
            table.insert(lst_chips, { w = int_chip_w, h = int_chip_h, y = int_cursor_y - int_chip_pad_y })
            if int_chip_w > int_max_width then
                int_max_width = int_chip_w
            end
        end
        int_cursor_y = int_cursor_y + int_line_h
    end

    local lst_paths = {}
    for _, obj_chip in ipairs(lst_chips) do
        local int_radius = obj_chip.h / 2  -- fully rounded ends, true "pill" shape
        local int_origin_x = int_max_width - obj_chip.w  -- right-align every chip
        table.insert(lst_paths, rounded_rect_path(int_origin_x, obj_chip.y, obj_chip.w, obj_chip.h, int_radius))
    end

    local int_box_x = (obj_overlay.res_x - int_margin_x) + int_chip_pad_x
    local int_box_y = int_offset_down
    obj_box_overlay.data = string.format(
        "{\\an9\\pos(%d,%d)\\1c&H000000&\\alpha%s\\bord0\\shad0\\p1}%s",
        int_box_x, int_box_y, str_box_alpha, table.concat(lst_paths, " "))
    obj_box_overlay:update()
end

local function update()
    local lst_lines = build_lines()
    draw_box(lst_lines)

    local lst_parts = {}
    for _, obj_line in ipairs(lst_lines) do
        table.insert(lst_parts, string.format("{\\fs%d}%s", obj_line.size, obj_line.str))
    end

    -- \an9 = anchor top-right; white fill, black outline so it reads on any photo.
    obj_overlay.data = string.format(
        "{\\an9\\pos(%d,%d)\\b1\\bord2.5\\shad1\\1c&HFFFFFF&\\3c&H000000&\\4c&H000000&}%s",
        obj_overlay.res_x - int_margin_x, int_offset_down,
        table.concat(lst_parts, "\\N"))
    obj_overlay:update()
end

local function fetch_weather()
    if not bool_weather_enabled then return end
    mp.command_native_async({
        name = "subprocess",
        args = {"curl", "-s", "--max-time", "10", str_weather_url},
        capture_stdout = true,
        playback_only = false,
    }, function(bool_ok, obj_result)
        if not bool_ok or not obj_result or obj_result.status ~= 0 then
            return
        end
        local obj_data = utils.parse_json(obj_result.stdout or "")
        if not obj_data or not obj_data.current or not obj_data.daily then
            return
        end

        local obj_cur, obj_daily = obj_data.current, obj_data.daily
        local str_cond, str_glyph = wx_lookup(obj_cur.weather_code, obj_cur.is_day)

        obj_weather.str_glyph     = str_glyph
        obj_weather.str_condition = str_cond
        obj_weather.int_temp      = math.floor(obj_cur.temperature_2m + 0.5)
        obj_weather.int_feels     = math.floor(obj_cur.apparent_temperature + 0.5)
        obj_weather.int_humidity  = math.floor(obj_cur.relative_humidity_2m + 0.5)
        obj_weather.int_wind      = math.floor(obj_cur.wind_speed_10m + 0.5)
        obj_weather.int_hi        = math.floor(obj_daily.temperature_2m_max[1] + 0.5)
        obj_weather.int_lo        = math.floor(obj_daily.temperature_2m_min[1] + 0.5)

        local str_tom_cond, str_tom_glyph = wx_lookup(obj_daily.weather_code[2], 1)
        obj_weather.str_tomorrow_glyph     = str_tom_glyph
        obj_weather.str_tomorrow_condition = str_tom_cond
        obj_weather.int_tomorrow_hi = math.floor(obj_daily.temperature_2m_max[2] + 0.5)
        obj_weather.int_tomorrow_lo = math.floor(obj_daily.temperature_2m_min[2] + 0.5)

        obj_weather.bool_loaded = true
        update()
    end)
end

mp.add_periodic_timer(1, update)
mp.register_event("file-loaded", update)
mp.add_periodic_timer(int_weather_refresh_s, fetch_weather)
update()
fetch_weather()
