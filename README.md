# laptop-scripts

Scripts that run an unattended machine's power schedule, boot logging, and
photo/video slideshow. This repo is a mirror of what's actually deployed on the
device — each subfolder notes where its files live on disk and how they're
installed, so the setup can be reproduced after a reinstall.

![alt text](https://github.com/LuisNavarro93/photo-frame-mediaserver/blob/mdia/portrait_landing.jpg)

## Purpose

This machine is set up to run unattended as two things at once:

- A **portrait-orientation photo slideshow display** that turns itself on
  and off automatically on a daily schedule, instead of staying powered on
  all the time.
- A **home media server**, using Jellyfin to stream media to other devices
  on the home network.

The scripts below implement the scheduling and logging around the first
role; Jellyfin (documented near the bottom) handles the second.

## System characteristics

Specs of the machine this is deployed on, for reference:

| | |
|---|---|
| OS | Ubuntu 26.04 LTS (Resolute Raccoon), kernel 7.0.0-28-generic |
| CPU | Intel Core i5-5300U @ 2.30GHz (2 cores / 4 threads) |
| GPU | Intel HD Graphics 5500 (Broadwell-U) |
| RAM | 7.5 GiB |
| Storage | 110 GB disk, ~31 GB free |

## Dependencies

Packages this setup relies on. All installed via `apt`; versions shown are
what's currently running on the machine.

| Package | Used for | Version |
|---|---|---|
| `util-linux` (`rtcwake`) | power-schedule — shutdown + RTC wake alarm | 2.41.3-3ubuntu2 |
| `mpv` | slideshow — fullscreen image playback | 0.41.0-2ubuntu4 |
| `openssh-server` | remote access | 10.2p1-2ubuntu3.5 |
| `vsftpd` | FTP access | 3.0.5-0.4 |
| `jellyfin` | media server | 10.11.11+ubu2604 |
| `git` | version control for this repo | 2.53.0-1ubuntu1 |
| `neovim` | editing scripts/config on the machine directly | 0.11.6-1 |
| `vim` | same, fallback/alternative editor | 9.1.2141-1ubuntu4.7 |
| `curl` | testing FTP/HTTP endpoints from the shell | 8.18.0-1ubuntu2.3 |

Install everything at once:
```bash
sudo apt install util-linux mpv openssh-server vsftpd jellyfin git neovim vim curl
```

`util-linux` ships as part of the base Ubuntu install, so `rtcwake` is
normally already present without needing to install it explicitly.

## power-schedule

Shuts the machine down every night and sets an RTC wake alarm for the next
day (5pm on weeknights so it wakes for the evening, 9am heading into the
weekend).

- `night-shutdown.sh` → deployed to `/usr/local/bin/night-shutdown.sh`
  (root:root, `755`)
- `root-crontab.txt` → line installed in root's crontab (`sudo crontab -e -u root`):
  ```
  0 23 * * * /usr/local/bin/night-shutdown.sh
  ```

## boot-logging

Logs a line to `~/Desktop/logs/schedule.log` every time the machine shuts
down (with the scheduled wake time) and every time it boots back up.

- `log-boot.sh` → deployed to `/usr/local/bin/log-boot.sh` (root:root, `755`)
- `boot-log.service` → deployed to `/etc/systemd/system/boot-log.service`,
  enabled with:
  ```
  sudo systemctl daemon-reload
  sudo systemctl enable boot-log.service
  ```

The shutdown-side logging is the `echo ... >> "$LOGFILE"` line inside
`power-schedule/night-shutdown.sh` itself — both scripts write to the same
log file.

Log file lives at `~/Desktop/logs/schedule.log` (not tracked in this repo —
it's runtime data, not a script).

## slideshow

Full-screen `mpv` photo slideshow of `~/Pictures/`, launched at login via
LXQt autostart, with screen blanking/DPMS disabled so it doesn't sleep mid-show.
Each loop, the file list is re-shuffled into a playlist file
(`/tmp/slideshow_playlist.txt`) and handed to `mpv` via `--playlist`, rather
than relying on mpv's own `--shuffle` (which only shuffles once per launch,
not per loop). `DISPLAY` and `XAUTHORITY` are exported explicitly since the
script runs from an autostart context rather than an interactive shell.

`mpv`'s output is piped through a filter that logs to
`~/Desktop/logs/schedule.log` alongside the power-schedule/boot-logging
entries: each `Playing: ...` line is logged as `SLIDESHOW`, and any line
matching error/fail/warning/cannot/unsupported/invalid (case-insensitive) is
logged as `SLIDESHOW-ERROR`. This catches per-file playback problems -- e.g.
some HEIC files decode to an unexpected embedded thumbnail track, or a
corrupt/unrecognized file fails to load outright -- without needing a
terminal open to see them.

LEFT/RIGHT arrow keys are bound to jump to the previous/next picture
(`slideshow-input.conf`, passed via `--input-conf`), since by default mpv
binds those keys to seeking within the current file rather than playlist
navigation.

A small `mpv` Lua script (`clock.lua`) draws the current date and time in
the top-right corner via an OSD overlay, refreshed every second, so the
frame doubles as a clock. It lives in mpv's scripts dir (auto-loaded) and is
also passed explicitly with `--script` so the dependency is visible in
`slideshow.sh`. Size/position/format are constants at the top of the file.

- `slideshow.sh` → deployed to `~/.config/autostart/slideshow.sh` (`755`)
- `slideshow-input.conf` → deployed to `~/.config/autostart/slideshow-input.conf` (`644`)
- `clock.lua` → deployed to `~/.config/mpv/scripts/clock.lua` (`644`)
- `slideshow.desktop` → deployed to `~/.config/autostart/slideshow.desktop`

## Reinstalling from this repo

```bash
# power schedule
sudo cp power-schedule/night-shutdown.sh /usr/local/bin/
sudo chown root:root /usr/local/bin/night-shutdown.sh
sudo chmod 755 /usr/local/bin/night-shutdown.sh
# then add the line from power-schedule/root-crontab.txt via: sudo crontab -e -u root

# boot logging
sudo cp boot-logging/log-boot.sh /usr/local/bin/
sudo chown root:root /usr/local/bin/log-boot.sh
sudo chmod 755 /usr/local/bin/log-boot.sh
sudo cp boot-logging/boot-log.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable boot-log.service

# slideshow
mkdir -p ~/.config/autostart
cp slideshow/slideshow.sh ~/.config/autostart/
chmod 755 ~/.config/autostart/slideshow.sh
cp slideshow/slideshow-input.conf ~/.config/autostart/
cp slideshow/slideshow.desktop ~/.config/autostart/
mkdir -p ~/.config/mpv/scripts
cp slideshow/clock.lua ~/.config/mpv/scripts/
```

## Jellyfin (not a script in this repo — reference only)

The machine also runs [Jellyfin](https://jellyfin.org/) as a media server,
so content is browsable/streamable over the network instead of only through
the local slideshow/player. It's not part of this repo because there's no
custom script or config behind it — it's a stock package install:

- Installed via `apt`: `jellyfin`, `jellyfin-server`, `jellyfin-web`,
  `jellyfin-ffmpeg7`.
- Runs as the `jellyfin.service` systemd unit (shipped by the package,
  `/usr/lib/systemd/system/jellyfin.service`), enabled so it starts on boot.
- There's a drop-in at `/etc/systemd/system/jellyfin.service.d/jellyfin.service.conf`,
  but every option in it is commented out — it's the unmodified template, not
  a local customization.

To reproduce on a fresh install:
```bash
sudo apt install jellyfin
sudo systemctl enable --now jellyfin
```

## wifi-adblock

A second WiFi network (`PortraitAdBlock`) broadcast by this laptop, alongside
(not instead of) the normal home network — join it from a phone/laptop to get
DNS-level ad blocking, while the regular home WiFi stays completely untouched
and unaffected by this laptop's power schedule.

Architecture: a virtual interface (`ap0`) is added on top of the same WiFi
radio used for the laptop's own connection, with `hostapd` broadcasting it as
an access point. `dnsmasq` handles DHCP + DNS for devices that join — DNS
queries for known ad/tracker domains (via a maintained hosts-format
blocklist) resolve to nothing, so the ad slot just fails to load. `iptables`
NAT routes traffic from the AP's clients out through the laptop's own WiFi
connection to actually reach the internet.

**Important hardware/regulatory constraint** that shaped this design: this
machine's WiFi card can only transmit (broadcast/beacon) on the 2.4GHz band —
5GHz is receive/client-only on this hardware (flagged `NO-IR`). On top of
that, the card only supports running as an access point *and* a client at the
same time if both share the exact same channel. That means the laptop's own
WiFi connection has to be on the router's **2.4GHz** band specifically (not
5GHz) — done by pinning the connection's BSSID to the router's 2.4GHz radio
in NetworkManager (`nmcli connection modify <profile> 802-11-wireless.bssid
<2.4ghz-bssid>`, found via `nmcli device wifi list`). That BSSID pin lives in
the NetworkManager connection profile, not in this repo — it's specific to
this router and isn't something a generic reinstall script should hardcode.

- `hostapd.conf` → deployed to `/etc/hostapd/hostapd.conf`. **The
  `wpa_passphrase` in this repo is a placeholder** (`CHANGE_ME_MIN_8_CHARS`)
  — the real passphrase deployed on the machine is not tracked here on
  purpose. Set your own before deploying.
- `adblock-ap.conf` → deployed to `/etc/dnsmasq.d/adblock-ap.conf`.
- `ap0-setup.sh` → deployed to `/usr/local/bin/ap0-setup.sh` (`755`);
  recreates the `ap0` virtual interface and its static IP
  (`192.168.50.1/24`) — virtual interfaces don't survive a reboot, so this
  has to re-run on every boot.
- `ap0-setup.service` → deployed to `/etc/systemd/system/ap0-setup.service`,
  enabled. Runs before `hostapd`/`dnsmasq` so `ap0` exists first.
- `hostapd-override.conf` / `dnsmasq-override.conf` → deployed to
  `/etc/systemd/system/hostapd.service.d/override.conf` and
  `/etc/systemd/system/dnsmasq.service.d/override.conf` — make those two
  packaged services wait on `ap0-setup.service`.
- `ap-nat.sh` → deployed to `/usr/local/bin/ap-nat.sh` (`755`); sets up NAT
  (MASQUERADE + FORWARD rules) so `ap0` clients can reach the internet
  through the laptop's own WiFi connection. Written idempotently (`-C` check
  before `-A`) so it's safe to re-run.
