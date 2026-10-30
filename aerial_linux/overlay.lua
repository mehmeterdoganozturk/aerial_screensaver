-- Aerial Screensaver OSD & macOS-Style Lock Overlay (mpv Lua script)
local mp = require 'mp'
local utils = require 'mp.utils'
pcall(function() os.setlocale("") end)

local function parse_bool(v, default)
    if v == nil then return default end
    return (v == "yes" or v == "true" or v == "1" or v == true)
end

local options = {
    show_location = parse_bool(mp.get_opt("aerial_show_location"), false),
    show_clock = parse_bool(mp.get_opt("aerial_show_clock"), true),
    clock_24h = parse_bool(mp.get_opt("aerial_clock_24h"), true),
    is_preview = parse_bool(mp.get_opt("aerial_preview"), false),
    lock_on_exit = parse_bool(mp.get_opt("aerial_lock_on_exit"), true),
    lock_mode = mp.get_opt("aerial_lock_mode") or "macos",
    lock_timeout = tonumber(mp.get_opt("aerial_lock_timeout")) or 20,
    user = mp.get_opt("aerial_user") or os.getenv("USER") or "user",
    full_name = mp.get_opt("aerial_full_name") or os.getenv("USER") or "User",
    initials = mp.get_opt("aerial_initials") or "U",
    unlock_file = mp.get_opt("aerial_unlock_file") or "",
    fallback_file = mp.get_opt("aerial_fallback_file") or "",
    screen_name = mp.get_opt("aerial_screen_name") or "",
    active_mon_file = mp.get_opt("aerial_active_mon_file") or "",
    focus_file = mp.get_opt("aerial_focus_file") or "",
    python_bin = mp.get_opt("aerial_python_bin") or "python3",
    auth_script = mp.get_opt("aerial_auth_script") or "",
}

if options.auth_script == "" then
    local home = os.getenv("HOME") or "/home/erdogan"
    options.auth_script = home .. "/.local/share/aerial-linux/aerial_linux/auth.py"
end

-- OSD Overlay setup
local ov = mp.create_osd_overlay("ass-events")
ov.res_x = 1920
ov.res_y = 1080

local start_time = mp.get_time()
local grace_period = 1.0     -- seconds to ignore initial launch jitter
local motion_threshold = 18 -- pixels movement to count as deliberate activity
local anchor_mouse = nil
local last_mouse_pos = { x = 0, y = 0 }
local meta_list = {}
local cur_title = ""
local cur_sub = ""
local loc_show_until = start_time + 14.0

-- Lock Card State
local is_macos_mode = (not options.is_preview) and options.lock_on_exit and (options.lock_mode == "macos")
local card_visible = false
local password_buffer = ""
local is_verifying = false
local error_message = ""
local failed_count = 0
local shake_offset_x = 0
local shake_timer = nil
local last_activity_time = 0
local timeout_seconds = options.lock_timeout

-- UTF-8 helper functions
local function utf8_pop(str)
    if not str or #str == 0 then return "" end
    local p = #str
    while p > 1 and (str:byte(p) >= 0x80 and str:byte(p) < 0xC0) do
        p = p - 1
    end
    return str:sub(1, p - 1)
end

local function utf8_len(str)
    if not str then return 0 end
    local _, count = string.gsub(str, "[^\128-\193]", "")
    return count
end

-- Load metadata list if passed via script-opts
local opt_meta = mp.get_opt("aerial_meta")
if opt_meta and opt_meta ~= "" then
    local parsed = utils.parse_json(opt_meta)
    if parsed then
        meta_list = parsed
    end
end

-- Updates current video metadata on track switch
local function on_file_loaded()
    local path = mp.get_property("path", "")
    cur_title = ""
    cur_sub = ""
    for _, item in ipairs(meta_list) do
        if item.play_path == path or item.stream_url == path or (item.id and string.find(path, item.id)) then
            cur_title = item.title or ""
            cur_sub = item.subtitle or ""
            break
        end
    end
    if cur_title == "" then
        cur_title = mp.get_property("media-title", "")
    end
    loc_show_until = mp.get_time() + 14.0
end

mp.register_event("file-loaded", on_file_loaded)

-- Forward declaration
local render_overlay

-- Multi-monitor active screen synchronization
local function mark_active_monitor()
    if options.active_mon_file ~= "" and options.screen_name ~= "" then
        local f = io.open(options.active_mon_file, "w")
        if f then
            f:write(options.screen_name .. "\n")
            f:close()
        end
    end
end

