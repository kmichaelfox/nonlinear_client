from datetime import datetime
import socket
import threading
import subprocess
import re
import select

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button

import argparse
import math
import time
import random

from pythonosc import dispatcher, osc_server, osc_message_builder, udp_client
from zeroconf import ServiceBrowser, ServiceInfo, ServiceStateChange, Zeroconf

class ptr:
    def __init__(self, obj): self.obj = obj
    def get(self): return self.obj
    def set(self, obj): self.obj = obj

# class ServiceListener():
#     def remove_service(self, zeroconf, type, name):
#         #ChatClient.services = {}
#         info = zeroconf.get_service_info(type, name)
#         if info:
#             # print("Service %s removed, service info:%s" % (name, info))
#             # if info.properties:
#             #     for key, value in info.properties.items():
#             #         print("     %s: %s" % (key, value))
#             print("Removing => " + str(info))
#             #ChatClient.services = refresh_services(info)
#             ChatClient.services[info.properties[b'user'].decode("utf-8")] = refresh_services(info)
#         else:
#             print("Service %s removed, no services left" % (name, ))

#         print(ChatClient.services)

#     def add_service(self, zeroconf, type, name):
#         info = zeroconf.get_service_info(type, name)
#         if info:
#             print("Adding => " + str(info))
#             ChatClient.services[info.properties[b'user'].decode("utf-8")] = refresh_services(info)
#         else:
#             print("Service %s added, service info: %s" % (name, info))

#         print(ChatClient.services)

# def refresh_services(info):
#     if info.name =='nonlinear_chat_client._http._tcp.local.':
#         print("    " + info.properties[b'user'].decode('utf-8'))
#         if info.properties and b'user' in info.properties:
#             return (info.properties[b'user'], socket.inet_ntoa(info.address), info.port)

#     return None

def service_state_change(zeroconf, service_type, name, state_change):
    print("Service %s of type %s state changed: %s" % (name, service_type, state_change))

    if (not CLIENT_NAME.match(name)):
        print("Unrecognized service, skipping...")
        return

    info = zeroconf.get_service_info(service_type, name)

    if state_change is ServiceStateChange.Added:
        print("ADDING   |\n        |v|")
        if info:
            print("  Address: %s:%d" % (socket.inet_ntoa(info.address), info.port))
            print("  Weight: %d, priority:%d" % (info.weight, info.priority))
            print("  Server: %s" % (info.server,))
            if info.properties:
                print("  Properties are:")
                for key, value in info.properties.items():
                    print("    %s: %s" % (key, value))
                if (info.properties[b'user'].decode("utf-8") != ChatClient.uname):
                    ChatClient.services[name] = (info.properties[b'user'], socket.inet_ntoa(info.address), info.port)
                ChatBuffer.instance.get().push_sys_msg(extract_name(name)+" has connected")
            else:
                print("  No properties")
        else:
            print("  No info")
        print('\n')
    else:
        #info = zeroconf.get_service_info(service_type, name)
        print("REMOVING |\n        |v|")
        print("  %s" % name)
        if ChatClient.services.pop(name):
            ChatBuffer.instance.get().push_sys_msg(extract_name(name)+" has disconnected")
        
    print("\n")
    print(ChatClient.services)
    print("\n")

def extract_name(service_name):
    return re.sub(USER_NAME_DELIM, '', service_name)
    
class ChatBuffer(TextInput):
    instance = None

    def __init__(self, **kwargs):
        super(ChatBuffer, self).__init__(**kwargs)
        self.multiline=True
        self.readonly=True
        self.history = ['Ensemble Nonlinear Client', '']
        self.refresh_text()
        if (ChatBuffer.instance == None): ChatBuffer.instance = ptr(self)

    def push(self, input):
        #c_from = self.selection_from
        #c_to = self.selection_to
        self.history = self.history + [ChatClient.uname + ' [' + get_time() + '] $ ' + input.text]

        builder = osc_message_builder.OscMessageBuilder("/ensemble_nonlinear/ch4t")
        builder.add_arg(ChatClient.uname)
        builder.add_arg(get_time())
        builder.add_arg(input.text)
        output = builder.build()
        # services = ChatClient.services
        for key, value in ChatClient.services.items():
            print("sending message to %s" % (value,))
            ChatClient.osc[OSC_BROADCASTER].nl_send_msg((value[SVC_ADDR], value[SVC_PORT]), output)
        #diff = 0
        #while (len(self.history) > 200):
        #    diff = diff + len(self.history.pop(0))

        #diff = diff - len(self.history[-1])
        #c_from = min(0, c_from - diff)
        #c_to = min(0, c_to - diff)

        self.refresh_text()
        #self.selection_from = c_from
        #self.selection_to = c_to
        input.text = ''

    def push_msg(self, input):
        self.history = self.history + [input[MSG_USER] + ' [' + input[MSG_TIME] + '] $ ' + input[MSG_BODY]]
        self.refresh_text()

    def push_sys_msg(self, input):
        lines = input.split('\n')
        self.history += lines
        self.refresh_text()

    def refresh_text(self):
        self.text = '\n'.join(self.history)

