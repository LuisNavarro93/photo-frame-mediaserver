# laptop-scripts

Scripts that run an unattended machine's power schedule, boot logging, and
photo/video slideshow. This repo is a mirror of what's actually deployed on the
device — each subfolder notes where its files live on disk and how they're
installed, so the setup can be reproduced after a reinstall.

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

- `slideshow.sh` → deployed to `~/.config/autostart/slideshow.sh` (`755`)
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
cp slideshow/slideshow.desktop ~/.config/autostart/
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
