#! usr/bin/python
#coding=utf-8
"""
Support for gaode traffic situation sensors.
For more details about this platform, please refer to the documentation at
"""
import logging
from homeassistant.util.dt import now as dt_now
from datetime import datetime
import time
from homeassistant.util import Throttle
from datetime import timedelta
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (DOMAIN, PLATFORM_SCHEMA)
import json
import urllib
import urllib.request
import urllib.parse
_Log=logging.getLogger(__name__)
CONF_ROAD_NAME = 'road_name'
CONF_CITY = 'city'
CONF_UPDATE_INTERVAL = 'interval'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_ROAD_NAME): cv.string,
    vol.Required(CONF_CITY): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=120)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""

    sensor_name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY,None)
    interval = config.get(CONF_UPDATE_INTERVAL)
    if api_key == None:
        _Log.error('Pls enter api_key!')
        return False
    road_name = config.get(CONF_ROAD_NAME,None)
    if road_name == None:
        _Log.error('Pls enter road_name!')
    city = config.get(CONF_CITY,None)
    if city == None:
        _Log.error('Pls enter city!')
    gaodetrafficData = TrafficData(
        api_key = api_key,
        city = city,
        road_name = road_name,
        interval = interval
    )
    gaodetrafficData.update()
    gaodetraffic = gaodetrafficSensor(hass,sensor_name,gaodetrafficData)
    add_devices([gaodetraffic])
    def update(call=None):
        gaodetrafficData._update()
        gaodetraffic.update()
    hass.services.register(DOMAIN, sensor_name+'_update', update)




class gaodetrafficSensor(Entity):
    """Representation of a Sensor."""


    def __init__(self,hass,sensor_name,gaodetrafficData):


        self._state = None
        self._name = sensor_name
        self.attributes = {}
        self._data = gaodetrafficData
        self.update()


    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attributes


    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._data.update()
        if self._data == None:
            _Log.error('No data!')


        expedite = self._data.data['trafficinfo']['evaluation']['expedite']
        congested = self._data.data['trafficinfo']['evaluation']['congested']
        blocked = self._data.data['trafficinfo']['evaluation']['blocked']
        unknown = self._data.data['trafficinfo']['evaluation']['unknown']
        description = self._data.data['trafficinfo']['evaluation']['description']
        status = self._data.data['trafficinfo']['evaluation']['status']
        if status == '0':
            traffic_status = '未知'
        elif status == '1':
            traffic_status = '畅通'
        elif status == '2':
            traffic_status = '缓行'
        elif status == '3':
            traffic_status = '拥堵'
        elif status == '4':
            traffic_status = '超堵'
        else:
            traffic_status = '无数据'
        self._state = traffic_status

        adddict = {
        '畅通所占百分比':expedite,
        '缓行所占百分比':congested,
        '拥堵所占百分比':blocked,
        '未知路段所占百分比':unknown,
        '道路描述':description,
        '路况': self._data.data['trafficinfo']['description'],
        '更新时间':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        self.attributes=adddict

class TrafficData(object):
    def __init__(self,api_key,city,road_name,interval):
        self.data = None
        self.api_key = api_key
        self.city = city
        self.road_name = road_name
        self.update =  Throttle(interval)(self._update)


    #@Throttle(SCAN_INTERVAL)
    def _update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """




        trafficdata = {'name': self.road_name,
                     'city': self.city,
                     'key' : self.api_key,
                             }

        trafficdata =  urllib.parse.urlencode(trafficdata)
        ret = urllib.request.urlopen("%s?%s" % ("http://restapi.amap.com/v3/traffic/status/road", trafficdata))
        if ret.status != 200:
            _Log.error('http get data Error StatusCode:%s' % ret.status)
            return
        res = ret.read().decode('utf-8')

        json_obj = json.loads(res)
        if not 'trafficinfo' in json_obj:
            _Log.error('Json Status Error1!')
            return
        if not 'description' in json_obj['trafficinfo']:
            _Log.error('No traffic data in json!')
            return
        self.data = json_obj