class InputBox(TextInput):
    instance = None

    def __init__(self, **kwargs):
        super(InputBox, self).__init__(**kwargs)
        self.multiline = False
        self.size_hint=(1, 1)
        self.focus = True
        #self.bind(on_text_validate=self.on_enter)
        #self.bind(focus=True)
        if (InputBox.instance == None): InputBox.instance = ptr(self)

    def on_text_validate(self):
        if (len(self.text) == 0):
            Clock.schedule_once(self.refocus_self)
            return

        ChatBuffer.instance.get().push(self)
        Clock.schedule_once(self.refocus_self)

    def refocus_self(self, *args):
        self.focus = True;

    def on_release(instance, value):
        pass

class InputSubmitButton(Button):
    def __init__(self, **kwargs):
        super(Button, self).__init__(**kwargs)
        self.text='Send'
        self.size_hint=(None, 1)
        self.width=40
        self.bind(on_press=self.callback)

    def callback(instance, value):
        if (len(InputBox.instance.get().text) == 0): return

        ChatBuffer.instance.get().push(InputBox.instance.get())

class InputPane(BoxLayout):
    def __init__(self, **kwargs):
        super(InputPane, self).__init__(**kwargs)
        self.size_hint=(1, None)
        self.height=30
        self.label = Label(text='=>')
        self.add_widget(self.label)
        self.label.size_hint=(None, 1)
        self.label.width=30
        self.input=InputBox()
        self.add_widget(self.input)
        self.submit=InputSubmitButton()
        self.add_widget(self.submit)

def get_computer_name():
        cmd = "scutil --get ComputerName"
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()

        return output[:-1].decode('utf-8')

def get_time():
    return datetime.now().strftime("%H:%M:%S")

# def chat_receive(unused_addr, *args):
#     print("message received")
#     ChatBuffer.instance.get().push_msg((args[MSG_USER], args[MSG_TIME], args[MSG_BODY]))
def chat_receive(unused_addr, usr, time, body):
    print("message received")
    ChatBuffer.instance.get().push_msg((usr, time, body))

'''
This needs to be fixed, it won't be functional
'''
def link_patch(unused_addr, args, msg):
    ChatBuffer.instance.get().push_msg([ChatClient.uname, get_time(), msg[2]])
    builder = osc_message_builder.OscMessageBuilder(msg[0])
    builder.add_arg(ChatClient.ports[OSC_LISTENER])
    output = builder.build()
    ChatClient.osc[OSC_BROADCASTER].nl_send_msg((LOCALHOST, msg[1]), output)

LOCALHOST = "127.0.0.1"
OSC_LISTENER = 0
OSC_BROADCASTER = 1
ZCONF_REGISTER = 0
ZCONF_BROWSER = 1

SVC_USER = 0
SVC_ADDR = 1
SVC_PORT = 2

MSG_USER = 0
MSG_TIME = 1
MSG_BODY = 2

DEST_ADDR = 0
DEST_PORT = 1

NAME_PATTERN = "_nonlinear_client\._http\._tcp\.local\."
CLIENT_NAME = re.compile(".+(%s)"%(NAME_PATTERN,), re.U)
USER_NAME_DELIM = re.compile(NAME_PATTERN, re.U)

