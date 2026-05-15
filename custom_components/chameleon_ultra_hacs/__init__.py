"""Support pour Chameleon Ultra - Version Allégée."""
import asyncio
import logging
import re
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS

DOMAIN = "chameleon_ultra_hacs"
_LOGGER = logging.getLogger(__name__)

UART_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

def calc_checksum(buffer: bytes) -> int:
    return (256 - (sum(buffer) % 256)) % 256

def build_read_cmd(page: int) -> bytearray:
    payload = bytes([0xFC, 0x01, 0xF4, 0x00, 0x10, 0x30, page])
    header = bytes([0x07, 0xDA, 0x00, 0x00, 0x00, 0x07])
    return bytearray([0x11, 0xEF]) + header + bytes([calc_checksum(header), *payload, calc_checksum(payload)])

class ChameleonData:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.mac_addr: str = entry.data[CONF_ADDRESS]
        self.is_connecting: bool = False
        self.cooldown_until: float = 0.0

    async def async_process_tags(self, device: bluetooth.BluetoothServiceInfoBleak) -> bool:
        from bleak_retry_connector import establish_connection, BleakClientWithServiceCache
        _LOGGER.debug("🔌 Connexion au Chameleon...")
        await asyncio.sleep(0.1)
        
        state: dict[str, Any] = {"uid": None, "uuid": None, "buf": ""}
        success = False
        
        def rx_handler(sender, data: bytearray):
            if len(data) < 10: return
            cmd = data[2:4]
            if cmd == b'\x07\xd0':
                uid_len = data[9]
                if uid_len > 0:
                    state["uid"] = data[10:10+uid_len].hex().upper()
            elif cmd == b'\x07\xda':
                p_len = int.from_bytes(data[6:8], 'big')
                if p_len > 0:
                    state["buf"] += data[9 : 9 + p_len].decode('utf-8', 'ignore')
                    m = re.search(r'[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}', state["buf"], re.IGNORECASE)
                    if m: state["uuid"] = m.group(0).lower()

        try:
            client = await establish_connection(BleakClientWithServiceCache, device, device.name, max_attempts=2)
            try:
                await client.start_notify(UART_RX, rx_handler)
                # Mode Lecteur
                h_m = bytes([0x03, 0xE9, 0x00, 0x00, 0x00, 0x01])
                await client.write_gatt_char(UART_TX, bytearray([0x11, 0xEF]) + h_m + bytes([calc_checksum(h_m), 0x01, 0xFF]))
                await asyncio.sleep(0.4)
                
                # Scan (15s)
                c_s = bytearray([0x11, 0xEF, 0x07, 0xD0, 0x00, 0x00, 0x00, 0x00, 0x29, 0x00])
                for _ in range(15):
                    if state["uid"]: break
                    await client.write_gatt_char(UART_TX, c_s, response=False)
                    await asyncio.sleep(1.0)
                
                if state["uid"]:
                    for attempt in range(2):
                        if state["uuid"]: break
                        state["buf"] = ""
                        for p in [0x04, 0x08, 0x0C, 0x10, 0x14]:
                            await client.write_gatt_char(UART_TX, build_read_cmd(p), response=False)
                            await asyncio.sleep(0.3)
                    
                    if state["uuid"]:
                        _LOGGER.warning(f"🎯 BINGO : {state['uuid']}")
                        self.hass.bus.async_fire("tag_scanned", {"tag_id": state["uuid"], "device_id": "chameleon_ultra"})
                        success = True
                await client.stop_notify(UART_RX)
            finally:
                await client.disconnect()
        except Exception as e:
            _LOGGER.debug(f"ℹ️ Fin de session BLE : {e}")
        return success

type ChameleonConfigEntry = ConfigEntry[ChameleonData]

async def async_setup_entry(hass: HomeAssistant, entry: ChameleonConfigEntry) -> bool:
    data = entry.runtime_data = ChameleonData(hass, entry)

    async def _trigger_scan():
        if data.cooldown_until > time.time() or data.is_connecting:
            return
            
        data.is_connecting = True
        device = bluetooth.async_ble_device_from_address(hass, data.mac_addr, connectable=True)
        
        if not device:
            _LOGGER.error(f"❌ {data.mac_addr} non trouvé.")
            data.is_connecting = False
            return

        async def _run():
            try:
                await data.async_process_tags(device)
            finally:
                data.cooldown_until = time.time() + 5.0
                data.is_connecting = False
                _LOGGER.warning("🛡️ Bouclier actif (5s).")
        
        hass.async_create_task(_run())

    async def _on_esphome_event(event):
        if event.data.get("mac", "").upper() == data.mac_addr.upper():
            await _trigger_scan()

    entry.async_on_unload(hass.bus.async_listen("esphome.esphome_ble_device_woke_up", _on_esphome_event))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ChameleonConfigEntry) -> bool:
    return True