- `ap-nat.service` → deployed to `/etc/systemd/system/ap-nat.service`,
  enabled, runs after `hostapd`.

Not tracked in this repo (runtime data, not config): `/etc/dnsmasq_adblock_hosts`
(the downloaded blocklist, ~97k entries from
[StevenBlack/hosts](https://github.com/StevenBlack/hosts)) and IP forwarding
(`net.ipv4.ip_forward=1`, dropped in `/etc/sysctl.d/99-ap-forward.conf`).

To reproduce on a fresh install:
```bash
sudo apt install hostapd dnsmasq

sudo iw dev wlp3s0 interface add ap0 type __ap
echo '[keyfile]
unmanaged-devices=interface-name:ap0' | sudo tee /etc/NetworkManager/conf.d/unmanaged-ap0.conf
sudo nmcli device set ap0 managed no

sudo cp wifi-adblock/hostapd.conf /etc/hostapd/hostapd.conf
# then edit /etc/hostapd/hostapd.conf and set your own wpa_passphrase

sudo curl -sSL https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts -o /etc/dnsmasq_adblock_hosts
sudo cp wifi-adblock/adblock-ap.conf /etc/dnsmasq.d/adblock-ap.conf

sudo cp wifi-adblock/ap0-setup.sh /usr/local/bin/ap0-setup.sh
sudo chmod 755 /usr/local/bin/ap0-setup.sh
sudo cp wifi-adblock/ap0-setup.service /etc/systemd/system/ap0-setup.service

sudo mkdir -p /etc/systemd/system/hostapd.service.d /etc/systemd/system/dnsmasq.service.d
sudo cp wifi-adblock/hostapd-override.conf /etc/systemd/system/hostapd.service.d/override.conf
sudo cp wifi-adblock/dnsmasq-override.conf /etc/systemd/system/dnsmasq.service.d/override.conf

sudo cp wifi-adblock/ap-nat.sh /usr/local/bin/ap-nat.sh
sudo chmod 755 /usr/local/bin/ap-nat.sh
sudo cp wifi-adblock/ap-nat.service /etc/systemd/system/ap-nat.service

echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-ap-forward.conf
sudo sysctl --system

sudo systemctl daemon-reload
sudo systemctl enable --now ap0-setup.service
sudo systemctl enable --now hostapd
sudo systemctl enable --now dnsmasq
sudo systemctl enable --now ap-nat.service

# pin your own WiFi connection to your router's 2.4GHz band (required, see above):
# nmcli device wifi list
# nmcli connection modify <profile> 802-11-wireless.bssid <2.4ghz-bssid>
# nmcli connection up <profile>
```

## Remote access (SSH)

Used to administer the machine from another laptop (deploying/updating the
scripts in this repo, checking `schedule.log`, etc.), not a script in this
repo either — just how remote access is set up. (`<server-ip>` below is a
placeholder — substitute this machine's actual LAN IP, e.g. from
`hostname -I` run on the machine itself, or your router's client list.)

- `openssh-server` is installed and running, activated on demand via
  `ssh.socket` (enabled) rather than a permanently-running `ssh.service` —
  this means it comes back up automatically after the nightly
  shutdown/wake cycle without needing `ssh.service` itself enabled.
- Key-based login is set up so day-to-day access doesn't need a password:
  from the laptop you want to administer from,
  ```bash
  ssh-keygen -t ed25519          # skip if you already have a key
  ssh-copy-id portrait@<server-ip>   # prompts once for the account password
  ssh portrait@<server-ip>           # passwordless from now on
  ```

To reproduce on a fresh install:
```bash
sudo apt install openssh-server
sudo systemctl enable --now ssh.socket
```

## FTP access (vsftpd)

Lets any laptop on the home network browse/copy the machine's files
(`Documents`, `Pictures`, etc.) straight from a normal file manager, no
terminal needed.

- Installed via `apt install vsftpd`, running as the `vsftpd` systemd
  service (enabled, active).
- Key settings in `/etc/vsftpd.conf`:
  - `anonymous_enable=NO` / `local_enable=YES` — log in with the machine's
    normal account (`portrait`) and its password.
  - `write_enable=YES` — upload/edit, not just download.
  - `chroot_local_user=YES` (+ `allow_writeable_chroot=YES`) — each user is
    jailed to their own home directory and can't browse outside it.
  - `ssl_enable=NO` — plain, unencrypted FTP. Acceptable here since the
    server is only reachable on the trusted home LAN, never exposed to the
    internet.
- Connecting from a file manager — use "Connect to Server" / "Add network
  location" (GNOME Files, Dolphin, Thunar, Windows Explorer, macOS Finder
  via <kbd>Cmd+K</kbd>, FileZilla, etc.) and enter:
  ```
  ftp://<server-ip>
  ```
  logging in with the `portrait` account credentials. The home folder
  (`Documents`, `Pictures`, `Shows`, `Videos`, …) shows up directly.

To reproduce on a fresh install:
```bash
sudo apt install vsftpd
# set anonymous_enable=NO, local_enable=YES, write_enable=YES,
# chroot_local_user=YES, allow_writeable_chroot=YES in /etc/vsftpd.conf
sudo systemctl enable --now vsftpd
```
