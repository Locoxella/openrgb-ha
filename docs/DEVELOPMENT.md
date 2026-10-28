# OpenRGB Home Assistant Custom Component Guide

## Architecture Overview
This project maintains our customized OpenRGB integration for Home Assistant. It bridges local hardware running the OpenRGB SDK server to Home Assistant without device duplication issues caused by Linux dynamic `/dev/hidraw*` allocations.

## Key Files & Patches
1. `custom_components/openrgb/coordinator.py`:
   - `stable_location(location)` replaces transient HID/USB numbers with persistent virtual indices.
   - `_get_device_key`: Always forces `stable_location` for Asus and Razer hardware even when the device goes to sleep and serial drops to `""` or `"none"`.
2. `custom_components/openrgb/__init__.py`:
   - Enforces the same stable key logic in migration steps.
   - Automatic cleanup of stale dynamic HID devices in device registry.
   - Unicode string decoder monkeypatch for controller stability.
3. `custom_components/openrgb/light.py`:
   - Normalizes empty serial strings to avoid corrupt device entries.

## Release & Sync Pipeline
- `.github/workflows/auto_sync_release.yml`:
  - Monitors `home-assistant/core` releases.
  - Automatically rebases or applies patches against new upstream Core releases.
  - Generates tags formatted as `<UPSTREAM_VERSION>-custom.<N>` and creates GitHub Releases for HACS.
