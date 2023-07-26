#!/usr/bin/python3
#################################################
__author__ = "Michael Bompani & Teodor Chetrusca"
__copyright__ = "Mead Informatica SRL."
__license__ = "NDA"
__version__ = "0.1"
__maintainer__ = "Michael Bompani"
__email__ = "m.bompani@meadinformatica.it"
__status__ = "1.0"
#################################################

import os
import logging
import smtplib
import sys
import time
import configparser


import requests
import datetime
from datetime import date, timedelta
from dateutil import tz
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from dateutil import tz
from jinja2 import Template
from logging.handlers import RotatingFileHandler


class Utils:
    """
    Classe che serve per definire tutti i path e le configurazioni
    """

    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.path = os.path.dirname(sys.executable)
        elif __file__:
            self.path = os.path.dirname(os.path.abspath(__file__))
        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(self.path + "/" + sys.argv[1] + '/config.ini')

    def change_time(self, utc):
        """
        Funzione che serve a cambiare il tempo da UTC a locale
        :param utc:  tempo in utc
        :return:
        """

        utc = datetime.datetime.strptime(utc, '%Y-%m-%dT%H:%M:%S.%fZ')
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()
        # datetime objects are 'naive' by default
        utc = utc.replace(tzinfo=from_zone)
        # Convert time zone
        central = utc.astimezone(to_zone)
        return central.strftime('%Y-%m-%d %H:%M:%S')

    def get_RAPID7_url_base(self):
        return self.config['RAPID7']['URL_BASE']

    def get_RAPID7_url_path(self):
        return self.config['RAPID7']['URL_PATH']

    def get_RAPID7_url_path_single_inv(self):
        return self.config['RAPID7']['URL_PATH_SINGLE_INV']

    def get_RAPID7_tenant_url(self):
        return self.config['RAPID7']['TENANT_URL']

    def get_RAPID7_TOKEN(self):
        return self.config['RAPID7']['TOKEN']
    
    def get_RAPID7_time_in_seconds_w(self):
        return int(self.config['RAPID7']['TIME_IN_SECONDS_W'])     
       
    def get_EMAIL_path(self):
        return self.config['EMAIL']['PATH']

    def get_EMAIL_relay(self):
        return self.config['EMAIL']['RELAY']

    def get_EMAIL_subject(self):
        return self.config['EMAIL']['SUBJECT']

    def get_EMAIL_from(self):
        return self.config['EMAIL']['FROM']

    def get_EMAIL_to(self):
        return self.config['EMAIL']['TO']

    def get_EMAIL_senders(self):
        return self.config['EMAIL']['SENDERS']

    def get_LOG_file(self):
        return self.config['LOG']['LOGFILE']

    def get_LOG_Level(self):
        return self.config['LOG']['LOGLEVEL']

class Logger:
    """
    Classe per la gestione degli errori in tutto il programma.
    """
    logger = None

    def __init__(self):
        self.logger = logging.getLogger('Rapid7 - ' + sys.argv[1])
        self.fh = RotatingFileHandler(_utils.path + _utils.get_LOG_file(), maxBytes=4000000, backupCount=20)
        self.fh.setLevel(self.get_level())
        formatter = logging.Formatter('%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
                                      , '%d-%m-%Y:%H:%M:%S')
        self.fh.setFormatter(formatter)
        self.logger.addHandler(self.fh)
        self.logger.setLevel(self.get_level())

    def get_level(self):
        '''
        Funzione che serve per assegnare il livello di debug
        :return: in base al debug viene assegnato il livello.
        '''
        if 'INFO' in _utils.get_LOG_Level():
            return logging.INFO
        elif 'DEBUG' in _utils.get_LOG_Level():
            return logging.DEBUG
        elif 'CRITICAL' in _utils.get_LOG_Level():
            return logging.CRITICAL
        


class Investigation:
    def __init__(self, title, status, source, created_time, assignee, url, severity):
        self.title = title
        self.status = status
        self.source = source
        self.created_time = created_time
        self.assignee = assignee
        self.url = url
        self.severity = severity


