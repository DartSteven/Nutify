<p align="right">
<a href="https://www.buymeacoffee.com/DartSteven" target="_blank">
  <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&amp;&amp;slug=DartSteven&amp;button_colour=FFDD00&amp;font_colour=000000&amp;font_family=Cookie&amp;outline_colour=000000&amp;coffee_colour=ffffff" width="160"/>
</a>
</p>

<div align="center">
  <img src="pic/Nutify_Logo.png" alt="Nutify official logo" width="200"/>
</div>

<p align="center">
  <a href="https://github.com/DartSteven/Nutify/blob/main/changelog.md" target="_blank">
    <img alt="Changelog" src="https://img.shields.io/badge/changelog-0.2.0-green">
  </a>
  <a href="https://github.com/DartSteven/Nutify/wiki" target="_blank">
    <img alt="Wiki" src="https://img.shields.io/badge/wiki-updated-0ea5e9">
  </a>
  <a href="https://github.com/DartSteven/Nutify/discussions" target="_blank">
    <img alt="Discussions" src="https://img.shields.io/badge/community-discussions-orange">
  </a>
</p>

<h1 align="center">Nutify - UPS Monitoring System</h1>

Nutify is an open-source UPS monitoring and management platform built on top of <a href="https://networkupstools.org">Network UPS Tools (NUT)</a>. It provides real-time status, historical telemetry, alerts, scheduled reports, and interactive charts through a modern web interface. From single-UPS setups to mixed local/remote multi-UPS fleets, Nutify helps you configure, monitor, and operate your power infrastructure from one place.
Join our <a href="https://discord.gg/ry82VdKK">Discord</a> community for support, testing, and feature discussions. If Nutify helps you, please consider starring the project on GitHub.

<p align="center">
  <img src="pic/Readme/Main-Light.jpg" alt="Energy dashboard" width="640"/>
</p>

<p align="center">
  <img src="pic/Readme/Battery-Light.jpg" alt="Battery dashboard" width="220"/>
  <img src="pic/Readme/Power-Light.jpg" alt="Power dashboard" width="220"/>
  <img src="pic/Readme/Voltage-Light.jpg" alt="Voltage dashboard" width="245"/>
</p>

<p align="center">
  <img src="pic/Readme/Energy-Light.jpg" alt="Energy dashboard" width="220"/>
  <img src="pic/Readme/EnergyDetails-Light.jpg" alt="Energy Details dashboard" width="275"/>
</p>

## What's New In 0.2.0

- Multi-UPS monitoring promoted as a first-class workflow across setup, dashboard, APIs, and reporting.
- New profile-aware setup wizard (`single` and `multi`) with topology flow (`remote_only`, `local_only`, `mixed`).
- New dedicated Multi-UPS page with per-target status and active target switching.
- Settings split into two scopes:
  - `Options` / target scope (`/settings?view=target`)
  - `Settings/System` / global scope (`/settings?view=system`)
- New `Operations` section for formula and runtime variable mapping logic.
- Enhanced `Remapper` workflow for canonical variable mapping per target.
- Canonical multi-target telemetry flow on `ups_monitor_data` with target-aware storage strategies.

<p align="center">
  <img src="pic/Readme/Multi-UPS-Light.jpg" alt="Monitor Multi-UPS" width="600"/>
</p>


## Current Version

- Version: `0.2.0`

> [!WARNING]
> Version `0.2.0` is **not backward compatible** with previous releases.
>  
> The database must be **recreated from scratch**.
>  
> To avoid incompatible or dirty data, it is strongly recommended to start from a completely clean environment using a **new empty folder**.
> Do not reuse files or data from older versions.

For full details, see [changelog.md](changelog.md).

## Supported Architectures

Nutify is available for multiple hardware platforms:

| Architecture | Docker Image Tag | Devices |
|--------------|------------------|---------|
| 🖥️ **AMD64/x86_64** | dartsteven/nutify:latest-amd64 | Standard PCs, servers, most cloud VMs |
| 🍎 **Apple Silicon (ARM64)** | dartsteven/nutify:latest-mac-arm64  | Apple M1/M2/M3+ Macs running Docker |
| 🍓 **Raspberry Pi 4 – 32-bit OS required** | dartsteven/nutify:latest-raspberrypi4-armv7 | For Raspberry Pi 4 running a 32-bit OS |
| 🍓 **Raspberry Pi 4 / 5 – 64-bit OS required** | dartsteven/nutify:latest-raspberrypi5-arm64 | For Raspberry Pi 4 or 5 running a 64-bit OS |

## Quick Start (Docker)

