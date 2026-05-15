# ChameleonUltraHACS
Enable the Chameleon Ultra to connect in BLE through a Bluetooth proxy.

# pour ESP Home
```esphome
esphome:
  name: atoms3-lite-multiproxy
  friendly_name: "Proxy Multi-Fonctions Salon"
  name_add_mac_suffix: false
  platformio_options:
    # Mode et vitesse de communication avec la puce Flash
    board_build.flash_mode: dio
    board_build.f_flash: 80000000L

esp32:
  board: esp32-s3-devkitc-1
  variant: esp32s3
  # Paramètres matériels spécifiques au Atom S3 Lite
  flash_size: 8MB
  cpu_frequency: 240MHz
  framework:
    type: esp-idf
    version: recommended #5.5.1
    sdkconfig_options:
      # Isolation matérielle (Multiplexage spatial)
      CONFIG_ESP_WIFI_TASK_PINNED_TO_CORE_0: y
      CONFIG_BT_NIMBLE_MAX_BONDS: "5"
      CONFIG_BT_NIMBLE_MAX_CONNECTIONS: "5"
      CONFIG_BT_NIMBLE_PINNED_TO_CORE_1: y
      CONFIG_ESP_COEX_SW_COEXIST_ENABLE: y
      CONFIG_COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_BT_BLE_42_FEATURES_SUPPORTED: y
      CONFIG_BT_BLE_50_FEATURES_SUPPORTED: y
      CONFIG_ESP_TASK_WDT_TIMEOUT_S: "15"

logger:
  level: DEBUG
  hardware_uart: UART0
  # Correspond au monitor_speed de PlatformIO
  baud_rate: 115200

# Enable Home Assistant API
api:
  encryption:
    key: 
  reboot_timeout: 15min
  on_client_connected:
    - esp32_ble_tracker.start_scan:
        continuous: true

interval:
  - interval: 30s
    then:
      - esp32_ble_tracker.start_scan:
          continuous: true
ota:
  - platform: esphome
    password: 

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  # Maintient le Wi-Fi éveillé
  power_save_mode: none

  manual_ip:
    static_ip: 192.168.0.0
    gateway: 192.168.0.0
    subnet: 255.255.255.0
    dns1: 192.168.0.0
    dns2: 192.168.0.1
  # =====================================

  ap:
    ssid: "M5Stack-Atoms3-Lite"
    password: 

captive_portal:

# =======================================================
# GESTION DU TEMPS ET BOUTONS DE MAINTENANCE
# =======================================================
time:
  - platform: sntp
    id: sntp_time
    servers:
      - pool.ntp.org

button:
  - platform: safe_mode
    name: "Redémarrage de Sécurité (Safe Mode)"
  - platform: restart
    name: "Réinitialisation Logicielle"

# =======================================================
# GESTION MATÉRIELLE BLUETOOTH (NOUVEAU)
# =======================================================
esp32_ble:
  # Synchronisation absolue avec le timeout de Home Assistant
  connection_timeout: 20s
  disable_bt_logs: true
  max_connections: 5

# =======================================================
# 1. SCANNER BLE ET DÉCLENCHEUR NFC (CHAMELEON)
# =======================================================
esp32_ble_tracker:
  scan_parameters:
    # Calibrage strict pour laisser 90% du temps radio au Wi-Fi
    interval: 320ms
    # Augmenté à 200ms pour ne pas rater les émissions brèves au boot
    window: 200ms
    active: false
    continuous: true
    
  on_ble_advertise:
    - then:
        - if:
            # FILTRE SOFT : On ne transmet que si le nom de l'appareil contient "Chameleon"
            # Cela protège HA d'une attaque DDoS par tes autres appareils Bluetooth
            condition:
              lambda: 'return x.get_name().find("Chameleon") != std::string::npos;'
            then:
              - homeassistant.event:
                  # Nom d'événement générique pour tous les appareils de ce type
                  event: esphome.esphome_ble_device_woke_up 
                  data:
                    # Extraction DYNAMIQUE de l'adresse MAC
                    mac: !lambda 'return x.address_str();'

# =======================================================
# 2. PROXY BLUETOOTH DOMOTIQUE
# =======================================================
bluetooth_proxy:
  active: true
  # Mise en cache indispensable pour des reconnexions instantanées
  cache_services: True
  connection_slots: 3

# =======================================================
# 3. ÉMETTEUR INFRAROUGE MATÉRIEL (ATOM S3 LITE)
# =======================================================
remote_transmitter:
  id: ir_tx
  pin: GPIO4 # Broche de la LED infrarouge native du M5Stack AtomS3 Lite
  carrier_duty_percent: 50%
  non_blocking: True

# =======================================================
# 4. INTÉGRATION INFRAROUGE NATIVE VERS HOME ASSISTANT
# =======================================================
infrared:
  - platform: ir_rf_proxy
    name: "IR Proxy Emetteur"
    remote_transmitter_id: ir_tx
```
