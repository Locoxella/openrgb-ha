# OpenRGB Home Assistant Custom Fork

This repository provides an enhanced, HACS-compatible custom component for **OpenRGB** in Home Assistant, maintaining parity with official Home Assistant Core integration updates while fixing peripheral disconnect/reconnect and entity duplication bugs.

---

## 🛠 Customizations & Problem Solved

### 1. Razer & Asus Device Reconnection Bug (`stable_location`)
- **The Issue**: In the official Home Assistant Core OpenRGB component, dynamic paths (e.g. `HID: /dev/hidraw24`) are replaced with stable keys (`hid_0`) **only** when a valid hardware serial number is reported. Peripherals like the **Razer Deathadder V2 Pro (Wireless)** or wireless dongles frequently drop their serial metadata upon entering sleep mode or waking up, causing OpenRGB to report `serial: "none"`.
- **The Result**: On every wake/sleep cycle or reboot, Home Assistant generated a brand new device and entity (e.g., `light.razer_deathadder_v2_pro_wireless_2`, `_3`, etc.).
- **The Fix**:
  - `stable_location` in `coordinator.py` and `__init__.py` now explicitly protects devices from vendors like `Razer` and `Asus` even when the serial is blank or `"none"`.
  - Serial numbers in `light.py` (`DeviceInfo`) are normalized and sanitized.
  - An automatic registry cleaner cleans up any obsolete dynamic `HID: /dev/...` duplicate devices during setup.

### 2. UnicodeDecodeError Protection
- Robust monkeypatch for `openrgb.utils.parse_string` to guard against corrupt/non-UTF8 metadata sent by certain RGB controllers without crashing the integration.

---

## 🔄 Branch Architecture & Release Workflow

Following our **`xtend_tuya`** workflow conventions:

- **Upstream Source**: `home-assistant/core` (`homeassistant/components/openrgb/`).
- **Target Branch**: `feature/hardware-stability` (our active working branch).
- **Versioning Scheme**: `${HA_CORE_VERSION}-custom.${PATCH_NUM}` (e.g. `2026.10.4-custom.1`).
- **Automated Workflow (`.github/workflows/auto_sync_release.yml`)**:
  - Runs automatically on schedule (every 6 hours) or via `workflow_dispatch`.
  - Detects new Home Assistant Core stable tags.
  - Preserves local hardware stability patches.
  - Updates `manifest.json` with the lexicographically safe version tag.
  - Packages the component and publishes a GitHub Release with `openrgb.zip` for HACS.

---

## 📦 HACS Installation

1. In Home Assistant, open **HACS** > **Integrations** > **Custom repositories**.
2. Add `https://github.com/Locoxella/openrgb-ha` with category **Integration**.
3. Download the release (version will display as `2026.10.x-custom.y`).
4. Restart Home Assistant or reload the OpenRGB integration.