local function reset_timeout(seconds)
    last_activity_time = mp.get_time()
    if seconds then
        timeout_seconds = seconds
    else
        timeout_seconds = options.lock_timeout
    end
end

local function show_lock_card()
    if not is_macos_mode then return end
    mark_active_monitor()
    card_visible = true
    error_message = ""
    reset_timeout()
    render_overlay()
end

local function hide_lock_card()
    card_visible = false
    password_buffer = ""
    error_message = ""
    is_verifying = false
    shake_offset_x = 0
    if shake_timer then
        shake_timer:kill()
        shake_timer = nil
    end
    anchor_mouse = nil
    render_overlay()
end

-- Shake animation on password error
local shake_offsets = {-12, 12, -10, 10, -6, 6, -3, 3, 0}
local function run_shake()
    local step_idx = 1
    if shake_timer then
        shake_timer:kill()
        shake_timer = nil
    end
    shake_timer = mp.add_periodic_timer(0.035, function()
        if step_idx <= #shake_offsets then
            shake_offset_x = shake_offsets[step_idx]
            step_idx = step_idx + 1
            render_overlay()
        else
            shake_offset_x = 0
            if shake_timer then
                shake_timer:kill()
                shake_timer = nil
            end
            render_overlay()
        end
    end)
end

-- Password submission & PAM verification
local function submit_password()
    if not is_macos_mode or not card_visible then return end
    if #password_buffer == 0 or is_verifying then return end

    is_verifying = true
    error_message = ""
    render_overlay()

    mp.command_native_async({
        name = "subprocess",
        playback_only = false,
        capture_stdout = true,
        capture_stderr = true,
        stdin_data = password_buffer,
        args = { options.python_bin, options.auth_script, options.user }
    }, function(success, res, err)
        is_verifying = false
        if success and res and res.status == 0 then
            -- PAM authentication success!
            if options.unlock_file ~= "" then
                local f = io.open(options.unlock_file, "w")
                if f then
                    f:write("ok\n")
                    f:close()
                end
            end
            mp.command("quit 0")
        else
            -- Authentication failed
            if res and res.stderr and res.stderr ~= "" then
                print("[aerial-auth stderr] " .. tostring(res.stderr))
            end
            failed_count = failed_count + 1
            password_buffer = ""
            if failed_count >= 5 then
                if options.fallback_file ~= "" then
                    local ff = io.open(options.fallback_file, "w")
                    if ff then ff:write("fallback\n"); ff:close() end
                end
                mp.command_native_async({
                    name = "subprocess",
                    playback_only = false,
                    args = {"loginctl", "lock-session"}
                })
                mp.command("quit")
                return
            end
            error_message = "Hatalı parola"
            run_shake()
            reset_timeout(15)
            render_overlay()
        end
    end)
end

-- Periodic multi-monitor focus & timeout checker
local function on_tick()
    local now = mp.get_time()

    -- 1. Multi-monitor sync: if another screen became active, hide our card
    if is_macos_mode and card_visible and options.active_mon_file ~= "" and options.screen_name ~= "" then
        local f = io.open(options.active_mon_file, "r")
        if f then
            local active_mon = f:read("*l")
            f:close()
            if active_mon and active_mon ~= "" and active_mon ~= options.screen_name then
                hide_lock_card()
                return
            end
        end
    end

    -- 2. Auto-dismiss timeout (20s inactivity -> smoothly retreat back to full video)
    if is_macos_mode and card_visible and not is_verifying then
        if (now - last_activity_time) >= timeout_seconds then
            hide_lock_card()
            return
        end
    end

    render_overlay()
end

mp.add_periodic_timer(0.25, on_tick)

-- Focus Loss Watchdog (Alt+Tab defense)
local focus_loss_timer = nil
local function on_focus_change(name, val)
    if (mp.get_time() - start_time) < grace_period then return end
    if not is_macos_mode then return end

    if val == true then
        -- This monitor's window is focused
        if focus_loss_timer then
            focus_loss_timer:kill()
            focus_loss_timer = nil
        end
        mark_active_monitor()
        if options.focus_file ~= "" then
            local f = io.open(options.focus_file, "w")
            if f then
                f:write(tostring(mp.get_time()) .. "\n")
                f:close()
            end
        end
    elseif val == false then
        -- Focus lost!
        if focus_loss_timer then
            focus_loss_timer:kill()
        end
        -- 350ms delay allows focus transition between monitors in multi-monitor setups
        focus_loss_timer = mp.add_timeout(0.35, function()
            focus_loss_timer = nil
            local another_has_focus = false
            if options.focus_file ~= "" then
                local f = io.open(options.focus_file, "r")
                if f then
                    local ts_str = f:read("*l")
                    f:close()
                    local ts = tonumber(ts_str)
                    if ts and (mp.get_time() - ts) < 0.5 then
                        another_has_focus = true
                    end
                end
            end

            if not another_has_focus then
                -- Genuine focus loss to external application (e.g. Alt+Tab attempt)!
                -- Immediately trigger GNOME lock screen to prevent unauthorized access
                print("[aerial-watchdog] Odak kaybedildi (Alt+Tab vb.), GNOME kilidi devreye giriyor...")
                if options.fallback_file ~= "" then
                    local ff = io.open(options.fallback_file, "w")
                    if ff then ff:write("focus_lost\n"); ff:close() end
                end
                mp.command_native_async({
                    name = "subprocess",
                    playback_only = false,
                    args = {"loginctl", "lock-session"}
                })
                mp.command("quit")
            end
        end)
    end
