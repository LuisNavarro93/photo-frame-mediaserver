-- Draws a date/clock, and an icon-forward today/tomorrow weather summary,
-- in the top-right corner of the mpv window during the slideshow.
local mp = require "mp"
local utils = require "mp.utils"

local obj_overlay = mp.create_osd_overlay("ass-events")
obj_overlay.res_x = 1280   -- virtual canvas; mpv scales it to the real screen
obj_overlay.res_y = 720

-- clock
local int_margin_x    = 65   -- gap from the right edge (incl. ~1cm extra left shift)
local int_offset_down = 70   -- how far below the top corner to sit (~8% of height)
local int_date_size   = 38
local int_time_size   = 68
local str_date_format = "%a %d %b %Y"
local str_time_format = "%H:%M"

-- weather (Open-Meteo: free, no API key -- https://open-meteo.com)
-- "Icon-forward hero" layout: today's icon + daily low-high lead, with a
-- rain-start time below (omitted entirely on a dry day); tomorrow trails
-- as a single small line, also omitted entirely if tomorrow stays dry.
local bool_weather_enabled  = true
local str_weather_lat       = "20.9674"   -- Merida, Yucatan, Mexico
local str_weather_lon       = "-89.5926"
local str_weather_tz_param  = "America%2FMerida"  -- URL-encoded timezone
local int_weather_refresh_s = 1800  -- re-fetch every 30 min
local int_hero_size         = 50    -- today's icon + low-high line
local int_rain_size         = 24    -- "Rain from ..." line
local int_tomorrow_size     = 22    -- trailing tomorrow line
local int_rain_threshold    = 50    -- precipitation_probability %% that counts as "rain"

local str_weather_url = string.format(
    "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s" ..
    "&daily=temperature_2m_max,temperature_2m_min,weather_code" ..
    "&hourly=precipitation_probability" ..
    "&timezone=%s&forecast_days=2&temperature_unit=celsius",
    str_weather_lat, str_weather_lon, str_weather_tz_param)

-- WMO weather code -> {condition text, glyph}. Glyphs are plain Unicode
-- symbols (not color emoji) so they inherit the clock's fill/outline color.
-- These are daily (whole-day) codes, so there's no day/night variant here.
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

local function wx_lookup_daily(int_code)
    local tup_entry = dict_wmo[int_code] or {"\226\128\148", "\226\152\129"}
    return tup_entry[1], tup_entry[2]
end

-- First hour (0-23), scanning forward from local midnight, whose
-- precipitation_probability crosses int_rain_threshold. arr_probs is the
-- full 48-entry hourly array (today's 24 hours then tomorrow's);
-- int_day_offset is 0 for today, 24 for tomorrow. Returns nil on a dry day.
local function rain_start_hour(arr_probs, int_day_offset)
    for int_h = 0, 23 do
        local num_prob = arr_probs[int_day_offset + int_h + 1]
        if num_prob and num_prob >= int_rain_threshold then
            return int_h
        end
    end
    return nil
end

local function fmt_hour12(int_h)
    local int_h12 = int_h % 12
    if int_h12 == 0 then
        int_h12 = 12
    end
    local str_ampm = (int_h < 12) and "AM" or "PM"
    return int_h12 .. " " .. str_ampm
end

local obj_weather = { bool_loaded = false }

-- One entry per on-screen line: its text and font size.
local function build_lines()
    local lst_lines = {
        { str = os.date(str_date_format), size = int_date_size },
        { str = os.date(str_time_format), size = int_time_size },
    }
    if bool_weather_enabled and obj_weather.bool_loaded then
        table.insert(lst_lines, {
            size = int_hero_size,
            str = string.format("%s %d\194\176\226\128\147%d\194\176",
                obj_weather.str_today_glyph, obj_weather.int_today_lo, obj_weather.int_today_hi),
        })
        if obj_weather.int_today_rain_hour then
            table.insert(lst_lines, {
                size = int_rain_size,
                str = "Rain from " .. fmt_hour12(obj_weather.int_today_rain_hour),
            })
        end
        if obj_weather.int_tomorrow_rain_hour then
            table.insert(lst_lines, {
                size = int_tomorrow_size,
                str = string.format("%s Tomorrow %d\194\176\226\128\147%d\194\176, rain %s",
                    obj_weather.str_tomorrow_glyph, obj_weather.int_tomorrow_lo,
                    obj_weather.int_tomorrow_hi, fmt_hour12(obj_weather.int_tomorrow_rain_hour)),
            })
        end
    end
    return lst_lines
end

local function update()
    local lst_lines = build_lines()

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
        if not obj_data or not obj_data.daily or not obj_data.hourly then
            return
        end

        local obj_daily = obj_data.daily
        local arr_probs = obj_data.hourly.precipitation_probability

        obj_weather.int_today_lo = math.floor(obj_daily.temperature_2m_min[1] + 0.5)
        obj_weather.int_today_hi = math.floor(obj_daily.temperature_2m_max[1] + 0.5)
        local _, str_today_glyph = wx_lookup_daily(obj_daily.weather_code[1])
        obj_weather.str_today_glyph = str_today_glyph

        obj_weather.int_tomorrow_lo = math.floor(obj_daily.temperature_2m_min[2] + 0.5)
        obj_weather.int_tomorrow_hi = math.floor(obj_daily.temperature_2m_max[2] + 0.5)
        local _, str_tomorrow_glyph = wx_lookup_daily(obj_daily.weather_code[2])
        obj_weather.str_tomorrow_glyph = str_tomorrow_glyph

        obj_weather.int_today_rain_hour    = rain_start_hour(arr_probs, 0)
        obj_weather.int_tomorrow_rain_hour  = rain_start_hour(arr_probs, 24)

        obj_weather.bool_loaded = true
        update()
    end)
end

mp.add_periodic_timer(1, update)
mp.register_event("file-loaded", update)
mp.add_periodic_timer(int_weather_refresh_s, fetch_weather)
update()
fetch_weather()
