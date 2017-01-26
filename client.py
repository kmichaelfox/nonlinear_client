from datetime import datetime
import socket
import threading

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
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf

class ptr:
    def __init__(self, obj): self.obj = obj
    def get(self): return self.obj
    def set(self, obj): self.obj = obj

class ChatHistory(TextInput):
    instance = None

    def __init__(self, **kwargs):
        super(ChatHistory, self).__init__(**kwargs)
        self.multiline=True
        self.readonly=True
        self.history = ['Ensemble Nonlinear Client', '']
        self.text = '\n'.join(self.history)
        if (ChatHistory.instance == None): ChatHistory.instance = ptr(self)

    def push(self, input):
        #c_from = self.selection_from
        #c_to = self.selection_to
        self.history = self.history + [ChatClient.uname + ' [' + get_time() + '] $ ' + input.text]
        #diff = 0
        #while (len(self.history) > 200):
        #    diff = diff + len(self.history.pop(0))

        #diff = diff - len(self.history[-1])
        #c_from = min(0, c_from - diff)
        #c_to = min(0, c_to - diff)

        self.text = '\n'.join(self.history)
        #self.selection_from = c_from
        #self.selection_to = c_to
        input.text = ''

    def push_msg(self, input):
        self.history = self.history + [input[1] + ' [' + input[2] + '] $ ' + input[3]]
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

        ChatHistory.instance.get().push(self)
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

        ChatHistory.instance.get().push(InputBox.instance.get())

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

def get_time():
    return datetime.now().strftime("%H:%M:%S")

def chat_receive(unused_addr, args, msg):
    ChatHistory.instance.get().push_msg(msg)

def link_patch(unused_addr, args, msg):
    ChatHistory.instance.get().push_msg([ChatClient.uname, get_time(), msg[2]])
    builder = OscMessageBuilder(msg[0])
    builder.add_arg(ChatClient.ports[OSC_LISTENER])
    ChatClient.osc[OSC_BROADCASTER].nl_send_msg((LOCALHOST, msg[1]), output)

LOCALHOST = "127.0.0.1"
OSC_LISTENER = 0
OSC_BROADCASTER = 1
ZCONF_REGISTER = 0
ZCONF_BROWSER = 1

class ChatClient(BoxLayout):
    uname = None
    ports = None
    osc = None
    server_thread = None
    zconf = None
    service_info = None
    services = None

    def __init__(self, **kwargs):
        super(ChatClient, self).__init__(**kwargs)
        ChatClient.uname = socket.gethostbyaddr(socket.gethostname())[0].split('.')[0]
        self.padding = 10
        self.orientation='vertical'
        self.history=ChatHistory()
        self.add_widget(self.history)
        self.input_pane=InputPane()
        self.add_widget(self.input_pane)

        self.dispatcher = dispatcher.Dispatcher()
        self.dispatcher.map("/ensemble_nonlinear/ch4t/", chat_receive)
        self.dispatcher.map("/ensemble_nonlinear/link_patch", link_patch)

        ChatClient.osc = self.init_osc()
        ChatClient.zconf = self.init_zconf()

    def __del__(self):
        if ChatClient.osc != None:
            ChatClient.osc[OSC_LISTENER].shutdown()

        if ChatClient.zconf != None:
            ChatClient.zconf[ZCONF_REGISTER].unregister_service(ChatClient.service_info)

    def init_osc(self):
        listening_port, broadcasting_port = ChatClient.ports = self.get_open_ports()

        print("Listening on port: %d", listening_port)
        print("Broadcasting on port: %d", broadcasting_port)

        broadcaster = self.init_broadcaster(broadcasting_port)
        listener = self.init_listener(listening_port)

        return (listener, broadcaster)

    def init_listener(self, port):
        server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", port), self.dispatcher)
        ChatClient.server_thread = threading.Thread(target=server.serve_forever)
        ChatClient.server_thread.start()
        return server

    def init_broadcaster(self, port):
        #return udp_client.SimpleUDPClient("127.0.0.1", 5005)
        return NonlinearOSCClient()

    def init_zconf(self):
        return (self.init_service_registry(), self.init_service_browser())

    def init_service_browser(self):
        return None

    def init_service_registry(self):
        desc = {'user': ChatClient.uname}
        info = ServiceInfo("_http._tcp.local.",
                         "nonlinear_chat_client._http._tcp.local.",
                         socket.inet_aton(LOCALHOST),
                         ChatClient.ports[OSC_LISTENER], 0, 0, desc)
        r = Zeroconf()
        ChatClient.service_info = info
        r.register_service(info)
        return r

    def get_open_ports(self):
        ports = [None, None]
        for i in range(0,1):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("", 0))
            s.listen(1)
            ports[i] = s.getsockname()[1]
            s.close()

        return tuple(ports)

class ClientApp(App):
    def build(self):
        return ChatClient()

class NonlinearOSCClient(udp_client.SimpleUDPClient):
    def __init__(self):
        super(NonlinearOSCClient, self).__init__("127.0.0.1", 1234)

    def nl_send_msg(self, destination, msg):
        #if not isinstance(destination, tuple) and not isinstance(destination[0], basestring) and not isinstance(destination[1], int):
        self._address = destination[0]
        self._port = destination[1]
        self.send(msg)

if __name__ == '__main__':
    ClientApp().run()
    ChatClient.osc[OSC_LISTENER].shutdown()
    ChatClient.osc = None
    ChatClient.zconf[ZCONF_REGISTER].unregister_service(ChatClient.service_info)
