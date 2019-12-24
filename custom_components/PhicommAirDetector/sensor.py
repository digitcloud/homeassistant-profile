"""
Support for Phicomm Air Detector M1 plant sensor.
Developer by lixinb
192.168.123.200 aircat.phicomm.com
"""
import logging
import datetime
import json
import re
import select
import voluptuous as vol
from socket import socket, AF_INET, SOCK_STREAM
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME)


_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=5)
DEFAULT_NAME = 'Phicomm M1'

ATTR_TEMPERATURE = 'temperature'
ATTR_HUMIDITY = 'humidity'
ATTR_PM25 = 'pm25'
ATTR_HCHO = 'hcho'
ATTR_BRIGHTNESS = 'brightness'
CONNECTION_LIST = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Phicomm M1 sensor."""
    _LOGGER.info("PhicommM1Sensor setup_platform")

    name = config.get(CONF_NAME)
    connection_list = CONNECTION_LIST
    sock = socket(AF_INET, SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.bind(("0.0.0.0", 9000))
        sock.listen(5)
    except OSError as e:
        _LOGGER.warning("PhicommM1Sensor server got %s", e)
        pass

    connection_list.append(sock)
    _LOGGER.warning("PhicommM1Sensor server started on port 9000")

    devs = []

    devs.append(PhicommM1Sensor(
        hass, connection_list, sock, name))

    add_devices(devs)


class PhicommM1Sensor(Entity):
    """Implementing the Phicomm M1 sensor."""

    def __init__(self, hass, connection_list, sock, name):
        """Initialize the sensor."""
        _LOGGER.info("PhicommM1Sensor __init__")
        self.iCount = 0
        self.iClientEmptyLogCount = 0
        self._hass = hass
        self._connection_list = connection_list
        self.sock = sock
        self._name = name
        self._state = None
        self.data = []
        self._state_attrs = {
            ATTR_PM25: None,
            ATTR_TEMPERATURE: None,
            ATTR_HUMIDITY: None,
            ATTR_HCHO: None,
            ATTR_BRIGHTNESS: 50.0,
        }
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state_attrs[ATTR_PM25]

    @property
    def state_attributes(self):
        """Return the state of the sensor."""
        return self._state_attrs

    def shutdown(self, event):
        """Signal shutdown of sock."""
        _LOGGER.debug("Sock close")
        self.sock.shutdown(2)
        self.sock.close()

    def broadcast_data(self, sock, message):
        for socket in self._connection_list:
            if socket != self.sock and socket != sock:
                try:
                    socket.sendall(message)
                except OSError:
                    socket.close()
                    self._connection_list.remove(socket)

    def update(self):
        """
        Update current conditions.
        """

        self.iCount += 1
        heart_msg = b'\xaaO\x01%F\x119\x8f\x0b\x00\x00\x00\x00\x00\x00\x00\x00\xb0\xf8\x93\x11dR\x007\x00\x00\x02{"type":5,"status":1}\xff#END#'
        if self.iCount >= 8:
            for sockA in self._connection_list:
                if sockA is self.sock:
                    continue
                else:
                    try:
                        sockA.sendall(heart_msg)
                        self.iCount = 0
                        _LOGGER.info(
                            'PhicommM1Sensor Force send a heartbeat to %s', sockA.getpeername())
                        break
                    except OSError as e:
                        _LOGGER.warning(
                            "PhicommM1Sensor Force send a heartbeat got %s. Closing socket", e)
                        try:
                            sockA.shutdown(2)
                            sockA.close()
                        except OSError:
                            pass
                        self._connection_list.remove(sockA)
                        continue
        read_sockets, write_sockets, error_sockets = select.select(
            self._connection_list, [], [], 0)
        if len(self._connection_list) is 1:
            self.iClientEmptyLogCount += 1
            if self.iClientEmptyLogCount is 13:
                _LOGGER.warning("PhicommM1Sensor Client list is empty")
                self.iClientEmptyLogCount = 0
                return None
        else:
            self.iClientEmptyLogCount = 0

        brightness_state = 50.0
        brightness = self._hass.states.get('input_number.phicomm_m1_led')
        if brightness is not None:
            brightness_state = brightness.state
        if self._state_attrs[ATTR_BRIGHTNESS] != brightness_state:
            send_msg = b'\xaaO\x01\xf2E\x119\x8f\x0b\x00\x00\x00\x00\x00\x00\x00\x00\xb0\xf8\x93\x11T/\x007\x00\x00\x02{"brightness":"%b","type":2}\xff#END#' % str(
                round(float(brightness_state))).encode('utf8')
        else:
            send_msg = None

        for sock in read_sockets:
            if sock is self.sock:
                _LOGGER.warning(
                    "PhicommM1Sensor going to accept new connection")
                try:
                    sockfd, addr = self.sock.accept()
                    sockfd.settimeout(1)
                    self._connection_list.append(sockfd)
                    _LOGGER.warning(
                        "PhicommM1Sensor Client (%s, %s) connected" % addr)
                    try:
                        sockfd.sendall(heart_msg)
                        _LOGGER.warning(
                            "PhicommM1Sensor Force send a heartbeat:%s", heart_msg)
                    except OSError as e:
                        _LOGGER.warning("PhicommM1Sensor Client error %s", e)
                        sock.shutdown(2)
                        sock.close()
                        self._connection_list.remove(sockfd)
                        continue
                except OSError:
                    _LOGGER.warning("PhicommM1Sensor Client accept failed")
                    continue
            else:
                data = None
                try:
                    _LOGGER.debug(
                        "PhicommM1Sensor Processing Client %s", sock.getpeername())
                    data = sock.recv(1024)
                except OSError as e:
                    _LOGGER.warning(
                        "PhicommM1Sensor Processing Client error %s", e)
                    continue
                if send_msg is not None:
                    try:
                        sock.sendall(send_msg)
                    except OSError as e:
                        _LOGGER.warning("PhicommM1Sensor Client error %s", e)
                        sock.shutdown(2)
                        sock.close()
                        self._connection_list.remove(sock)
                        continue
                if data:
                    jsonData = self.parseJsonData(data)
                    if jsonData is not None:
                        self._state_attrs = {
                            ATTR_PM25: jsonData["value"],
                            ATTR_TEMPERATURE: format(float(jsonData["temperature"]), '.1f'),
                            ATTR_HUMIDITY: format(float(jsonData["humidity"]), '.1f'),
                            ATTR_HCHO: format(float(jsonData["hcho"]) / 1000, '.2f'),
                            ATTR_BRIGHTNESS: brightness_state,
                        }
                else:
                    _LOGGER.warning("PhicommM1Sensor Client offline, closing")
                    sock.shutdown(2)
                    sock.close()
                    self._connection_list.remove(sock)
                    continue

    def parseJsonData(self, data):
        pattern = r"(\{ \".*?\" \})"
        jsonStr = re.findall(pattern, str(data), re.M)
        l = len(jsonStr)
        if l > 0:
            return json.loads(jsonStr[l - 1])
        else:
            return None