end

mp.observe_property("focused", "bool", on_focus_change)

-- Renders OSD (location, clock, and lock card)
render_overlay = function()
    local now = mp.get_time()
    local lines = {}

    -- 1. Location badge (Bottom Left)
    if options.show_location and cur_title ~= "" and not card_visible then
        local remaining = loc_show_until - now
        local alpha = "00"
        if remaining < 2.0 and remaining > 0 then
            local fade = math.floor((1.0 - remaining / 2.0) * 255)
            alpha = string.format("%02X", math.min(255, math.max(0, fade)))
        elseif remaining <= 0 then
            alpha = "FF"
        end

        if alpha ~= "FF" then
            local clean_title = cur_title:gsub("([{}\\])", "")
            local clean_sub = cur_sub:gsub("([{}\\])", "")
            local loc_ass = string.format(
                "{\\an1\\pos(80,1020)\\fs34\\b1\\c&H%sFFFFFF&\\3c&H%s000000&\\bord2\\shad1}%s",
                alpha, alpha, clean_title
            )
            if clean_sub ~= "" then
                loc_ass = loc_ass .. string.format(
                    "\\N{\\fs20\\b0\\c&H%sCCCCCC&\\3c&H%s000000&\\bord1.5\\shad1}%s",
                    alpha, alpha, clean_sub
                )
            end
            table.insert(lines, loc_ass)
        end
    end

    -- 2. Minimal Clock (Bottom Right)
    if options.show_clock then
        local time_fmt = options.clock_24h and "%H:%M" or "%I:%M %p"
        local time_str = os.date(time_fmt)
        local date_str = os.date("%A, %B %d")
        table.insert(lines, string.format(
            "{\\an3\\pos(1840,1020)\\fs34\\b1\\c&HFFFFFF&\\3c&H000000&\\bord2\\shad1}%s\\N{\\fs18\\b0\\c&HCCCCCC&\\3c&H000000&\\bord1.5\\shad1}%s",
            time_str, date_str
        ))
    end

    -- 3. macOS Style Lock Overlay (Ultra-transparent, borderless, floating directly on video)
    if is_macos_mode and card_visible then
        local cx = 960 + shake_offset_x
        local cy = 540

        -- A. Circular Avatar Badge: Diameter 76 (R=38) at (cx - 38, cy - 84)
        -- macOS style dark translucent glass disc (rgba(20,20,24, 0.55))
        table.insert(lines, string.format(
            "{\\an7\\pos(%d,%d)\\1a&H70&\\3a&HB0&\\bord1.2\\3c&HFFFFFF&\\1c&H181414&\\p1}m 0 38 b 0 17 17 0 38 0 b 59 0 76 17 76 38 b 76 59 59 76 38 76 b 17 76 0 59 0 38{\\p0}",
            cx - 38, cy - 84
        ))
        table.insert(lines, string.format(
            "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs28\\b1\\c&HFFFFFF&\\bord0\\shad1}%s",
            cx, cy - 46, options.initials
        ))

        -- B. User Full Name (clean, with soft drop shadow for readability over bright or dark video)
        local clean_name = options.full_name:gsub("([{}\\])", "")
        table.insert(lines, string.format(
            "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs19\\b1\\c&HFFFFFF&\\bord0\\shad2}%s",
            cx, cy + 4, clean_name
        ))

        -- C. Password Pill: W=224, H=36, R=18 at (cx - 112, cy + 24)
        -- macOS frosted glass (rgba(255, 255, 255, 0.28) -> 1a=&HB0&, 1c=&HFFFFFF&)
        -- Soft border (rgba(255, 255, 255, 0.35) -> 3a=&HA0&)
        table.insert(lines, string.format(
            "{\\an7\\pos(%d,%d)\\1a&HB0&\\3a&HA0&\\bord1.0\\3c&HFFFFFF&\\1c&HFFFFFF&\\p1}m 18 0 l 206 0 b 216 0 224 8 224 18 b 224 28 216 36 206 36 l 18 36 b 8 36 0 28 0 18 b 0 8 8 0 18 0{\\p0}",
            cx - 112, cy + 24
        ))

        -- D. Input text / bullets inside pill (left-aligned, matching clock Gtk.PasswordEntry)
        local pwd_len = utf8_len(password_buffer)
        if pwd_len == 0 then
            -- Muted placeholder text "Parola" without blinking pipe cursor
            table.insert(lines, string.format(
                "{\\an4\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs14\\b0\\c&HE8E8E8&\\bord0\\shad1}Parola",
                cx - 96, cy + 42
            ))
        else
            -- Bullet dots
            local dots = {}
            for _ = 1, pwd_len do
                table.insert(dots, "●")
            end
            local bullet_str = table.concat(dots, "   ")
            table.insert(lines, string.format(
                "{\\an4\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs15\\b1\\c&HFFFFFF&\\bord0}%s",
                cx - 96, cy + 42, bullet_str
            ))
        end

        -- E. Arrow submit button circle inside pill: R=12 at (cx + 82, cy + 30)
        table.insert(lines, string.format(
            "{\\an7\\pos(%d,%d)\\1a&H90&\\3a&H80&\\bord1.0\\3c&HFFFFFF&\\1c&HFFFFFF&\\p1}m 0 12 b 0 5.4 5.4 0 12 0 b 18.6 0 24 5.4 24 12 b 24 18.6 18.6 24 12 24 b 5.4 24 0 18.6 0 12{\\p0}",
            cx + 82, cy + 30
        ))
        table.insert(lines, string.format(
            "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs12\\b1\\c&H1A1A1A&\\bord0}➔",
            cx + 94, cy + 42
        ))

        -- F. Status / Error Message
        if is_verifying then
            table.insert(lines, string.format(
                "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs13\\b0\\c&HCCCCCC&\\bord0\\shad1}Doğrulanıyor...",
                cx, cy + 76
            ))
        elseif error_message ~= "" then
            table.insert(lines, string.format(
                "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs13\\b1\\c&H3A45FF&\\bord0\\shad1}%s",
                cx, cy + 76, error_message
            ))
        else
            table.insert(lines, string.format(
                "{\\an5\\pos(%d,%d)\\fnInter,Ubuntu,sans-serif\\fs11\\b0\\c&HD0D0D0&\\bord0\\shad1}İptal etmek için Esc",
                cx, cy + 76
            ))
        end
    end

    ov.data = table.concat(lines, "\n")
    ov:update()