class API:

    def __init__(self, url_base, url_path, url_path_single_inv, token, delta_sec) -> None:
        self.url_base = url_base
        self.url_path = url_path
        self.url_path_single_inv = url_path_single_inv
        self.token = token
        self.delta_sec = delta_sec

    def format_iso_time(self, ft_rule='%Y-%m-%dT%H:%M:%S.000Z', delta_sec=0):
        calc_time = datetime.datetime.utcnow() - datetime.timedelta(seconds=delta_sec)
        return calc_time.strftime(ft_rule)

    def call_api(self, time_in_seconds):
        nowTime = self.format_iso_time(delta_sec=54000) #Esclusi dalle 20:00 del giorno prima
        startTime = self.format_iso_time(delta_sec=time_in_seconds)

        query_params = {
            'end_time': nowTime,
            'start_time': startTime,
            'size': 100
        }
        headers = {'X-Api-Key': self.token}

        try:
            r = requests.get(str(self.url_base) + str(self.url_path),
                             params=query_params, headers=headers)
            return r
        except requests.exceptions.RequestException as e:
            return None

    def call_api_single_investigation(self, id):
        """
        Funzione che serve per avere le info delle singole investigation con le API V2
        :param id: id del investigation
        :return: il json di ritorno da rapid7
        """
        query_params = {
            'id': id
        }
        headers = {'X-Api-Key': self.token,
                   'Accept-version': 'investigations-preview'}
        try:

            r = requests.get(str(self.url_base) + str(self.url_path_single_inv) + "/" + str(id),
                             params=query_params, headers=headers)
            return r
        except requests.exceptions.RequestException as e:
            return None


def parse_json(response, tenant_url):
    data = response.json()
    if 'data' in data:
        for k in data['data']:
            time.sleep(1)
            _title = ""
            _status = ""
            _source = ""
            _created_time = ""
            _url = ""
            _severity = ""
            _assignee = ""
            _alerts = []

            if 'title' in k:
                _title = k['title']
            if 'status' in k:
                _status = k['status']
            if 'source' in k:
                _source = k['source']
            if 'created_time' in k:
                _created_time = _utils.change_time(k['created_time'])
            if 'assignee' in k:
                _assignee = k['assignee']['name']

            if 'id' in k:
                _url = tenant_url + k['id']
                _inv = inv.call_api_single_investigation(k['id']).json()
                if 'priority' in _inv:
                    _severity = _inv['priority']
  
            if _status == "OPEN":
                investigations_open.append(Investigation(_title, _status, _source, _created_time, _assignee, _url, _severity))
            elif _status == "INVESTIGATING":
                investigations_inv.append(Investigation(_title, _status, _source, _created_time, _assignee, _url, _severity))
            elif _status == "WAITING":
                investigations_waiting.append(Investigation(_title, _status, _source, _created_time, _assignee, _url, _severity))                


def send_report():
    message = MIMEMultipart("alternative")
    message["Subject"] = _utils.get_EMAIL_subject()
    message["From"] = _utils.get_EMAIL_from()
    message["To"] = _utils.get_EMAIL_to()


    file = open(_utils.path + _utils.get_EMAIL_path(), 'r', encoding="utf8")
    email_html = file.read()
    my_templ = Template(email_html)

    inv_o = []
    for inv in investigations_open:
        inv_o.append(inv.created_time)
        inv_o.append(inv.title)
        inv_o.append(inv.severity)        
        inv_o.append(inv.assignee)
        inv_o.append(inv.url)

    inv_i = []
    for inv in investigations_inv:
        inv_i.append(inv.created_time)
        inv_i.append(inv.title)
        inv_i.append(inv.severity)        
        inv_i.append(inv.assignee)
        inv_i.append(inv.url)

    inv_w = []
    for inv in investigations_waiting:
        inv_w.append(inv.created_time)
        inv_w.append(inv.title)
        inv_w.append(inv.severity)        
        inv_w.append(inv.assignee)
        inv_w.append(inv.url)


    email_html = my_templ.render(tot_open=len(investigations_open), tot_inv=len(investigations_inv), tot_wait=len(investigations_waiting), opens=inv_o, invs=inv_i, waits=inv_w)
    file.close()
    html = MIMEText(email_html, "html")
    message.attach(html)

    try:
        server = smtplib.SMTP(_utils.get_EMAIL_relay())
        senders = _utils.get_EMAIL_senders().strip()
        senders = senders.split(",")
        server.sendmail(_utils.get_EMAIL_from(), senders, message.as_string())
        server.quit()
    except smtplib.SMTPException as e:
        _log.logger.critical(str(e) + "\n")
    except ConnectionRefusedError as e:
        _log.logger.critical(str(e) + "\n")

if __name__ == '__main__':

    investigations_open = []
    investigations_waiting = []
    investigations_inv = []
    _utils = Utils()
    _log = Logger()
    
    inv = API(_utils.get_RAPID7_url_base(), _utils.get_RAPID7_url_path(), _utils.get_RAPID7_url_path_single_inv(),
              _utils.get_RAPID7_TOKEN(),
              _utils.get_RAPID7_time_in_seconds_w())
    
    parse_json(inv.call_api(_utils.get_RAPID7_time_in_seconds_w()), _utils.get_RAPID7_tenant_url())
    send_report()
