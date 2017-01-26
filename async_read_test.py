from zeroconf import Zeroconf, ServiceBrowser

class MyListener():

    def remove_service(self, zeroconf, type, name):
        print("Service %s removed" % (name, ))

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        print("Service %s added, service info: %s" % (name, info))

def main():
    global zeroconf
    global listener
    global browser

    zeroconf = Zeroconf()
    listener = MyListener()
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)

    try: input("Press enter to exit...\n\n")
    finally: zeroconf.close()

zeroconf = None
listener = None
browser = None
services = {}

if __name__ == '__main__':
    main()