end

-- Traditional exit handler (for GNOME mode or fallback)
local quitting = false
local function trigger_quit()
    if options.is_preview or quitting then return end
    if (mp.get_time() - start_time) < grace_period then return end
    quitting = true

    if options.lock_on_exit then
        mp.command_native_async({
            name = "subprocess",
            playback_only = false,
            args = {"loginctl", "lock-session"}
        })
    end

    mp.command("quit")
end

-- Mouse motion handler
local function check_mouse_move(name, val)
    if not val or not val.x or not val.y then return end
    local now = mp.get_time()
    last_mouse_pos = { x = val.x, y = val.y }

    if (now - start_time) < grace_period then
        anchor_mouse = nil
        return
    end

    if is_macos_mode then
        if not card_visible then
            if not anchor_mouse then
                anchor_mouse = { x = val.x, y = val.y }
                return
            end
            local dx = val.x - anchor_mouse.x
            local dy = val.y - anchor_mouse.y
            if math.sqrt(dx * dx + dy * dy) > motion_threshold then
                show_lock_card()
            end
        else
            reset_timeout()
        end
    else
        -- GNOME mode
        if not anchor_mouse then
            anchor_mouse = { x = val.x, y = val.y }
            return
        end
        local dx = val.x - anchor_mouse.x
        local dy = val.y - anchor_mouse.y
        if math.sqrt(dx * dx + dy * dy) > motion_threshold then
            trigger_quit()
        end
    end
end

mp.observe_property("mouse-pos", "native", check_mouse_move)