```yaml
services:
  nut:
    # Container image
    image: dartsteven/nutify:latest-amd64        # Nutify image version
    container_name: Nutify                       # Static container name for easy reference

    # Privileges required for 
    # direct UPS and USB device access
    privileged: true                             # Broad hardware access for NUT and USB integration
    cap_add:
      - SYS_ADMIN                                # Extended system administration capabilities
      - SYS_RAWIO                                # Raw hardware I/O access
      - MKNOD                                    # Create special device files if needed

    # USB device mapping
    devices:
      - /dev/bus/usb:/dev/bus/usb:rwm            # Map host USB bus into the container
    device_cgroup_rules:
      - 'c 189:* rwm'                            # Allow all USB character devices

    # Persistent storage and host integration
    volumes:
      - ./Nutify/logs:/app/nutify/logs           # Application logs
      - ./Nutify/instance:/app/nutify/instance   # Persistent app data and runtime files
      - ./Nutify/ssl:/app/ssl                    # SSL certificates and private keys
      - ./Nutify/etc/nut:/etc/nut                # NUT configuration directory
      - /dev:/dev:rw                             # Full device tree access for hardware detection
      - /run/udev:/run/udev:ro                   # Udev event access for hotplug monitoring

    # Runtime environment
    environment:
      - SECRET_KEY=test1234567890                # Secret key used for sessions and encrypted values
      - UDEV=1                                   # Enable udev-aware USB detection mode
      - SSL_ENABLED=false                        # true or false, default is false
     
     # DNS resolvers
    dns:
      - 1.1.1.1                                  # Cloudflare DNS
      - 8.8.8.8                                  # Google DNS
    dns_opt:
      - timeout:2                                # DNS timeout per query
      - attempts:2                               # Retry count before failure

    # Exposed ports
    ports:
      - 3493:3493                                # NUT daemon communication port
      - 5050:5050                                # Nutify application port
      - 443:443                                  # HTTPS secure web access

    restart: always                              # Keep the service running across failures/reboots
    user: root                                   # Root required for full device and NUT access
```

Run:

```bash
docker compose up -d
```

Then open:

- `http://localhost:5050`

## Web-Based Configuration

The setup wizard allows you to configure:
- Monitoring profile (`Single Monitor` or `Multi Monitor`)
- Fleet topology based on the selected profile:
  - Single: `Standalone`, `Network Server`, or `Network Client`
  - Multi: `Remote NUT Only`, `Local Targets Only`, or `Mixed Local + Remote`
- Connection method: `Manual Configuration` or `Auto-detect with nut-scanner`
- Driver selection from the supported NUT driver catalog
- Local and remote connection parameters (`host`, `port`, `username`, `password`, `ups identifier`)
- Per-target metadata:
  - `Target Display Name (UI label)`
  - `Target Timezone`
  - `Target Currency`
  - `Polling Interval`
- Validation flow with test actions before save (`Test Target`, `Test & Save Primary Target`)
- Final configuration preview and controlled restart to apply generated NUT files


## Tested UPS Models

Nutify aims for broad compatibility with UPS devices supported by Network UPS Tools (NUT). 

**Is your UPS model working with Nutify but not listed here?** Please help us expand this list by sharing your experience in the

[UPS Compatibility List discussion](https://github.com/DartSteven/Nutify/discussions/16)

Knowing which models work helps the entire community.

While Nutify should work with most NUT-compatible devices, the models listed above have specific confirmation from users.

## Documentation [Nutify Wiki](https://github.com/DartSteven/Nutify/wiki)

For detailed documentation, including:
- Complete configuration options
- Advanced features
- Troubleshooting
- Screenshots and examples
- Technical details
- ... And More ...

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support the Project

Nutify is developed and maintained in my free time. If you find this project useful and would like to support its continued development, please consider making a donation.

Your support helps cover development costs and encourages further improvements and new features. Thank you for your generosity!

<p align="center">
  <a href="https://www.blockchain.com/btc/address/bc1qprc948hf49s88cyfhennj5yaafewr8vat9qrk9" target="_blank">
    <img alt="Donate Bitcoin" src="https://img.shields.io/badge/Donate%20Bitcoin-F7931A?style=flat&logo=bitcoin&logoColor=white" width="160">
  </a>
  &nbsp;&nbsp;
<a href="https://www.buymeacoffee.com/DartSteven" target="_blank">
  <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&amp;&amp;slug=DartSteven&amp;button_colour=FFDD00&amp;font_colour=000000&amp;font_family=Cookie&amp;outline_colour=000000&amp;coffee_colour=ffffff" width="160"/>
</a>
  </a>
</p>

## Stargazers over time
[![Stargazers over time](https://starchart.cc/DartSteven/Nutify.svg?variant=adaptive)](https://starchart.cc/DartSteven/Nutify)
