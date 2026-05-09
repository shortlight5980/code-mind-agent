import os

def greet(name):
    return f"hello {name}"

class Service:
    def run(self):
        return os.getcwd()