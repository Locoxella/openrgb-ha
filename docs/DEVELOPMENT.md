# OpenRGB Home Assistant Custom Component Guide

## Architecture Overview
This project maintains our customized OpenRGB integration for Home Assistant. It bridges local hardware running the OpenRGB SDK server to Home Assistant without device duplication issues caused by Linux dynamic `/dev/hidraw*` allocations.

## Key Files & Patches
1. `custom_components/openrgb/coordinator.py`:
   - `stable_location(location)` replaces transient HID/USB numbers with persistent virtual indices.
   - `_get_device_key`: Always forces `stable_location` for Asus and Razer hardware even when the device goes to sleep and serial drops to `""` or `"none"`.
2. `custom_components/openrgb/const.py`:
   - Universal early monkeypatch for `openrgb.utils.parse_string` (`errors="replace"`) to prevent fatal crashes on non-UTF-8 bytes (e.g. SteelSeries keyboard serials).
3. `custom_components/openrgb/config_flow.py`:
   - Declares `VERSION = 2` and `MINOR_VERSION = 1` ensuring compatibility with migrated config entries and preventing `ConfigEntryState.MIGRATION_ERROR`.
4. `custom_components/openrgb/__init__.py`:
   - Enforces the same stable key logic in migration steps.
   - Automatic cleanup of stale dynamic HID devices in device registry.
5. `custom_components/openrgb/light.py`:
   - Normalizes empty serial strings to avoid corrupt device entries.

## Release & Sync Pipeline
- `.github/workflows/auto_sync_release.yml`:
  - Monitors `home-assistant/core` releases every 6 hours (and on manual trigger / push).
  - Automatically fetches fresh upstream components from Home Assistant Core releases.
  - Safely preserves custom patched files (`coordinator.py`, `__init__.py`, `light.py`, `config_flow.py`, `const.py`).
  - Generates tags formatted as `<UPSTREAM_VERSION>-custom.<N>` and publishes GitHub Releases.

## Upstream Pull Request Roadmap & Strategy

### Target PR 1: Upstream Python SDK (`jath03/openrgb-python`)
- **Repository:** `jath03/openrgb-python`
- **Issue:** `openrgb.utils.parse_string` performs strict UTF-8 decoding (`.decode()`). Devices returning raw binary bytes in their serial or metadata (such as SteelSeries Apex Pro TKL keyboards with `\xff`) throw `UnicodeDecodeError`, which halts device enumeration across the entire SDK client.
- **Fix:** Update `parse_string` to decode with `errors="replace"`, making controller parsing resilient to arbitrary vendor firmware payloads:
  ```python
  def parse_string(data: Iterator[int]) -> str:
      length = parse_var('H', data)
      return parse_var(f'{length}s', data).decode('utf-8', errors='replace').rstrip('\x00')
  ```
- **PR Status:** To be submitted once local multi-device stability is confirmed.

### Target PR 2: Home Assistant Core (`home-assistant/core`)
- **Target Component:** `homeassistant/components/openrgb`
- **Target Branch:** `dev`
- **Key Changes for PR:**
  1. `coordinator.py`: Generalize `stable_location` invocation to include vendors whose wireless/battery-saving peripherals omit serial numbers during sleep cycles (e.g. `vendor_lower in ("asus", "razer")` or whenever a device key needs stable fallback).
  2. `light.py`: Sanitize `serial_number` in `DeviceInfo` (`None` instead of raw whitespace string or `"none"`).
- **Checklist before submitting PR:**
  - [ ] Validate stability over multi-day use (confirm zero duplicate mouse entities after wake/sleep cycles).
  - [ ] Verify clean automated sync of fork releases via GitHub Actions.
  - [ ] Branch out from `home-assistant/core:dev` (`fix/openrgb-peripheral-sleep-reconnect`).
  - [ ] Run Home Assistant Core pre-commit hooks (`ruff`, `mypy`).
