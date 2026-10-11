-- Draws a date/clock, and current + tomorrow's weather, in the top-right
-- corner of the mpv window during the slideshow.
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

local function build_weather_block()
    if not (bool_weather_enabled and obj_weather.bool_loaded) then
        return ""
    end
    local str_now = string.format(
        "{\\fs%d}%s %d\194\176  %s\\N" ..
        "{\\fs%d}Feels %d\194\176 \194\183 H %d\194\176 L %d\194\176\\N" ..
        "{\\fs%d}%d%% hum \194\183 %d km/h wind",
        int_weather_size, obj_weather.str_glyph, obj_weather.int_temp, obj_weather.str_condition,
        int_weather_sub_size, obj_weather.int_feels, obj_weather.int_hi, obj_weather.int_lo,
        int_weather_sub_size, obj_weather.int_humidity, obj_weather.int_wind)

    local str_tomorrow = string.format(
        "\\N{\\fs10}\\N{\\fs%d}TOMORROW\\N{\\fs%d}%s %d\194\176 / %d\194\176  %s",
        int_label_size,
        int_weather_sub_size, obj_weather.str_tomorrow_glyph,
        obj_weather.int_tomorrow_hi, obj_weather.int_tomorrow_lo, obj_weather.str_tomorrow_condition)

    return str_now .. str_tomorrow
end

local function update()
    local str_date = os.date(str_date_format)
    local str_time = os.date(str_time_format)

    -- \an9 = anchor top-right; white fill, black outline so it reads on any photo.
    local str_body = string.format(
        "{\\an9\\pos(%d,%d)\\b1\\bord2.5\\shad1\\1c&HFFFFFF&\\3c&H000000&\\4c&H000000&}" ..
        "{\\fs%d}%s\\N{\\fs%d}%s",
        obj_overlay.res_x - int_margin_x, int_offset_down,
        int_date_size, str_date, int_time_size, str_time)

    local str_weather = build_weather_block()
    if str_weather ~= "" then
        str_body = str_body .. "\\N" .. str_weather
    end

    obj_overlay.data = str_body
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