-- Mouse click handler
local function handle_mouse_click()
    local now = mp.get_time()
    if (now - start_time) < grace_period then return end

    if is_macos_mode then
        if not card_visible then
            show_lock_card()
        else
            reset_timeout()
            -- Check if click is on arrow button
            local mx = last_mouse_pos.x or 0
            local my = last_mouse_pos.y or 0
            local cx = 960 + shake_offset_x
            local cy = 540
            if mx >= (cx + 70) and mx <= (cx + 115) and my >= (cy + 20) and my <= (cy + 60) then
                submit_password()
            end
        end
    else
        trigger_quit()
    end
end

-- Key & Input Bindings
if options.is_preview then
    -- Preview Mode: Esc / Q exits, F toggles fullscreen
    mp.add_forced_key_binding("ESC", "preview_esc", function() mp.command("quit") end)
    mp.add_forced_key_binding("q", "preview_q", function() mp.command("quit") end)
    mp.add_forced_key_binding("f", "preview_f", function()
        local fs = mp.get_property_bool("fullscreen")
        mp.set_property_bool("fullscreen", not fs)
    end)
elseif is_macos_mode then
    -- macOS Lock Overlay Mode
    mp.add_forced_key_binding("MBTN_LEFT", "lock_click", handle_mouse_click)
    mp.add_forced_key_binding("MBTN_RIGHT", "lock_rclick", handle_mouse_click)

    mp.add_forced_key_binding("ESC", "lock_esc", function()
        if card_visible then
            hide_lock_card()
        end
    end)

    mp.add_forced_key_binding("ENTER", "lock_enter", function()
        if card_visible then
            submit_password()
        else
            show_lock_card()
        end
    end)
    mp.add_forced_key_binding("KP_ENTER", "lock_kp_enter", function()
        if card_visible then
            submit_password()
        else
            show_lock_card()
        end
    end)

    mp.add_forced_key_binding("BS", "lock_bs", function()
        if card_visible then
            password_buffer = utf8_pop(password_buffer)
            error_message = ""
            reset_timeout()
            render_overlay()
        else
            show_lock_card()
        end
    end)

    -- Keypad (Numpad) support: NumLock ON & OFF
    local kp_keys = {
        ["KP0"] = "0", ["KP1"] = "1", ["KP2"] = "2", ["KP3"] = "3", ["KP4"] = "4",
        ["KP5"] = "5", ["KP6"] = "6", ["KP7"] = "7", ["KP8"] = "8", ["KP9"] = "9",
        ["KP_DEC"] = ".", ["KP_INS"] = "0", ["KP_END"] = "1", ["KP_DOWN"] = "2",
        ["KP_PGDWN"] = "3", ["KP_LEFT"] = "4", ["KP_BEGIN"] = "5", ["KP_RIGHT"] = "6",
        ["KP_HOME"] = "7", ["KP_UP"] = "8", ["KP_PGUP"] = "9", ["KP_DEL"] = "."
    }
    for kp, ch in pairs(kp_keys) do
        mp.add_forced_key_binding(kp, "lock_" .. kp, function()
            if (mp.get_time() - start_time) < grace_period then return end
            if not card_visible then
                show_lock_card()
            end
            password_buffer = password_buffer .. ch
            error_message = ""
            reset_timeout()
            render_overlay()
        end)
    end

    -- Any typed character (letters, numbers, symbols, UTF-8)
    mp.add_forced_key_binding("ANY_UNICODE", "lock_unicode", function(e)
        if (mp.get_time() - start_time) < grace_period then return end
        if e.event == "press" or e.event == "repeat" or e.event == "down" then
            local text = e.key_text
            if text and #text > 0 then
                -- Ignore control characters / newlines
                local b = text:byte(1)
                if b >= 32 and b ~= 127 then
                    if not card_visible then
                        show_lock_card()
                    end
                    password_buffer = password_buffer .. text
                    error_message = ""
                    reset_timeout()
                    render_overlay()
                end
            end
        end
    end, {complex = true})

else
    -- GNOME mode: any key / mouse exits and locks session
    local exit_keys = {
        "MBTN_LEFT", "MBTN_RIGHT", "MBTN_MID", "MBTN_BACK", "MBTN_FORWARD",
        "WHEEL_UP", "WHEEL_DOWN", "WHEEL_LEFT", "WHEEL_RIGHT",
        "ANY_UNICODE", "SPACE", "ENTER", "ESC", "BS", "TAB",
        "UP", "DOWN", "LEFT", "RIGHT", "HOME", "END", "PGUP", "PGDWN", "DEL", "INS"
    }
    for _, k in ipairs(exit_keys) do
        mp.add_forced_key_binding(k, "quit_" .. k, trigger_quit)
    end
end
