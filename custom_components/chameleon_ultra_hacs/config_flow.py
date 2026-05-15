"""Config flow pour Chameleon Ultra."""
import voluptuous as vol
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS

DOMAIN = "chameleon_ultra_hacs"

class ChameleonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gère le processus de configuration pour Chameleon."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Étape utilisateur pour choisir l'appareil découvert."""
        # Si l'utilisateur a sélectionné un appareil dans la liste
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            
            # On crée l'entrée avec l'adresse MAC sauvegardée
            return self.async_create_entry(
                title=f"Chameleon Ultra ({address})", 
                data={CONF_ADDRESS: address}
            )

        # Si c'est la première ouverture, on scanne les appareils BLE disponibles
        discovered_devices = {}
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            name = discovery_info.name or ""
            
            # On ne garde que les appareils dont le nom contient "chameleon"
            if "chameleon" in name.lower():
                discovered_devices[address] = f"{name} ({address})"

        # Aucun Chameleon trouvé à portée
        if not discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Affichage du menu déroulant à l'utilisateur
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(discovered_devices)}
            ),
        )