class ChatClient(BoxLayout):
    uname = None
    ports = None
    osc = None
    server_thread = None
    zconf = None
    service_info = None
    services = {}

    def __init__(self, **kwargs):
        super(ChatClient, self).__init__(**kwargs)
        ChatClient.uname = get_computer_name()
        #ChatClient.uname = ' '.join(socket.gethostbyaddr(socket.gethostname())[0].split('.'))
        self.padding = 10
        self.orientation='vertical'
        self.history=ChatBuffer()
        self.add_widget(self.history)
        self.input_pane=InputPane()
        self.add_widget(self.input_pane)

        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map("/ensemble_nonlinear/ch4t", chat_receive)
        self.dispatcher.map("/ensemble_nonlinear/link_patch", link_patch)

        zconf = Zeroconf()
        ChatClient.osc = self.init_osc()

        if ChatClient.uname == "anonymous":
            ChatClient.uname += ':'+str(ChatClient.ports[OSC_LISTENER])

        ChatClient.zconf = self.init_zconf(zconf)

    def __del__(self):
        if ChatClient.osc != None:
            ChatClient.osc[OSC_LISTENER].shutdown()

        if ChatClient.zconf != None:
            ChatClient.zconf[ZCONF_REGISTER].unregister_service(ChatClient.service_info)

    def init_osc(self):
        ChatClient.ports = self.get_open_ports()
        listening_port = ChatClient.ports[OSC_LISTENER]
        broadcasting_port = ChatClient.ports[OSC_BROADCASTER]

        print("Listening on port: %d", listening_port)
        print("Broadcasting on port: %d", broadcasting_port)

        broadcaster = self.init_broadcaster(broadcasting_port)
        listener = self.init_listener(listening_port)

        return (listener, broadcaster)

    def init_listener(self, port):
        server = osc_server.ThreadingOSCUDPServer((socket.gethostbyname(socket.getfqdn()), port), self.dispatcher)
        ChatClient.server_thread = threading.Thread(target=server.serve_forever)
        ChatClient.server_thread.start()
        return server

    def init_broadcaster(self, port):
        #return udp_client.SimpleUDPClient("127.0.0.1", 5005)
        client = NonlinearOSCClient(LOCALHOST, port)
        client.connect((LOCALHOST, port))
        return client

    def init_zconf(self, zeroconf):
        return (self.init_service_registry(zeroconf), self.init_service_browser(zeroconf))

    def init_service_browser(self, zeroconf):
        #listener = ServiceListener()
        #browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
        browser = ServiceBrowser(zeroconf, "_http._tcp.local.", handlers=[service_state_change])
        return browser

    def init_service_registry(self, zeroconf):
        desc = {'user': ChatClient.uname}
        info = ServiceInfo("_http._tcp.local.",
                         ChatClient.uname+"_nonlinear_client._http._tcp.local.",
                         socket.inet_aton(socket.gethostbyname(socket.getfqdn())),
                         ChatClient.ports[OSC_LISTENER], 0, 0, desc)
        ChatClient.service_info = info
        zeroconf.register_service(info)
        return zeroconf

    def get_open_ports(self):
        ports = [None, None]
        for i in range(0,2):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("", 0))
            s.listen(1)
            ports[i] = s.getsockname()[1]
            s.close()

        return tuple(ports)

class ClientApp(App):
    def build(self):
        return ChatClient()

class OSCError(Exception):
    """Base Class for all OSC-related errors
    """
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class OSCClientError(OSCError):
    """Class for all OSCClient errors
    """
    pass

class NonlinearOSCClient(object):
    SND_BUF_SIZE = 4096 * 8
    
    def __init__(self, addr, port):
        #super(NonlinearOSCClient, self).__init__(LOCALHOST, 1234)
        self._client_address = (addr, port)
        self._sock=None
        #self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self._sock.connect(self._client_address)
        #self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.sndbuf_size)
        #self._fd = self._sock.fileno()

    def connect(self, address):
        try:
            self._ensureConnected(address)
            self._client_address = address
        except socket.error as e:
            self._client_address = None
            raise OSCClientError("SocketError: %s" % str(e))

    def _ensureConnected(self, address):
        if not self._sock:
            self._setSocket(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        self._sock.connect(address)

    def _setSocket(self, skt):
        if self._sock != None:
            self.close()
        self._sock = skt
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, NonlinearOSCClient.SND_BUF_SIZE)
        self._fd = self._sock.fileno()
        print("\n\n\t\t\tself._fd = %s\n\n" % (self._fd,))

    def close(self):
        if self._sock != None:
            self._sock.close()
        self._sock = None

    def nl_send_msg(self, addr, msg, timeout=None):
        #if not isinstance(destination, tuple) and not isinstance(destination[0], basestring) and not isinstance(destination[1], int):
        print("SENDING MSG: "+ str(addr[DEST_ADDR]) + " " + str(addr[DEST_PORT]))
        #self._address = destination[0]
        #self._port = destination[1]
        #self.send(msg)
        ret = select.select([], [self._fd], [], timeout)
        try:
            ret[1].index(self._fd)
        except:
            raise OSCClientError("Timed out wiating for file descriptor")

        try:
            self._ensureConnected(addr)
            self._sock.sendall(msg.dgram)

            if self._client_address:
                self._sock.connect(self._client_address)
        except OSError:
            if sys.exc_info()[0] in (7, 65): # 7: no addr associated with node, 65: no route to host
                raise e
            else:
                raise OSCClientError("while sending to %s: %s" % (str(address), str(e)))


if __name__ == '__main__':
    ClientApp().run()
    ChatClient.osc[OSC_LISTENER].shutdown()
    ChatClient.osc[OSC_BROADCASTER].close()
    ChatClient.osc = None
    ChatClient.zconf[ZCONF_REGISTER].unregister_service(ChatClient.service_info)
    ChatClient.zconf[ZCONF_BROWSER].cancel()
    ChatClient.zconf[ZCONF_REGISTER].close()
